"""
LinqAlpha Financial Research Agent for OpenBB Workspace.

Integrates LinqAlpha's Search and RMS APIs to provide AI-powered financial research.
Supports three modes:
- Search Chat: Basic financial document search and Q&A
- RMS Chat: Enhanced research with organizational context
- RMS Deep Research: Comprehensive multi-step analysis

Each mode requires different configuration settings. See README for details.
"""

import json
from typing import AsyncGenerator, Any, Dict, List

import httpx
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from openbb_ai import message_chunk
from openbb_ai.models import (
    Citation,
    CitationCollection,
    CitationCollectionSSE,
    SourceInfo,
    MessageChunkSSE,
    QueryRequest,
)
from sse_starlette.sse import EventSourceResponse

from settings import get_settings

# Configuration
settings = get_settings()

# API Constants
LINQALPHA_BASE_URL = "https://api.linqalpha.com"
LINQALPHA_V1_URL = f"{LINQALPHA_BASE_URL}/v1"
LINQALPHA_V2_URL = f"{LINQALPHA_BASE_URL}/v2"

# Timeout Constants (in seconds)
DEFAULT_TIMEOUT = 30.0
LONG_TIMEOUT = 60.0
STREAM_TIMEOUT = 120.0

# Content Constants
CONTENT_TRUNCATE_LIMIT = 10000
URL_EXPIRY_TIME = "10 minutes"

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Helper Functions

def _build_api_headers() -> Dict[str, str]:
    """Build HTTP headers for LinqAlpha API requests."""
    return {
        "X-API-KEY": settings.linqalpha_api_key,
        "Content-Type": "application/json",
    }


def _build_rms_payload(user_message: str, org_id: str) -> Dict[str, Any]:
    """Build payload for RMS API requests (both Chat and Deep Research)."""
    return {
        "organization_id": org_id,
        "user_id": settings.linqalpha_user_id,
        "user_email": settings.linqalpha_user_email,
        "user_name": settings.linqalpha_user_name,
        "query": user_message,
        "search_types": ["rms", "external"],
        "external_types": ["transcript", "filing", "news"],
    }


def _build_search_payload(user_message: str) -> Dict[str, Any]:
    """Build payload for Search Chat API requests."""
    return {
        "query": user_message,
        "external_types": ["transcript", "news", "filing"],
    }


async def _fetch_citations(
    client: httpx.AsyncClient, chat_message_id: str, headers: Dict[str, str]
) -> List[Citation]:
    """
    Fetch and format citations from LinqAlpha API.

    Args:
        client: HTTP client instance
        chat_message_id: The chat message ID to fetch citations for
        headers: HTTP headers for the request

    Returns:
        List of unique Citation objects sorted by citation index
    """
    try:
        refs_response = await client.get(
            f"{LINQALPHA_V1_URL}/references",
            headers=headers,
            params={"chat_message_id": chat_message_id},
            timeout=DEFAULT_TIMEOUT
        )
        refs_response.raise_for_status()
        refs_data = refs_response.json()

        if refs_data.get("error"):
            return []

        references = refs_data.get("payload", {}).get("references", [])
        if not references:
            return []

        # Deduplicate by citation_idx, keeping first occurrence
        seen_citations = {}
        for ref in references:
            citation_idx = ref.get('citation_idx')
            if citation_idx is None:
                continue

            # Convert to int for proper comparison
            try:
                idx = int(citation_idx)
            except (ValueError, TypeError):
                continue

            # Keep only the first occurrence of each citation_idx
            if citation_idx not in seen_citations:
                seen_citations[citation_idx] = {
                    'idx': idx,
                    'name': ref.get('document_name', 'Unknown Document'),
                    'citation_idx': citation_idx
                }

        # Sort by citation index and create Citation objects
        citations = []
        for citation_idx, info in sorted(seen_citations.items(), key=lambda x: x[1]['idx']):
            url = f"https://chat.linqalpha.com/rms/viewer?chat_message_id={chat_message_id}&citation_idx={info['citation_idx']}"
            citation_name = f"[{info['citation_idx']}] - {info['name']}"

            citations.append(
                Citation(
                    source_info=SourceInfo(type="web", name=citation_name),
                    details=[{"Link": url, "Title": info['name']}],
                )
            )

        return citations
    except Exception:
        return []


