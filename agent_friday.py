"""
FRIDAY – Voice Agent (MCP-powered)
===================================
Iron Man-style voice assistant that controls RGB lighting, runs diagnostics,
scans the network, and triggers dramatic boot sequences via an MCP server
running on the Windows host.

MCP Server URL is auto-resolved from WSL → Windows host IP.

Run:
  uv run agent_friday.py dev      – LiveKit Cloud mode
  uv run agent_friday.py console  – text-only console mode
"""

import os
import asyncio
import json
import logging
import re
import subprocess
import time
from typing import Any

from dotenv import load_dotenv
from livekit.agents import JobContext, WorkerOptions, cli
from livekit.agents.voice import Agent, AgentSession
from livekit.agents.llm import mcp

# Plugins
from livekit.plugins import google as lk_google, openai as lk_openai, sarvam, silero

# ---------------------------------------------------------------------------
# CONFIG
# ---------------------------------------------------------------------------

load_dotenv()


def _env(name: str, default: str) -> str:
    value = os.getenv(name, default).strip()
    return value or default


def _env_int(name: str, default: int) -> int:
    try:
        return int(_env(name, str(default)))
    except ValueError:
        return default


def _env_float(name: str, default: float) -> float:
    try:
        return float(_env(name, str(default)))
    except ValueError:
        return default


FRIDAY_MODE = _env("FRIDAY_MODE", "balanced").lower()
MODE_PRESETS = {
    "fast": {
        "max_tokens": 160,
        "temperature": 0.25,
        "max_endpointing": 0.28,
        "interruption_duration": 0.18,
    },
    "balanced": {
        "max_tokens": 220,
        "temperature": 0.35,
        "max_endpointing": 0.45,
        "interruption_duration": 0.28,
    },
    "accurate": {
        "max_tokens": 320,
        "temperature": 0.3,
        "max_endpointing": 0.85,
        "interruption_duration": 0.38,
    },
}
MODE = MODE_PRESETS.get(FRIDAY_MODE, MODE_PRESETS["balanced"])

STT_PROVIDER = _env("STT_PROVIDER", "sarvam").lower()
LLM_PROVIDER = _env("LLM_PROVIDER", "openai").lower()
TTS_PROVIDER = _env("TTS_PROVIDER", "openai").lower()
FRIDAY_ENABLE_PROVIDER_FALLBACKS = _env("FRIDAY_ENABLE_PROVIDER_FALLBACKS", "true").lower() == "true"
FRIDAY_AGENT_NAME = _env("FRIDAY_AGENT_NAME", "friday")

SARVAM_STT_LANGUAGE = _env("SARVAM_STT_LANGUAGE", "en-IN")
SARVAM_STT_MODEL = _env("SARVAM_STT_MODEL", "saaras:v3")
SARVAM_STT_PROMPT = _env(
    "SARVAM_STT_PROMPT",
    "Common words and names: Friday, Jarvis, LiveKit, OpenAI, Sarvam, "
    "Tony Stark, world monitor, finance monitor, dashboard, latency.",
)

GEMINI_LLM_MODEL = _env("GEMINI_LLM_MODEL", "gemini-2.5-flash")
OPENAI_LLM_MODEL = _env("OPENAI_LLM_MODEL", "gpt-4o")
OPENAI_LLM_TEMPERATURE = _env_float("OPENAI_LLM_TEMPERATURE", MODE["temperature"])
OPENAI_LLM_MAX_TOKENS = _env_int("OPENAI_LLM_MAX_TOKENS", MODE["max_tokens"])

OPENAI_TTS_MODEL = _env("OPENAI_TTS_MODEL", "tts-1")
OPENAI_TTS_VOICE = _env("OPENAI_TTS_VOICE", "nova")
TTS_SPEED = _env_float("TTS_SPEED", 1.15)

SARVAM_TTS_LANGUAGE = _env("SARVAM_TTS_LANGUAGE", "en-IN")
SARVAM_TTS_SPEAKER = _env("SARVAM_TTS_SPEAKER", "rahul")

