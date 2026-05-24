# F.R.I.D.A.Y. — Tony Stark Demo

> *"Fully Responsive Intelligent Digital Assistant for You"*

A Tony Stark-inspired AI assistant split into two cooperating pieces:

| Component | What it is |
|-----------|-----------|
| **MCP Server** (`uv run friday`) | A [FastMCP](https://github.com/jlowin/fastmcp) server that exposes tools (news, web search, system info, …) over SSE. Think of it as the Stark Industries backend — it does the actual work. |
| **Voice Agent** (`uv run friday_voice`) | A [LiveKit Agents](https://github.com/livekit/agents) voice pipeline that listens to your microphone, reasons with an LLM (OpenAI by default), and speaks back with OpenAI TTS — all while pulling tools from the MCP server in real time. |

Demo: [Instagram reel](https://www.instagram.com/p/DW2HjYtkwg_/)

[![Demo Video Guide](https://img.youtube.com/vi/mMY9swqe3BI/maxresdefault.jpg)](https://www.youtube.com/watch?v=mMY9swqe3BI)

---

## How it works

```
Microphone ──► STT (Sarvam Saaras v3)
                    │
                    ▼
             LLM (OpenAI default)    ◄──────► MCP Server (FastMCP / SSE)
                    │                              ├─ get_world_news
                    ▼                              ├─ open_world_monitor
             TTS (OpenAI nova)                     ├─ search_web
                    │                              └─ …more tools
                    ▼
             Speaker / LiveKit room
```

The voice agent connects to the MCP server via SSE at `http://127.0.0.1:8000/sse` (auto-resolved to the Windows host IP when running inside WSL).

---

## Project structure

```
friday-tony-stark-demo/
├── server.py           # uv run friday  → starts the MCP server (SSE on :8000)
├── agent_friday.py     # uv run friday_voice → starts the LiveKit voice agent
├── pyproject.toml
├── .env.example        # copy → .env and fill in your keys
│
└── friday/             # MCP server package
    ├── config.py       # env-var loading & app-wide settings
    ├── tools/          # MCP tools (callable by the LLM)
    │   ├── web.py      # search_web, fetch_url, get_world_news, open_world_monitor
    │   ├── system.py   # get_current_time, get_system_info
    │   └── utils.py    # format_json, word_count
    ├── prompts/        # MCP prompt templates (summarize, explain_code, …)
    └── resources/      # MCP resources exposed to clients (friday://info)
```

---

## Quick start

### 1. Prerequisites

- Python ≥ 3.11
- [`uv`](https://github.com/astral-sh/uv) — `pip install uv` or `curl -Lsf https://astral.sh/uv/install.sh | sh`
- Local LiveKit for development, or a [LiveKit Cloud](https://cloud.livekit.io) project for remote/cloud testing

### 2. Clone & install

```bash
git clone https://github.com/SAGAR-TAMANG/friday-tony-stark-demo.git
cd friday-tony-stark-demo
uv sync          # creates .venv and installs all dependencies
```

### 3. Set up environment

```bash
cp .env.example .env
# Open .env and fill in your API keys (see the section below)
```

### 4. Run — local LiveKit first

For fastest local testing, run Friday against a local LiveKit server:

```powershell
scripts\install-livekit-server-windows.ps1
scripts\use-livekit-local.ps1
scripts\start-livekit-local.ps1
```

See [docs/livekit-local.md](docs/livekit-local.md) for the full local stack and restore instructions.

### 5. Run — one-command local stack

For a production-style local launch with logs and health checks:

```powershell
scripts\start-friday-stack.ps1
```

This starts local LiveKit, the MCP server, the voice agent, and the desktop UI. Logs and pid files are written to `logs\`.

Useful launcher variants:

```powershell
scripts\start-friday-stack.ps1 -SkipMcp -SkipVoiceAgent -SkipDesktopUi
scripts\stop-friday-stack.ps1
```

### 6. Run — two terminals

**Terminal 1 — MCP server** (must start first)

```bash
uv run friday
```

Starts the FastMCP server on `http://127.0.0.1:8000/sse`. The voice agent connects here to fetch its tools.

**Terminal 2 — Voice agent**

```bash
uv run friday_voice
```

Starts the LiveKit voice agent in **dev mode** — it joins a LiveKit room and begins listening. Open the [LiveKit Agents Playground](https://agents-playground.livekit.io) and connect to your room to talk to FRIDAY.

---

## `uv run friday` vs `uv run friday_voice`

| Command | Entry point | What it does |
|---------|------------|--------------|
| `uv run friday` | `server.py → main()` | Launches the **FastMCP server** over SSE transport on port 8000. This is the "brain backend" — it registers all tools, prompts, and resources that the LLM can call. |
| `uv run friday_voice` | `agent_friday.py → dev()` | Launches the **LiveKit voice agent**. It builds the STT / LLM / TTS pipeline, connects to your LiveKit room, and wires up the MCP server as a tool source. The `dev()` wrapper auto-injects the `dev` CLI flag so you don't have to type it manually. |

> Both processes must run **simultaneously**. The voice agent calls the MCP server in real time whenever it needs a tool (e.g. fetching news).

---

## Environment variables

Copy `.env.example` → `.env` and fill in the values below.

| Variable | Required | Where to get it |
|----------|----------|----------------|
| `LIVEKIT_URL` | ✅ | Local: `ws://127.0.0.1:7880`; Cloud: LiveKit Cloud project URL |
| `LIVEKIT_API_KEY` | ✅ | Local: `devkey`; Cloud: LiveKit Cloud API key |
| `LIVEKIT_API_SECRET` | ✅ | Local: `secret`; Cloud: LiveKit Cloud API secret |
| `GROQ_API_KEY` | optional | [console.groq.com](https://console.groq.com) — only needed if you switch `LLM_PROVIDER` to `"groq"` |
| `SARVAM_API_KEY` | ✅ (default STT) | [dashboard.sarvam.ai](https://dashboard.sarvam.ai) |
| `OPENAI_API_KEY` | ✅ (default LLM/TTS) | [platform.openai.com/api-keys](https://platform.openai.com/api-keys) |
| `DEEPGRAM_API_KEY` | optional | [console.deepgram.com](https://console.deepgram.com) |
| `GOOGLE_APPLICATION_CREDENTIALS` | optional | GCP service-account JSON path — only for `STT_PROVIDER = "google"` |
| `GOOGLE_API_KEY` | optional | [aistudio.google.com](https://aistudio.google.com/projects) — only needed if `LLM_PROVIDER=gemini` |
| `SUPABASE_URL` | optional | [supabase.com](https://supabase.com) — for the ticketing tool |
| `SUPABASE_API_KEY` | optional | Supabase project → API settings |

---

## Switching providers

Set these in `.env` so provider changes do not require code edits:

```dotenv
STT_PROVIDER=sarvam
LLM_PROVIDER=openai
TTS_PROVIDER=openai
FRIDAY_MODE=balanced
OPENAI_LLM_MODEL=gpt-4o
OPENAI_LLM_TEMPERATURE=0.35
OPENAI_LLM_MAX_TOKENS=220
SARVAM_STT_LANGUAGE=en-IN
SARVAM_STT_MODEL=saaras:v3
```

Latency-sensitive turn handling is also configurable from `.env`:

```dotenv
FRIDAY_MAX_ENDPOINTING_DELAY=0.45
FRIDAY_MIN_INTERRUPTION_DURATION=0.28
FRIDAY_MIN_INTERRUPTION_WORDS=1
```

---

## Current capabilities

- Live world and finance headline briefs with optional dashboard opening.
- Web search, URL fetch, and safe browser opening.
- Local time, system info, system snapshot, arithmetic, JSON formatting, word counts, and compact text.
- Explicit memory tools: remember, recall, and forget user-approved facts or preferences.
- Voice-first system prompting that asks for clarification when STT output looks garbled instead of confidently answering nonsense.
- Real LiveKit telemetry packets for agent state, transcript events, tool calls, interruptions, errors, and latency.
- Desktop debug panel with STT, turn, LLM, TTS, and end-to-response timing.
- Visible desktop memory panel backed by the same local memory file as the MCP tools.
- One-command stack launcher with local service checks and logs.

---

## Adding a new tool

1. Create or open a file in `friday/tools/`
2. Define a `register(mcp)` function and decorate tools with `@mcp.tool()`
3. Import and call `register(mcp)` inside `friday/tools/__init__.py`

The MCP server will pick it up on next start.

---

## Tech stack

- **[FastMCP](https://github.com/jlowin/fastmcp)** — MCP server framework
- **[LiveKit Agents](https://github.com/livekit/agents)** — real-time voice pipeline
- **Sarvam Saaras v3** — STT (Indian-English optimised)
- **OpenAI / Google Gemini** — configurable LLM
- **OpenAI TTS** (`nova` voice) — TTS
- **[uv](https://github.com/astral-sh/uv)** — fast Python package manager

---

## License

MIT