async def _handle_search_chat_stream(
    response: httpx.Response,
) -> AsyncGenerator[tuple[str, Any], None]:
    """
    Handle Search Chat API streaming response.

    Yields:
        Tuples of (event_type, data) where event_type can be:
        - 'answer': Answer piece to display
        - 'usage': Token usage info
        - 'error': Error message
        - 'chat_message_id': Chat message ID for citation fetching
    """
    received_data = False
    buffer = ""

    async for chunk_bytes in response.aiter_bytes():
        chunk = chunk_bytes.decode("utf-8", errors="replace")
        buffer += chunk

        while "\n" in buffer:
            line, buffer = buffer.split("\n", 1)
            line = line.strip()
            if not line:
                continue

            try:
                # Parse SSE format
                if line.startswith("data: "):
                    json_str = line[6:].strip()
                elif line.startswith("{"):
                    json_str = line.strip()
                else:
                    continue

                # Skip markers
                if json_str in ["[DONE]", ""]:
                    continue

                data = json.loads(json_str)
                received_data = True

                event_name = data.get("event_name", "")
                event_data = data.get("data", {})

                # Capture chat_message_id
                if event_name in ["search_results_id", "search_results"]:
                    if "chat_message_id" in event_data:
                        yield ("chat_message_id", event_data["chat_message_id"])

                # Handle answer pieces
                if event_name == "answer":
                    answer_piece = event_data.get("answer_piece", "")
                    if answer_piece:
                        yield ("answer", answer_piece)

                # Handle usage information
                if "usage" in event_data and event_data["usage"]:
                    usage = event_data["usage"]
                    total_tokens = usage.get("total_tokens", 0)
                    if total_tokens:
                        yield ("usage", total_tokens)

                # Handle errors
                if "error" in event_data and event_data["error"]:
                    yield ("error", event_data["error"])

            except json.JSONDecodeError:
                continue
            except Exception:
                continue

    if not received_data:
        yield ("no_data", None)


async def _handle_rms_stream(
    response: httpx.Response, show_thinking: bool = False
) -> AsyncGenerator[tuple[str, Any], None]:
    """
    Handle RMS API (Chat and Deep Research) streaming response.

    Args:
        response: HTTP response object
        show_thinking: Whether to show thinking/sub-questions (for Deep Research)

    Yields:
        Tuples of (event_type, data) where event_type can be:
        - 'answer': Answer piece to display
        - 'message': Status message
        - 'status': Status update
        - 'think': Thinking process (if show_thinking=True)
        - 'sub_questions': Sub-questions list (if show_thinking=True)
    """
    async for line in response.aiter_lines():
        if not line.strip():
            continue

        try:
            if line.startswith("data: "):
                event_data = json.loads(line[6:])
                event_name = event_data.get("event_name", "")
                data = event_data.get("data", {})

                if event_name == "answer":
                    answer_piece = data.get("answer_piece", "")
                    if answer_piece:
                        yield ("answer", answer_piece)

                elif event_name == "message":
                    message = data.get("message", "")
                    if message:
                        yield ("message", message)

                elif event_name == "status":
                    status = data.get("status", "")
                    if status:
                        yield ("status", status)

                elif event_name == "think" and show_thinking:
                    thought = data.get("think", "")
                    if thought:
                        yield ("think", thought)

                elif event_name == "sub_questions" and show_thinking:
                    questions = data.get("sub_questions", [])
                    if questions:
                        yield ("sub_questions", questions)

        except json.JSONDecodeError:
            continue


@app.get("/agents.json")
def get_copilot_description():
    """Agent descriptor for the OpenBB Workspace."""
    return JSONResponse(
        content={
            "linqalpha_agent": {
                "name": "LinqAlpha Financial Research",
                "description": "AI-powered financial research using LinqAlpha's Search and RMS APIs.",
                "image": (
                    "https://media.licdn.com/dms/image/v2/D560BAQG3rQG9rxYfIg/company-logo_200_200/B56ZVDR2WWGQAM-/0/1740590507808/linqalpha_logo?e=2147483647&v=beta&t=z7SVmAzkRqYkPdjAUCRuI5Ed6Nu5a5qTShILsKCV2uY"
                ),
                "endpoints": {"query": "/v1/query"},
                "features": {
                    "streaming": True,
                    "widget-dashboard-select": True,
                    "widget-dashboard-search": True,
                    "rms-chat": {
                        "label": "RMS Chat",
                        "default": False,
                        "description": "Use LinqAlpha RMS Chat for enhanced research capabilities",
                    },
                    "deep-research": {
                        "label": "RMS Deep Research",
                        "default": False,
                        "description": "Enable comprehensive multi-step analysis with RMS Deep Research",
                    },
                },
            }
        }
    )