FRIDAY_MAX_TOOL_STEPS = _env_int("FRIDAY_MAX_TOOL_STEPS", 5)
FRIDAY_MIN_ENDPOINTING_DELAY = _env_float("FRIDAY_MIN_ENDPOINTING_DELAY", -1.0)
FRIDAY_MAX_ENDPOINTING_DELAY = _env_float("FRIDAY_MAX_ENDPOINTING_DELAY", MODE["max_endpointing"])
FRIDAY_MIN_INTERRUPTION_DURATION = _env_float(
    "FRIDAY_MIN_INTERRUPTION_DURATION",
    MODE["interruption_duration"],
)
FRIDAY_MIN_INTERRUPTION_WORDS = _env_int("FRIDAY_MIN_INTERRUPTION_WORDS", 1)
FRIDAY_DEBUG_TOPIC = _env("FRIDAY_DEBUG_TOPIC", "friday.debug")

COMMON_TRANSCRIPT_WORDS = {
    "a", "about", "after", "again", "all", "also", "am", "an", "and", "any", "are",
    "as", "at", "be", "because", "been", "before", "brief", "but", "by", "can",
    "catch", "check", "could", "current", "day", "did", "do", "does", "doing",
    "for", "from", "give", "go", "going", "good", "google", "has", "have",
    "hello", "help", "hey", "how", "i", "if", "in", "is", "it", "jarvis", "just",
    "latest", "let", "like", "look", "make", "market", "markets", "me",
    "memory", "monitor", "my", "need", "news", "no", "now", "of", "on",
    "open", "or", "please", "project", "pull", "question", "read", "response",
    "search", "show", "so", "stock", "summarize", "system", "tell", "that",
    "the", "then", "there", "this", "time", "to", "today", "transcribe", "up",
    "update", "weather", "what", "when", "where", "which", "who", "why", "with",
    "world", "would", "you", "calculator", "chrome", "dashboard", "finance",
    "friday", "livekit", "openai", "sarvam",
}
COMMON_TRANSCRIPT_ACRONYMS = {"AI", "API", "CPU", "GPU", "GPT", "LLM", "STT", "TTS", "VAD", "UI", "URL"}

# MCP server running on Windows host
MCP_SERVER_PORT = 8000

# ---------------------------------------------------------------------------
# System prompt – F.R.I.D.A.Y.
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """
You are F.R.I.D.A.Y. - Fully Responsive Intelligent Digital Assistant for You.
You serve the user as a fast, calm, privacy-aware voice assistant with a light
Tony Stark flavor. You are sharp, useful, and composed. You do not ramble.

Identity and voice:
- Call the user "boss" naturally, not in every sentence.
- Speak like a real-time aide, not a chatbot. Use short spoken paragraphs.
- Be warm when useful, dry only when it helps, and never perform a long bit.
- Do not mention that you are an LLM, model, pipeline, MCP server, tool call,
  or function unless the user explicitly asks about the system internals.

Core capability map:
- Current world news and finance news through live headline tools.
- Web search, page fetch, and safe URL opening.
- Local time, system snapshot, host details, math, JSON formatting, word counts.
- Explicit memory: remember only when the user clearly asks you to remember.
- Conversation help: summarize, explain, compare, draft, troubleshoot, and plan.

Real-time voice policy:
- Default answer length is one to three sentences.
- If the user asks for depth, give a concise structured explanation.
- Avoid markdown, bullet lists, and long enumerations in normal speech.
- If speech recognition looks garbled or self-contradictory, do not pretend.
  Say what you caught and ask for a quick repeat or confirmation.
- If the user corrects themselves, prioritize the latest correction.
- If the user interrupts, acknowledge the new request and continue from there.

Tool policy:
- Use tools for fresh/current facts, web/news/finance queries, system facts,
  calculations, memory operations, and opening URLs or dashboards.
- If a request is ambiguous, first classify it with the intent router, then
  choose the fastest safe path.
- Call tools silently. Do not say "I am calling a tool" or name the tool.
- Never invent real-time news, prices, search results, or system facts.
- For a world news brief, get the news first, summarize the top stories in
  three to five sentences, then open the world monitor unless the user says
  "just tell me", "do not open anything", or similar.
- For a finance or market brief, get finance news first, summarize only the
  market-moving items, then open the finance monitor unless the user opts out.
- If asked for exact live stock quotes and no quote tool exists, say you can
  check news/search context but not guarantee a real-time quote.

Safety and side effects:
- Ask for confirmation before destructive, irreversible, purchase, payment,
  email/message sending, credential, or file-deletion actions.
- Opening dashboards after explicit news/finance brief requests is allowed.
- For arbitrary links, open them only when the user asks to open/show/pull up
  the page, or after they confirm.
- Do not store secrets, passwords, tokens, or sensitive personal data in memory.

Failure handling:
- If a tool fails, say the capability is unavailable right now and offer the
  next best fallback. Keep it calm and short.
- If you are uncertain, say so directly. A precise "I do not have that yet" is
  better than a confident guess.

Style examples:
Right: "On it, boss. The main story is the market reacting to new inflation data; tech is carrying most of the move."
Wrong: "I will now retrieve current finance news using get_world_finance_news."
Right: "I caught 'open the monitor', but the rest came through rough. Say that last part once more?"
Wrong: "Sure, Franz then what has begun to go."
""".strip()
# ---------------------------------------------------------------------------
# Bootstrap
# ---------------------------------------------------------------------------

