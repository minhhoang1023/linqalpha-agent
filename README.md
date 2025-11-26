# LinqAlpha Financial Research Agent

AI-powered financial research agent for OpenBB Workspace using LinqAlpha's APIs.

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

## Usage with OpenBB Workspace

1. Open OpenBB Workspace
2. Go to Settings → Agents
3. Add agent URL: `http://localhost:7777`
4. Start asking questions:
   - "What was Apple's revenue in Q4 2023?"
   - "Compare Tesla and Rivian's delivery numbers"
   - "Analyze the latest Fed meeting transcript"

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