# LinqAlpha Financial Research Agent

AI-powered financial research agent for OpenBB Workspace using LinqAlpha's APIs.

## About

This agent combines **LinqAlpha's** multi-agent AI platform for investment research with **OpenBB Workspace's** enterprise infrastructure for data visualization and workflow customization. LinqAlpha specializes in processing unstructured financial data from earnings transcripts, SEC filings, and regulatory documents, while OpenBB provides the secure, customizable interface for institutional research workflows. Together, the two solutions enable research teams to access specialized AI agents directly within OpenBB's platform, streamlining complex analysis from filing review to peer comparison in minutes. Learn more in this [blog post](https://openbb.co/blog/how-openbb-and-linqalpha-can-power-institutional-research-workflows).

## Features

- **Search Chat**: Financial document search (transcripts, news, filings)
- **RMS Chat**: Enhanced research with organizational context
- **RMS Deep Research**: Multi-step comprehensive analysis

## Installation

1. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

2. **Configure environment**

   Copy `.env.example` to `.env`:
   ```bash
   cp .env.example .env
   ```

   Edit `.env` and add your API key:
   ```bash
   LINQALPHA_API_KEY=your_api_key_here
   ```

   Get your API key from [LinqAlpha](https://api.linqalpha.com)

3. **Run the agent**
   ```bash
   python agent.py
   ```

   Agent runs on `http://0.0.0.0:7777`

## Configuration

### Required
- `LINQALPHA_API_KEY` - Your LinqAlpha API key

### Optional (for RMS features)
- `LINQALPHA_ORG_ID` - Organization ID for RMS Chat/Deep Research
- `LINQALPHA_USER_ID` - User identifier
- `LINQALPHA_USER_EMAIL` - User email
- `LINQALPHA_USER_NAME` - User name

## Adding to OpenBB Workspace

### Prerequisites

Make sure the agent is running before adding it to OpenBB Workspace:
```bash
python agent.py
```

The agent should be accessible at `http://localhost:7777`

### Integration Steps

1. **Open OpenBB Workspace**

2. **Access the OpenBB Copilot**
   - Look for the OpenBB Copilot button at the bottom right of the Workspace interface
   - Click on it to open the Copilot panel

3. **Add New Agent**
   - Click the **+** icon (or pencil icon if editing) in the Copilot panel
   - Enter the agent base URL: `http://localhost:7777`
   - OpenBB Workspace will automatically fetch the agent metadata from `/agents.json`

   ![Add new agent](https://openbb-cms.directus.app/assets/412540b0-ef86-4285-8303-b9faf83bdc66.png)

   - The agent will appear in your available agents list

   ![Agent added successfully](https://openbb-cms.directus.app/assets/ce3bebd7-98cf-4598-9d6c-68a2ecc1ba1c.png)

4. **Start Using the Agent**

   Try these example queries:
   - "What was Apple's revenue in Q4 2023?"
   - "Compare Tesla and Rivian's delivery numbers"
   - "Analyze the latest Fed meeting transcript"
   - "Show me recent insider trading for NVIDIA"

### Technical Details

The agent exposes two endpoints for OpenBB Workspace:
- **`/agents.json`**: Returns agent metadata (name, description, features)
- **`/query`**: Handles queries via POST and streams responses using Server-Sent Events (SSE)

CORS is properly configured to allow OpenBB Workspace to communicate with the agent.

### Research Modes

- **Default**: Search Chat (no toggle needed)
- **RMS Chat**: Enable "RMS Chat" toggle (requires `LINQALPHA_ORG_ID`)
- **Deep Research**: Enable "RMS Deep Research" toggle (requires `LINQALPHA_ORG_ID`)

## Project Structure

```
agent.py          # Main application
settings.py       # Configuration
.env              # Your API keys (not in git)
.env.example      # Template
README.md         # This file
```