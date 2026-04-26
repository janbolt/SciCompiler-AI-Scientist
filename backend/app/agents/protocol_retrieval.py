"""Agent 3 of 11 — Protocol Retrieval Agent.

Searches protocols.io for existing lab procedures relevant to the hypothesis,
then uses an LLM to score each candidate's fitness. For the top-scoring
candidates, fetches the full protocol detail (GET /protocols/{id}) to extract
the actual step-by-step text, which is passed to the plan agent as a concrete
procedural skeleton.

Two execution modes:
- USE_STUB_AGENTS=true  → deterministic stub output, no network.
- PROTOCOLS_IO_TOKEN set → live: search → score → fetch full steps.
- PROTOCOLS_IO_TOKEN missing → degrades to stub, logs warning.
"""

from __future__ import annotations

import logging
import os
import re
from datetime import datetime, timezone
from typing import Any, Literal

import requests
from pydantic import BaseModel, Field

from app.schemas import ProtocolCandidate, StructuredHypothesis
from app.services.llm import LLM_MAX_RETRIES, LLM_MODEL, USE_STUB_AGENTS, get_client

logger = logging.getLogger(__name__)


PROTOCOLS_IO_BASE_URL = "https://www.protocols.io/api/v3"
PROTOCOLS_IO_TIMEOUT_SECONDS = 10
MAX_CANDIDATES = 5
MAX_DETAIL_FETCH = 2      # how many candidates get full step detail fetched
MAX_STEPS_PER_PROTOCOL = 20   # cap steps sent to the plan LLM


# ---------------------------------------------------------------------------
# LLM fit assessment schema
# ---------------------------------------------------------------------------


class _ProtocolFitLLMOutput(BaseModel):
    fit_score: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description=(
            "How well this protocol fits the hypothesis as a starting procedure. "
            "1.0 = exact match, 0.0 = completely unrelated."
        ),
    )
    confidence: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Confidence in the fit_score assessment.",
    )
    adaptation_notes: str = Field(
        ...,
        description=(
            "Concrete notes on what would need to be adapted or changed to use "
            "this protocol for the stated hypothesis. Be specific."
        ),
    )
    missing_steps: list[str] = Field(
        default_factory=list,
        description="Steps the protocol lacks that the hypothesis requires.",
    )
    limitations: list[str] = Field(
        default_factory=list,
        description="Known limitations of this protocol for the stated hypothesis.",
    )


FIT_SYSTEM_PROMPT = """\
You are a senior wet-lab scientist evaluating whether an existing lab protocol
from protocols.io is a suitable starting point for a new experiment.

You will receive:
1. A structured hypothesis describing the planned experiment.
2. A single protocol with its title and description/abstract.

Assess how well this protocol serves as a procedural starting point for the
hypothesis. Score fit_score from 0.0 to 1.0:
  1.0 = the protocol covers the core experimental procedure exactly
  0.7-0.9 = the protocol is closely related and needs minor adaptation
  0.4-0.6 = the protocol covers related techniques but needs significant adaptation
  0.1-0.3 = the protocol is only tangentially related
  0.0 = the protocol is unrelated

Be concrete in adaptation_notes — list specific changes needed (e.g.,
"replace sucrose with trehalose at equimolar concentration", not "adjust conditions").
"""


# ---------------------------------------------------------------------------
# protocols.io client
# ---------------------------------------------------------------------------


def _get_protocols_io_token() -> str:
    token = os.getenv("PROTOCOLS_IO_TOKEN", "").strip()
    if not token or token == "your_token_here":
        raise EnvironmentError(
            "PROTOCOLS_IO_TOKEN is not set. Add it to backend/.env."
        )
    return token


def _search_protocols(query: str, token: str) -> list[dict[str, Any]]:
    """Call protocols.io search for one query. Returns raw protocol dicts or []."""
    query = (query or "").strip()
    if not query:
        return []

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }
    base_url = f"{PROTOCOLS_IO_BASE_URL}/protocols"

    param_candidates: list[dict[str, Any]] = [
        {"key": query, "filter": "public", "order_field": "relevance", "order_dir": "desc", "page_size": 10},
        {"key": query, "filter": "public", "order_field": "published_on", "order_dir": "desc", "page_size": 10},
        {"key": query, "filter": "public", "page_size": 10},
        {"q": query, "filter": "public", "order_field": "published_on", "order_dir": "desc", "page_size": 10},
    ]

    for params in param_candidates:
        try:
            response = requests.get(
                base_url, headers=headers, params=params,
                timeout=PROTOCOLS_IO_TIMEOUT_SECONDS,
            )
        except requests.RequestException as exc:
            logger.warning("protocols.io request failed for query %r: %s", query, exc)
            return []

        if response.status_code >= 400:
            continue

        try:
            payload = response.json()
        except ValueError:
            continue

        items = payload.get("items") if isinstance(payload, dict) else None
        if isinstance(items, list) and items:
            return [item for item in items if isinstance(item, dict) and item.get("id")]

    return []