logger = logging.getLogger("friday-agent")
logger.setLevel(logging.INFO)


# ---------------------------------------------------------------------------
# Resolve Windows host IP from WSL
# ---------------------------------------------------------------------------

def _get_windows_host_ip() -> str:
    """Get the Windows host IP by looking at the default network route."""
    try:
        # 'ip route' is the most reliable way to find the 'default' gateway
        # which is always the Windows host in WSL.
        cmd = "ip route show default | awk '{print $3}'"
        result = subprocess.run(
            cmd, shell=True, capture_output=True, text=True, timeout=2
        )
        ip = result.stdout.strip()
        if ip:
            logger.info("Resolved Windows host IP via gateway: %s", ip)
            return ip
    except Exception as exc:
        logger.warning("Gateway resolution failed: %s. Trying fallback...", exc)

    # Fallback to your original resolv.conf logic if 'ip route' fails
    try:
        with open("/etc/resolv.conf", "r") as f:
            for line in f:
                if "nameserver" in line:
                    ip = line.split()[1]
                    logger.info("Resolved Windows host IP via nameserver: %s", ip)
                    return ip
    except Exception:
        pass

    return "127.0.0.1"

def _mcp_server_url() -> str:
    # host_ip = _get_windows_host_ip()
    # url = f"http://{host_ip}:{MCP_SERVER_PORT}/sse"
    # url = f"https://ongoing-colleague-samba-pioneer.trycloudflare.com/sse"
    url = f"http://127.0.0.1:{MCP_SERVER_PORT}/sse"
    logger.info("MCP Server URL: %s", url)
    return url


# ---------------------------------------------------------------------------
# Runtime telemetry and guard helpers
# ---------------------------------------------------------------------------

def _has_env(name: str) -> bool:
    return bool(os.getenv(name, "").strip())


def _resolve_provider(provider_type: str, requested: str) -> str:
    """Choose a provider, falling back only when the configured key is missing."""
    if not FRIDAY_ENABLE_PROVIDER_FALLBACKS:
        return requested

    if provider_type == "stt" and requested == "sarvam" and not _has_env("SARVAM_API_KEY"):
        if _has_env("OPENAI_API_KEY"):
            logger.warning("SARVAM_API_KEY missing; falling back STT to OpenAI Whisper")
            return "whisper"

    if provider_type == "llm" and requested == "openai" and not _has_env("OPENAI_API_KEY"):
        if _has_env("GOOGLE_API_KEY"):
            logger.warning("OPENAI_API_KEY missing; falling back LLM to Gemini")
            return "gemini"

    if provider_type == "llm" and requested == "gemini" and not _has_env("GOOGLE_API_KEY"):
        if _has_env("OPENAI_API_KEY"):
            logger.warning("GOOGLE_API_KEY missing; falling back LLM to OpenAI")
            return "openai"

    if provider_type == "tts" and requested == "openai" and not _has_env("OPENAI_API_KEY"):
        if _has_env("SARVAM_API_KEY"):
            logger.warning("OPENAI_API_KEY missing; falling back TTS to Sarvam")
            return "sarvam"

    if provider_type == "tts" and requested == "sarvam" and not _has_env("SARVAM_API_KEY"):
        if _has_env("OPENAI_API_KEY"):
            logger.warning("SARVAM_API_KEY missing; falling back TTS to OpenAI")
            return "openai"

    return requested


