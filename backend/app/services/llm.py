"""Shared LLM client used by every agent in the pipeline.

Design goals:
- Single instructor-wrapped OpenAI client, lazily built on first use.
- Schema-enforced structured outputs via ``instructor.Mode.TOOLS`` (function
  calling). ``Mode.JSON`` only requests JSON text and does NOT enforce the
  Pydantic schema at the API level, so we deliberately avoid it.
- Test-isolatable: ``reset_client()`` clears the cached client so tests can
  swap env vars between runs.
- Offline-safe: when ``USE_STUB_AGENTS=true`` the agents skip this module
  entirely, which means CI does not need any API key.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

logger = logging.getLogger(__name__)

BACKEND_DIR = Path(__file__).resolve().parents[2]
load_dotenv(BACKEND_DIR / ".env")


def _env_bool(name: str, default: str) -> bool:
    return os.environ.get(name, default).strip().lower() in {"1", "true", "yes", "on"}


LLM_MODEL: str = os.environ.get("LLM_MODEL", "gpt-4o-mini")
LLM_MAX_RETRIES: int = int(os.environ.get("LLM_MAX_RETRIES", "3"))
USE_STUB_AGENTS: bool = _env_bool("USE_STUB_AGENTS", "false")

_client: Any = None


def _get_api_key() -> str:
    key = os.environ.get("OPENAI_API_KEY", "").strip()
    if not key or "YOUR_KEY_HERE" in key:
        raise EnvironmentError(
            "OPENAI_API_KEY is missing or still set to the placeholder value. "
            "Copy backend/.env.example to backend/.env and set a real key, or "
            "set USE_STUB_AGENTS=true to run the pipeline in offline stub mode."
        )
    return key


def _build_client() -> Any:
    import httpx
    import instructor
    from openai import OpenAI

    key = _get_api_key()
    # Bypass shell-level proxy variables by default so local dev/pytest
    # are not blocked by corporate proxy 403 tunnel responses.
    http_client = httpx.Client(trust_env=False)
    raw_client = OpenAI(api_key=key, http_client=http_client)
    logger.info(
        "LLM client initialised | model=%s | key_prefix=%s | key_tail=%s | stub_mode=%s",
        LLM_MODEL,
        key[:8],
        key[-6:],
        USE_STUB_AGENTS,
    )
    return instructor.from_openai(raw_client, mode=instructor.Mode.TOOLS)


def get_client() -> Any:
    """Return the cached instructor-wrapped OpenAI client, building it lazily."""
    global _client
    if _client is None:
        _client = _build_client()
    return _client


def reset_client() -> None:
    """Drop the cached client. Required for test isolation between env changes."""
    global _client
    _client = None


__all__ = [
    "get_client",
    "reset_client",
    "LLM_MODEL",
    "LLM_MAX_RETRIES",
    "USE_STUB_AGENTS",
]