def _strip_html(text: str) -> str:
    """Remove HTML tags and normalise whitespace."""
    if not text:
        return ""
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"&nbsp;", " ", text)
    text = re.sub(r"&amp;", "&", text)
    text = re.sub(r"&lt;", "<", text)
    text = re.sub(r"&gt;", ">", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _fetch_protocol_steps(protocol_id: Any, token: str) -> tuple[list[str], str]:
    """Fetch full protocol detail from protocols.io and extract step texts.

    Returns (steps, protocol_url) where steps is a list of clean text strings
    and protocol_url is the public URI (empty string on failure).
    """
    try:
        url = f"{PROTOCOLS_IO_BASE_URL}/protocols/{protocol_id}"
        response = requests.get(
            url,
            headers={"Authorization": f"Bearer {token}"},
            timeout=PROTOCOLS_IO_TIMEOUT_SECONDS,
        )
        if response.status_code >= 400:
            logger.warning("protocols.io detail fetch HTTP %s for id=%s", response.status_code, protocol_id)
            return [], ""

        payload = response.json()
        protocol = payload.get("protocol") or payload  # v3 wraps in {"protocol": {...}}

        # Extract public URL
        protocol_url = str(protocol.get("uri") or protocol.get("url") or "")

        # Extract steps — v3 API returns steps as a list of step objects
        steps_raw = protocol.get("steps") or []
        result: list[str] = []

        for step in steps_raw:
            if not isinstance(step, dict):
                continue

            # Step description may live in several fields depending on step type
            desc = (
                step.get("description")
                or step.get("title")
                or ""
            )

            # Some step types nest content in 'components'
            if not desc:
                for comp in (step.get("components") or []):
                    if isinstance(comp, dict):
                        comp_text = comp.get("source", {})
                        if isinstance(comp_text, dict):
                            desc = comp_text.get("title") or comp_text.get("body") or ""
                        elif isinstance(comp_text, str):
                            desc = comp_text
                        if desc:
                            break

            desc = _strip_html(str(desc))
            if desc:
                result.append(desc[:400])

        return result[:MAX_STEPS_PER_PROTOCOL], protocol_url

    except Exception as exc:  # noqa: BLE001
        logger.warning("Protocol detail fetch failed for id=%s: %s", protocol_id, exc)
        return [], ""


def _published_year(protocol: dict[str, Any]) -> int | None:
    ts = protocol.get("published_on")
    if not isinstance(ts, (int, float)) or ts <= 0:
        return None
    try:
        return datetime.fromtimestamp(float(ts), tz=timezone.utc).year
    except (OSError, OverflowError, ValueError):
        return None


def _protocol_abstract(protocol: dict[str, Any]) -> str:
    text = protocol.get("description") or protocol.get("abstract") or ""
    if not isinstance(text, str):
        return "No description available."
    text = _strip_html(text)
    if len(text) > 500:
        text = text[:500] + "..."
    return text or "No description available."


# ---------------------------------------------------------------------------
# LLM fit assessment
# ---------------------------------------------------------------------------


def _assess_fit(
    hypothesis: StructuredHypothesis,
    protocol: dict[str, Any],
) -> _ProtocolFitLLMOutput:
    client = get_client()
    title = str(protocol.get("title") or "Untitled protocol")
    abstract = _protocol_abstract(protocol)

    user_message = (
        "HYPOTHESIS\n"
        f"- intervention: {hypothesis.intervention}\n"
        f"- biological_system: {hypothesis.biological_system}\n"
        f"- comparator_or_control: {hypothesis.comparator_or_control}\n"
        f"- measurable_outcome: {hypothesis.measurable_outcome}\n"
        f"- experiment_type: {hypothesis.experiment_type}\n\n"
        "PROTOCOL\n"
        f"Title: {title}\n"
        f"Description: {abstract}\n\n"
        "Assess the fit of this protocol as a procedural starting point."
    )

    return client.chat.completions.create(
        model=LLM_MODEL,
        response_model=_ProtocolFitLLMOutput,
        max_retries=LLM_MAX_RETRIES,
        temperature=1,
        messages=[
            {"role": "system", "content": FIT_SYSTEM_PROMPT},
            {"role": "user", "content": user_message},
        ],
    )


# ---------------------------------------------------------------------------
# Deduplication
# ---------------------------------------------------------------------------


def _dedupe_protocols(protocols: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[Any] = set()
    result: list[dict[str, Any]] = []
    for p in protocols:
        pid = p.get("id")
        if pid is None or pid in seen:
            continue
        seen.add(pid)
        result.append(p)
    return result


# ---------------------------------------------------------------------------
# Stub output
# ---------------------------------------------------------------------------


def _stub_protocol_retrieval(hypothesis: StructuredHypothesis) -> list[ProtocolCandidate]:
    intervention = (hypothesis.intervention or "").lower()
    exp_type = (hypothesis.experiment_type or "").lower()
    return [
        ProtocolCandidate(
            protocol_name=f"Standard {exp_type or 'laboratory'} protocol for {intervention or 'the intervention'}",
            source_type="stub",
            fit_score=0.75,
            confidence=0.65,
            adaptation_notes="Stub mode — no live protocols.io search performed. This is a placeholder candidate.",
            missing_steps=["Exact reagent concentrations", "Instrument-specific settings"],
            limitations=["Stub output only — real protocols.io search requires PROTOCOLS_IO_TOKEN."],
            raw_steps=[],
            protocol_url="",
        ),
    ]


# ---------------------------------------------------------------------------
# Main entrypoint
# ---------------------------------------------------------------------------


def run(hypothesis: StructuredHypothesis) -> list[ProtocolCandidate]:
    """Retrieve and assess protocol candidates for the given hypothesis.

    Runs three search queries:
      - literature_search_hint (full scope)
      - experiment_type (technique-level procedure)
      - intervention (organism/compound-level procedure — NEW)

    Top-scoring candidates have their full step text fetched from the
    protocols.io detail endpoint and stored in ProtocolCandidate.raw_steps.

    Returns up to MAX_CANDIDATES ProtocolCandidate objects ordered by fit_score.
    Degrades gracefully to stub if token is missing or API fails.
    """
    if USE_STUB_AGENTS:
        return _stub_protocol_retrieval(hypothesis)

    try:
        token = _get_protocols_io_token()
    except EnvironmentError as exc:
        logger.warning("Protocol Retrieval falling back to stub: %s", exc)
        return _stub_protocol_retrieval(hypothesis)

    try:
        # Three searches: full scope, technique class, and intervention/organism
        query_a = (hypothesis.literature_search_hint or "").strip()
        query_b = (hypothesis.experiment_type or "").strip().replace("_", " ")
        query_c = (hypothesis.intervention or "").strip()
        if len(query_c) > 80:
            # Trim to first 80 chars at a word boundary for cleaner search
            query_c = query_c[:80].rsplit(" ", 1)[0]

        raw_a = _search_protocols(query_a, token) if query_a else []
        raw_b = _search_protocols(query_b, token) if query_b else []
        raw_c = _search_protocols(query_c, token) if query_c else []

        all_raw = _dedupe_protocols(raw_a + raw_b + raw_c)

        if not all_raw:
            logger.info("protocols.io returned no results — falling back to stub.")
            return _stub_protocol_retrieval(hypothesis)

        # Score top candidates with LLM
        candidates: list[ProtocolCandidate] = []
        for protocol in all_raw[:MAX_CANDIDATES]:
            try:
                fit = _assess_fit(hypothesis, protocol)
                candidates.append(
                    ProtocolCandidate(
                        protocol_name=str(protocol.get("title") or "Untitled protocol"),
                        source_type="protocols_io",
                        fit_score=fit.fit_score,
                        confidence=fit.confidence,
                        adaptation_notes=fit.adaptation_notes,
                        missing_steps=fit.missing_steps,
                        limitations=fit.limitations,
                        raw_steps=[],
                        protocol_url="",
                    )
                )
            except Exception as exc:  # noqa: BLE001
                logger.warning("LLM fit assessment failed for protocol %r: %s", protocol.get("id"), exc)
                candidates.append(
                    ProtocolCandidate(
                        protocol_name=str(protocol.get("title") or "Untitled protocol"),
                        source_type="protocols_io",
                        fit_score=0.5,
                        confidence=0.3,
                        adaptation_notes="LLM fit assessment failed — manual review required.",
                        missing_steps=[],
                        limitations=["Automated fit assessment unavailable."],
                        raw_steps=[],
                        protocol_url="",
                    )
                )

        candidates.sort(key=lambda c: c.fit_score, reverse=True)

        # Fetch full step content for the top-scoring candidates
        # We zip with the original raw dicts to get the protocol ID
        id_map: dict[str, Any] = {
            str(p.get("title") or ""): p.get("id")
            for p in all_raw
        }

        enriched = 0
        for candidate in candidates:
            if enriched >= MAX_DETAIL_FETCH:
                break
            pid = id_map.get(candidate.protocol_name)
            if not pid:
                continue
            steps, url = _fetch_protocol_steps(pid, token)
            if steps:
                candidate.raw_steps = steps
                candidate.protocol_url = url
                logger.info(
                    "Fetched %d steps for candidate %r", len(steps), candidate.protocol_name
                )
            enriched += 1

        return candidates or _stub_protocol_retrieval(hypothesis)

    except Exception as exc:  # noqa: BLE001
        logger.exception("Protocol Retrieval pipeline failed: %s", exc)
        return _stub_protocol_retrieval(hypothesis)