@app.post("/v1/query")
async def query(request: QueryRequest) -> EventSourceResponse:
    """
    Process user queries using LinqAlpha APIs.

    Supports three modes based on workspace_options:
    - Default: Search Chat API (no org_id required)
    - rms-chat: RMS Chat API (requires org_id)
    - deep-research: RMS Deep Research API (requires org_id)
    """
    workspace_options = getattr(request, "workspace_options", [])
    rms_chat_enabled = "rms-chat" in workspace_options
    deep_research_enabled = "deep-research" in workspace_options

    # Extract user message
    user_message = ""
    for message in reversed(request.messages):
        if message.role == "human":
            user_message = message.content
            break

    async def execution_loop() -> AsyncGenerator[MessageChunkSSE, None]:
        chat_message_id = None

        # Validate API key
        if not settings.linqalpha_api_key:
            yield message_chunk("⚠️ LinqAlpha API key not configured.\n\n")
            yield message_chunk("Please set LINQALPHA_API_KEY in your .env file.\n")
            yield message_chunk("Get your API key at: https://api.linqalpha.com\n")
            return

        async with httpx.AsyncClient() as client:
            headers = _build_api_headers()

            # Determine endpoint and payload based on selected mode
            if deep_research_enabled:
                if not settings.linqalpha_org_id:
                    yield message_chunk("⚠️ RMS Deep Research requires LINQALPHA_ORG_ID\n\n")
                    return
                endpoint = f"{LINQALPHA_V2_URL}/rms_deep_research"
                payload = _build_rms_payload(user_message, settings.linqalpha_org_id)
                yield message_chunk("🔬 Using RMS Deep Research...\n\n")

            elif rms_chat_enabled:
                if not settings.linqalpha_org_id:
                    yield message_chunk("⚠️ RMS Chat requires LINQALPHA_ORG_ID\n\n")
                    return
                endpoint = f"{LINQALPHA_V2_URL}/rms_chat"
                payload = _build_rms_payload(user_message, settings.linqalpha_org_id)
                yield message_chunk("💬 Using RMS Chat...\n\n")

            else:
                endpoint = f"{LINQALPHA_V2_URL}/chat/sse"
                payload = _build_search_payload(user_message)

            try:
                async with client.stream(
                    "POST", endpoint, json=payload, headers=headers, timeout=STREAM_TIMEOUT
                ) as response:
                    response.raise_for_status()

                    # Handle Search Chat API
                    if "chat/sse" in endpoint:
                        async for event_type, data in _handle_search_chat_stream(response):
                            if event_type == "answer":
                                yield message_chunk(data)
                            elif event_type == "usage":
                                yield message_chunk(f"\n\n_Tokens used: {data}_\n")
                            elif event_type == "error":
                                yield message_chunk(f"\n❌ Error: {data}\n")
                            elif event_type == "chat_message_id":
                                chat_message_id = data
                            elif event_type == "no_data":
                                yield message_chunk("\n⚠️ No response received.\n")
                                yield message_chunk("Possible causes:\n")
                                yield message_chunk("• Invalid API key\n")
                                yield message_chunk("• No matching documents\n")
                                yield message_chunk("• API connectivity issues\n")

                    # Handle RMS APIs (Chat and Deep Research)
                    else:
                        async for event_type, data in _handle_rms_stream(
                            response, show_thinking=deep_research_enabled
                        ):
                            if event_type == "answer":
                                yield message_chunk(data)
                            elif event_type == "message":
                                yield message_chunk(f"\n📌 {data}\n")
                            elif event_type == "status":
                                yield message_chunk(f"\n⏳ Status: {data}\n")
                            elif event_type == "think":
                                yield message_chunk(f"\n🤔 {data}\n")
                            elif event_type == "sub_questions":
                                yield message_chunk("\n📝 Exploring sub-questions:\n")
                                for q in data:
                                    yield message_chunk(f"• {q}\n")

                # Fetch citations for Search Chat
                if chat_message_id:
                    citations = await _fetch_citations(client, chat_message_id, headers)
                    if citations:
                        yield message_chunk("\n\n---\n\n## References\n\n")
                        yield CitationCollectionSSE(data=CitationCollection(citations=citations))

            except httpx.HTTPError as e:
                yield message_chunk(f"\n❌ API Error: {str(e)}\n")
            except Exception as e:
                yield message_chunk(f"\n❌ Unexpected error: {str(e)}\n")

    return EventSourceResponse(
        content=(event.model_dump(exclude_none=True) async for event in execution_loop()),
        media_type="text/event-stream",
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=7777)

