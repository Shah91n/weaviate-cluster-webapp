import io
import contextlib
import re
import logging
from typing import List, Optional, Any
from core.connection.weaviate_connection_manager import get_weaviate_client

logger = logging.getLogger(__name__)

# Utilities for working with the QueryAgent (installed via weaviate-client[agents]).
# Provides: run_query_agent(), render_response() and helpers for formatting output.

def run_query_agent(collections: List[str], question: str, system_prompt: Optional[str] = None,
                    agents_host: Optional[str] = None, timeout: Optional[int] = 60):
    """Run a QueryAgent ask() call and return the response object.

    Parameters
    ----------
    collections : list[str]
        Collections to include in the query.
    question : str
        Natural language question to ask the agent.
    system_prompt : str | None
        Optional system prompt to influence agent behavior.
    agents_host : str | None
        Optional override for agents service host.
    timeout : int | None
        Request timeout in seconds.
    """
    logger.info(f"run_query_agent() called with collections: {collections}")
    try:
        from weaviate.agents.query import QueryAgent  # type: ignore
    except ImportError:
        logger.error("weaviate-client[agents] extra is not installed")
        raise RuntimeError("weaviate-client[agents] extra is not installed. Please install requirements.")

    client = get_weaviate_client()
    agent = QueryAgent(
        client=client,
        collections=collections,
        system_prompt=system_prompt if system_prompt else None,
        agents_host=agents_host if agents_host else None,
        timeout=timeout if timeout else None,
    )
    return agent.ask(question)


ANSI_PATTERN = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")
BOX_LINE_PATTERN = re.compile(r"^[\s\u2500-\u257F\x1b\[0-9;A-Za-z]+$")  # heuristic for decorative lines

def strip_ansi(text: str) -> str:
    return ANSI_PATTERN.sub("", text)

def capture_display(response: Any) -> str:
    """Capture the display() output; if missing, fall back to repr.
    We later sanitize ANSI escape sequences and remove most box drawing fluff.
    """
    buf = io.StringIO()
    try:
        with contextlib.redirect_stdout(buf):
            response.display()  # type: ignore[attr-defined]
        raw = buf.getvalue()
        return raw if raw.strip() else "(display() produced no output)"
    except Exception as e:
        return f"Unable to capture display(): {e}\nRaw: {repr(response)}"

def sanitize_display(raw: str) -> str:
    # 1. Remove ANSI color codes
    cleaned = strip_ansi(raw)
    # 2. Split lines and drop decorative box lines / empty padding lines
    lines = [ln.rstrip() for ln in cleaned.splitlines()]
    meaningful = []
    for ln in lines:
        stripped = ln.strip()
        if not stripped:
            continue
        # Heuristic: drop lines mostly composed of box drawing or framing artifacts
        if BOX_LINE_PATTERN.match(ln) and ('Ask Mode Response' not in ln):
            continue
        meaningful.append(stripped)
    # 3. Collapse multiple spaces
    normalized = [re.sub(r"\s+", " ", ln) for ln in meaningful]
    return "\n".join(normalized)


def extract_known_fields(response: Any) -> dict:
    """Attempt to extract common fields from AskModeResponse for structured rendering."""
    field_names = [
        "answer", "query", "collections", "generations", "contexts", "timing", "usage"
    ]
    data = {}
    for name in field_names:
        if hasattr(response, name):
            try:
                data[name] = getattr(response, name)
            except Exception:
                pass
    return data