def _require_provider_key(provider_type: str, provider: str) -> None:
    required = {
        ("stt", "sarvam"): "SARVAM_API_KEY",
        ("stt", "whisper"): "OPENAI_API_KEY",
        ("llm", "openai"): "OPENAI_API_KEY",
        ("llm", "gemini"): "GOOGLE_API_KEY",
        ("tts", "openai"): "OPENAI_API_KEY",
        ("tts", "sarvam"): "SARVAM_API_KEY",
    }.get((provider_type, provider))

    if required and not _has_env(required):
        raise RuntimeError(
            f"{provider_type.upper()} provider '{provider}' requires {required}. "
            "Set it in .env or enable a configured fallback provider."
        )


def _json_safe(value: Any, *, max_text: int = 600) -> Any:
    if isinstance(value, (str, int, float, bool)) or value is None:
        if isinstance(value, str) and len(value) > max_text:
            return value[:max_text] + "..."
        return value
    if isinstance(value, dict):
        return {str(k): _json_safe(v, max_text=max_text) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item, max_text=max_text) for item in value[:20]]
    return _json_safe(str(value), max_text=max_text)


def _ms(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return round(float(value) * 1000, 1)
    except (TypeError, ValueError):
        return None


def _publish_debug(ctx: JobContext, event: str, data: dict[str, Any]) -> None:
    payload = {
        "type": "friday.telemetry",
        "event": event,
        "timestamp": int(time.time() * 1000),
        "data": _json_safe(data),
    }

    def _log_task_failure(task: asyncio.Task[None]) -> None:
        try:
            task.result()
        except Exception as exc:
            logger.debug("Debug telemetry publish failed: %s", exc)

    try:
        task = asyncio.create_task(
            ctx.room.local_participant.publish_data(
                json.dumps(payload, ensure_ascii=False),
                reliable=True,
                topic=FRIDAY_DEBUG_TOPIC,
            )
        )
        task.add_done_callback(_log_task_failure)
    except RuntimeError as exc:
        logger.debug("Debug telemetry publish skipped without a running loop: %s", exc)
    except Exception as exc:
        logger.debug("Debug telemetry publish failed: %s", exc)


def _extract_metrics_ms(metrics: dict[str, Any]) -> dict[str, float]:
    field_map = {
        "transcriptionDelayMs": "transcription_delay",
        "endOfTurnDelayMs": "end_of_turn_delay",
        "turnCallbackDelayMs": "on_user_turn_completed_delay",
        "llmFirstTokenMs": "llm_node_ttft",
        "ttsFirstAudioMs": "tts_node_ttfb",
        "e2eLatencyMs": "e2e_latency",
    }
    result: dict[str, float] = {}
    for output_key, input_key in field_map.items():
        converted = _ms(metrics.get(input_key))
        if converted is not None:
            result[output_key] = converted
    return result


def _message_text(item: Any) -> str:
    return getattr(item, "text_content", None) or ""


def _looks_like_bad_transcript(text: str) -> bool:
    normalized = re.sub(r"\s+", " ", text or "").strip()
    if not normalized:
        return True

    words = re.findall(r"[A-Za-z0-9']+", normalized)
    if len(words) <= 1 and len(normalized) < 8:
        return True

    letters = re.findall(r"[A-Za-z]", normalized)
    if letters:
        vowel_ratio = len(re.findall(r"[AEIOUaeiou]", normalized)) / max(len(letters), 1)
        if len(letters) > 8 and vowel_ratio < 0.18:
            return True

    short_tokens = [word for word in words if len(word) <= 2]
    if len(words) >= 5 and len(short_tokens) / len(words) > 0.65:
        return True

    unknown_long_words = [
        word for word in words
        if len(word) >= 5 and word.lower() not in COMMON_TRANSCRIPT_WORDS
    ]
    intent_words = {
        "what", "how", "who", "why", "when", "where", "open", "search", "show",
        "tell", "make", "summarize", "calculate", "remember", "forget", "check",
        "explain", "compare",
    }
    if len(words) <= 4 and unknown_long_words and not (set(word.lower() for word in words) & intent_words):
        return True

    if len(words) <= 3 and any(
        len(word) >= 3
        and word.upper() not in COMMON_TRANSCRIPT_ACRONYMS
        and not re.search(r"[aeiouAEIOU]", word)
        for word in words
    ):
        return True

    return False


def _attach_session_observers(ctx: JobContext, session: AgentSession) -> None:
    session.on(
        "user_state_changed",
        lambda ev: _publish_debug(
            ctx,
            "user_state_changed",
            {"oldState": ev.old_state, "newState": ev.new_state},
        ),
    )
    session.on(
        "agent_state_changed",
        lambda ev: _publish_debug(
            ctx,
            "agent_state_changed",
            {"oldState": ev.old_state, "newState": ev.new_state},
        ),
    )
    session.on(
        "user_input_transcribed",
        lambda ev: _publish_debug(
            ctx,
            "user_input_transcribed",
            {
                "transcript": ev.transcript,
                "isFinal": ev.is_final,
                "speakerId": ev.speaker_id,
                "language": str(ev.language) if ev.language else None,
            },
        ),
    )
    session.on(
        "conversation_item_added",
        lambda ev: _publish_conversation_event(ctx, ev.item),
    )
    session.on(
        "function_tools_executed",
        lambda ev: _publish_debug(
            ctx,
            "function_tools_executed",
            {
                "tools": [
                    {
                        "name": getattr(call, "name", "unknown"),
                        "callId": getattr(call, "call_id", None),
                        "hasOutput": output is not None,
                        "output": getattr(output, "output", None) if output is not None else None,
                    }
                    for call, output in ev.zipped()
                ],
            },
        ),
    )
    session.on(
        "agent_false_interruption",
        lambda ev: _publish_debug(ctx, "agent_false_interruption", {"resumed": ev.resumed}),
    )
    session.on(
        "overlapping_speech",
        lambda ev: _publish_debug(
            ctx,
            "overlapping_speech",
            {
                "isInterruption": ev.is_interruption,
                "totalDurationMs": _ms(ev.total_duration),
                "detectionDelayMs": _ms(ev.detection_delay),
                "probability": round(float(ev.probability), 3),
            },
        ),
    )
    session.on(
        "speech_created",
        lambda ev: _publish_debug(
            ctx,
            "speech_created",
            {"source": ev.source, "userInitiated": ev.user_initiated},
        ),
    )
    session.on(
        "error",
        lambda ev: _publish_debug(
            ctx,
            "error",
            {
                "source": type(ev.source).__name__,
                "error": str(ev.error),
            },
        ),
    )


def _publish_conversation_event(ctx: JobContext, item: Any) -> None:
    role = getattr(item, "role", None)
    text = _message_text(item)
    metrics = _extract_metrics_ms(dict(getattr(item, "metrics", {}) or {}))
    _publish_debug(
        ctx,
        "conversation_item_added",
        {
            "role": role,
            "text": text,
            "interrupted": getattr(item, "interrupted", False),
            "metrics": metrics,
        },
    )
    if metrics:
        _publish_debug(ctx, "latency_updated", {"role": role, "metrics": metrics})


# ---------------------------------------------------------------------------
# Build provider instances
# ---------------------------------------------------------------------------

def _build_stt():
    provider = _resolve_provider("stt", STT_PROVIDER)
    _require_provider_key("stt", provider)
    if provider == "sarvam":
        logger.info("STT -> Sarvam %s", SARVAM_STT_MODEL)
        return sarvam.STT(
            language=SARVAM_STT_LANGUAGE,
            model=SARVAM_STT_MODEL,
            mode="transcribe",
            flush_signal=True,
            high_vad_sensitivity=True,
            prompt=SARVAM_STT_PROMPT,
            sample_rate=16000,
        )
    elif provider == "whisper":
        logger.info("STT -> OpenAI Whisper")
        return lk_openai.STT(model="whisper-1")
    else:
        raise ValueError(f"Unknown STT_PROVIDER: {provider!r}")


def _build_llm():
    provider = _resolve_provider("llm", LLM_PROVIDER)
    _require_provider_key("llm", provider)
    if provider == "openai":
        logger.info("LLM -> OpenAI (%s)", OPENAI_LLM_MODEL)
        return lk_openai.LLM(
            model=OPENAI_LLM_MODEL,
            temperature=OPENAI_LLM_TEMPERATURE,
            max_completion_tokens=OPENAI_LLM_MAX_TOKENS,
            parallel_tool_calls=True,
        )
    elif provider == "gemini":
        logger.info("LLM -> Google Gemini (%s)", GEMINI_LLM_MODEL)
        return lk_google.LLM(model=GEMINI_LLM_MODEL, api_key=os.getenv("GOOGLE_API_KEY"))
    else:
        raise ValueError(f"Unknown LLM_PROVIDER: {provider!r}")


def _build_tts():
    provider = _resolve_provider("tts", TTS_PROVIDER)
    _require_provider_key("tts", provider)
    if provider == "sarvam":
        logger.info("TTS -> Sarvam Bulbul v3")
        return sarvam.TTS(
            target_language_code=SARVAM_TTS_LANGUAGE,
            model="bulbul:v3",
            speaker=SARVAM_TTS_SPEAKER,
            pace=TTS_SPEED,
        )
    elif provider == "openai":
        logger.info("TTS -> OpenAI TTS (%s / %s)", OPENAI_TTS_MODEL, OPENAI_TTS_VOICE)
        kwargs = {
            "model": OPENAI_TTS_MODEL,
            "voice": OPENAI_TTS_VOICE,
            "speed": TTS_SPEED,
        }
        if "gpt-4o" in OPENAI_TTS_MODEL:
            kwargs["instructions"] = (
                "Speak as F.R.I.D.A.Y.: calm, quick, lightly dry, and concise. "
                "Prioritize intelligibility over drama."
            )
        return lk_openai.TTS(**kwargs)
    else:
        raise ValueError(f"Unknown TTS_PROVIDER: {provider!r}")


# ---------------------------------------------------------------------------
# Agent
# ---------------------------------------------------------------------------

class FridayAgent(Agent):
    """
    F.R.I.D.A.Y. – Iron Man-style voice assistant.
    All tools are provided via the MCP server on the Windows host.
    """

    def __init__(self, stt, llm, tts) -> None:
        super().__init__(
            instructions=SYSTEM_PROMPT,
            stt=stt,
            llm=llm,
            tts=tts,
            vad=silero.VAD.load(),
            mcp_servers=[
                mcp.MCPServerHTTP(
                    url=_mcp_server_url(),
                    transport_type="sse",
                    client_session_timeout_seconds=30,
                ),
            ],
        )

    async def on_user_turn_completed(self, turn_ctx, new_message) -> None:
        """Guard against low-quality STT before the LLM answers."""
        transcript = _message_text(new_message)
        if not _looks_like_bad_transcript(transcript):
            return

        new_message.extra["friday_quality_guard"] = "low_confidence_transcript"
        try:
            publisher = self.session.userdata.get("publish_debug")
            if publisher:
                publisher("quality_guard", {"reason": "low_confidence_transcript", "transcript": transcript})
        except Exception:
            logger.debug("Unable to publish transcript quality guard event", exc_info=True)
        turn_ctx.add_message(
            role="developer",
            content=(
                "The latest user transcript is likely incomplete or inaccurate. "
                f"Transcript: {transcript!r}. Do not answer the apparent request. "
                "Ask the user to repeat or confirm it in one short spoken sentence."
            ),
        )

    async def on_enter(self) -> None:
        """Greet the user based on the current time of day."""
        from datetime import datetime
        hour = datetime.now().hour

        if hour >= 22 or hour < 4:
            greeting_instruction = (
                "Greet the user with: 'Greetings boss, you're up late at night today. What are you up to?' "
                "Maintain a helpful but dry tone."
            )
        elif 4 <= hour < 12:
            greeting_instruction = (
                "Greet the user with: 'Good morning, boss. Early start today — what are we working on?' "
                "Maintain a helpful but dry tone."
            )
        elif 12 <= hour < 17:
            greeting_instruction = (
                "Greet the user with: 'Good afternoon, boss. What do you need?' "
                "Maintain a helpful but dry tone."
            )
        else:  # 17–21
            greeting_instruction = (
                "Greet the user with: 'Good evening, boss. What are you up to tonight?' "
                "Maintain a helpful but dry tone."
            )

        await self.session.generate_reply(instructions=greeting_instruction)


# ---------------------------------------------------------------------------
# LiveKit entry point
# ---------------------------------------------------------------------------

def _turn_detection() -> str:
    return "stt" if STT_PROVIDER == "sarvam" else "vad"


def _endpointing_delay() -> float:
    if FRIDAY_MIN_ENDPOINTING_DELAY >= 0:
        return FRIDAY_MIN_ENDPOINTING_DELAY
    return {"sarvam": 0.07, "whisper": 0.3}.get(STT_PROVIDER, 0.1)


async def entrypoint(ctx: JobContext) -> None:
    logger.info(
        "FRIDAY online – room: %s | mode=%s | STT=%s | LLM=%s | TTS=%s",
        ctx.room.name, FRIDAY_MODE, STT_PROVIDER, LLM_PROVIDER, TTS_PROVIDER,
    )

    stt = _build_stt()
    llm = _build_llm()
    tts = _build_tts()

    session = AgentSession(
        turn_detection=_turn_detection(),
        min_endpointing_delay=_endpointing_delay(),
        max_endpointing_delay=FRIDAY_MAX_ENDPOINTING_DELAY,
        allow_interruptions=True,
        resume_false_interruption=True,
        min_interruption_duration=FRIDAY_MIN_INTERRUPTION_DURATION,
        min_interruption_words=FRIDAY_MIN_INTERRUPTION_WORDS,
        max_tool_steps=FRIDAY_MAX_TOOL_STEPS,
        preemptive_generation=True,
        use_tts_aligned_transcript=True,
        userdata={"publish_debug": lambda event, data: _publish_debug(ctx, event, data)},
    )
    _attach_session_observers(ctx, session)
    _publish_debug(
        ctx,
        "session_config",
        {
            "mode": FRIDAY_MODE,
            "sttProvider": STT_PROVIDER,
            "llmProvider": LLM_PROVIDER,
            "ttsProvider": TTS_PROVIDER,
            "maxEndpointingDelayMs": _ms(FRIDAY_MAX_ENDPOINTING_DELAY),
            "minInterruptionDurationMs": _ms(FRIDAY_MIN_INTERRUPTION_DURATION),
            "maxToolSteps": FRIDAY_MAX_TOOL_STEPS,
        },
    )

    await session.start(
        agent=FridayAgent(stt=stt, llm=llm, tts=tts),
        room=ctx.room,
    )


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    cli.run_app(WorkerOptions(entrypoint_fnc=entrypoint, agent_name=FRIDAY_AGENT_NAME))

def dev():
    """Wrapper to run the agent in dev mode automatically."""
    import sys
    # If no command was provided, inject 'dev'
    if len(sys.argv) == 1:
        sys.argv.append("dev")
    main()

if __name__ == "__main__":
    main()
