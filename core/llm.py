"""Minimal LLM client. Provider-agnostic JSON-mode helper."""
from __future__ import annotations
import os, json, re
from typing import Any
import httpx
from dotenv import load_dotenv

load_dotenv()

PROVIDER = os.getenv("LLM_PROVIDER", "openai").lower()
OPENAI_KEY = os.getenv("OPENAI_API_KEY", "")
ANTHROPIC_KEY = os.getenv("ANTHROPIC_API_KEY", "")
FAST_MODEL = os.getenv("LLM_FAST_MODEL", "gpt-4o-mini" if PROVIDER == "openai" else "claude-haiku-4-5-20251001")
PLAN_MODEL = os.getenv("LLM_PLAN_MODEL", "gpt-4o" if PROVIDER == "openai" else "claude-sonnet-4-6")

_FENCE = re.compile(r"^```(?:json)?\s*|\s*```$", re.MULTILINE)


def _strip_fences(s: str) -> str:
    return _FENCE.sub("", s).strip()


async def chat_json(system: str, user: str, *, model: str | None = None) -> dict[str, Any]:
    model = model or FAST_MODEL
    if PROVIDER == "anthropic":
        return await _anthropic(system, user, model)
    return await _openai(system, user, model)


async def _openai(system: str, user: str, model: str) -> dict[str, Any]:
    if not OPENAI_KEY:
        raise RuntimeError("OPENAI_API_KEY not set")
    async with httpx.AsyncClient(timeout=180.0) as client:
        r = await client.post(
            "https://api.openai.com/v1/chat/completions",
            headers={"Authorization": f"Bearer {OPENAI_KEY}"},
            json={
                "model": model,
                "response_format": {"type": "json_object"},
                "temperature": 0.2,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
            },
        )
        r.raise_for_status()
        return json.loads(r.json()["choices"][0]["message"]["content"])


async def _anthropic(system: str, user: str, model: str) -> dict[str, Any]:
    if not ANTHROPIC_KEY:
        raise RuntimeError("ANTHROPIC_API_KEY not set")
    sys = system + "\n\nReturn ONLY valid JSON. No prose, no markdown fences."
    async with httpx.AsyncClient(timeout=180.0) as client:
        r = await client.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": ANTHROPIC_KEY,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            json={
                "model": model,
                "system": sys,
                "max_tokens": 4096,
                "messages": [{"role": "user", "content": user}],
            },
        )
        r.raise_for_status()
        return json.loads(_strip_fences(r.json()["content"][0]["text"]))
