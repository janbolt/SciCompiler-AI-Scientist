"""Agent 2 of 11 — Literature QC Agent.

Determines whether the same or a similar experiment already exists in the
protocols.io public protocol database. Three queries are issued sequentially
(full_scope / intervention_only / system_method), the union is deduplicated
by protocol id, and an LLM classifies the novelty signal across three
similarity dimensions (intervention, biological system, experiment type).

Python — not the LLM — owns:
    * confidence_score  (deterministic scoring matrix)
    * recommended_action (deterministic lookup)
    * search_coverage   (computed from query result counts)

The LLM owns:
    * novelty_signal     (not_found | similar_work_exists | exact_match_found)
    * explanation        (2–3 sentences, dimension-by-dimension)
    * confidence_reasoning (used as a soft input into the score)
    * top_reference_indices + relevance_notes (which protocols to surface)

Two execution modes:

- ``USE_STUB_AGENTS=true``  → ``_stub_literature_qc`` returns deterministic
  output without contacting any external API.
- Otherwise                 → live mode: protocols.io REST + OpenAI via the
  shared instructor client (``Mode.TOOLS``).
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from typing import Any, Literal

import requests
from pydantic import BaseModel, Field

from app.schemas import (
    MISSING,
    LiteratureQCResult,
    ProtocolReference,
    StructuredHypothesis,
)
from app.services.llm import LLM_MAX_RETRIES, LLM_MODEL, USE_STUB_AGENTS, get_client

logger = logging.getLogger(__name__)


PROTOCOLS_IO_BASE_URL = "https://www.protocols.io/api/v3"
PROTOCOLS_IO_TIMEOUT_SECONDS = 10
MAX_UNIQUE_PROTOCOLS = 8
MAX_PROTOCOLS_FOR_LLM = 5
MAX_REFERENCES_RETURNED = 3


# ---------------------------------------------------------------------------
# LLM extraction model — only fields the LLM is allowed to fill in.
# ---------------------------------------------------------------------------


class _LiteratureQCLLMOutput(BaseModel):
    novelty_signal: Literal["not_found", "similar_work_exists", "exact_match_found"] = Field(
        ...,
        description=(
            "Classify the novelty of the hypothesis against the retrieved protocols. "
            "Use 'exact_match_found' only when at least one protocol covers BOTH the "
            "same/equivalent intervention AND the same/similar biological system. "
            "Use 'similar_work_exists' when there is meaningful prior art (same "
            "intervention on a related system, same compound class on the same "
            "system, or same experiment type with different intervention purpose). "
            "Use 'not_found' when retrieved protocols are only peripherally related, "
            "or when no protocols were retrieved."
        ),
    )
    explanation: str = Field(
        ...,
        description=(
            "2–3 sentences justifying the novelty_signal. Reason explicitly across "
            "three dimensions: (1) intervention, (2) biological system, (3) "
            "experiment type / assay. Reference protocols by their bracketed index "
            "when relevant."
        ),
    )
    confidence_reasoning: str = Field(
        ...,
        description=(
            "1–2 sentences describing how certain you are. Use honest hedge words "
            "such as 'unclear', 'tangential', 'limited', 'cannot confirm', 'may be' "
            "when warranted; do not just paraphrase the novelty_signal."
        ),
    )
    top_reference_indices: list[int] = Field(
        default_factory=list,
        description=(
            "0-based indices into the protocol list provided in the user message, "
            "for the most relevant protocols. Maximum 3 indices. Empty list if no "
            "protocol is relevant."
        ),
    )
    relevance_notes: list[str] = Field(
        default_factory=list,
        description=(
            "One short relevance note per index in top_reference_indices, in the "
            "same order. Each note must explain why that specific protocol is "
            "relevant to THIS hypothesis (not a generic description)."
        ),
    )


# ---------------------------------------------------------------------------
# System prompt
# ---------------------------------------------------------------------------


SYSTEM_PROMPT = """\
You are a senior wet-lab scientist evaluating whether a planned experiment
already exists in published protocol databases.

You will receive:
1. A structured hypothesis with these fields: intervention, biological_system,
   comparator_or_control, measurable_outcome, experiment_type.
2. A list of protocols retrieved from protocols.io, each with title, abstract,
   authors, year, and which search query found it.

Your job is to classify the novelty of the hypothesis using exactly one of:

CLASSIFICATION RULES (read carefully — these are intentionally realistic):

exact_match_found:
  Use this when at least one retrieved protocol covers BOTH:
    (a) the same or functionally equivalent intervention, AND
    (b) the same or very similar biological system or experimental context.
  The threshold and exact outcome do NOT need to match — protocols rarely
  report exact success thresholds. Focus on whether the core experiment
  (what is being tested, on what system) is already described.
  Example: a protocol for "trehalose as cryoprotectant in mammalian cell lines"
  is an exact match for a hypothesis about trehalose in HeLa cells.

similar_work_exists:
  Use this when retrieved protocols cover ONE of the following:
    (a) The same intervention applied to a different but related biological system, OR
    (b) A closely related intervention (same compound class, same technique family)
        applied to the same or similar biological system, OR
    (c) The same experimental type and assay in the same system, but for a
        different intervention purpose.
  This means: there is prior art the scientist must engage with, but the
  specific combination being proposed may not have been directly tested.

not_found:
  Use this when retrieved protocols are only peripherally related —
  same general field but different technique, different compound class,
  different organism kingdom, or the results are clearly unrelated to
  the hypothesis dimensions.
  Also use this when NO protocols were retrieved at all.

DIMENSION REASONING:
When classifying, explicitly reason across these three dimensions in your
explanation — this makes your decision auditable:
  1. Intervention dimension: is the same compound/method present in any protocol?
  2. Biological system dimension: is the same or similar system present?
  3. Experiment type dimension: is the same assay or methodology described?

RULES:
- Never claim certainty you do not have. If protocols are tangential, say so.
- Never invent protocol details not in the provided list.
- If no protocols were provided, classify as not_found and say so clearly.
- relevance_notes must explain specifically why that protocol is relevant to
  THIS hypothesis — not a generic description of the protocol.
- confidence_reasoning must reflect your genuine uncertainty, not just echo
  the novelty_signal. "Two protocols matched the intervention but neither
  used HeLa cells specifically" is good reasoning.
"""


# ---------------------------------------------------------------------------
# Token / env helpers
# ---------------------------------------------------------------------------


def _get_protocols_io_token() -> str:
    token = os.getenv("PROTOCOLS_IO_TOKEN", "").strip()
    if not token or token == "your_token_here":
        raise EnvironmentError(
            "PROTOCOLS_IO_TOKEN is not set. Add it to backend/.env."
        )
    return token


# ---------------------------------------------------------------------------
# protocols.io client
# ---------------------------------------------------------------------------


def _search_protocols(query: str, match_type: str, token: str | None = None) -> list[dict[str, Any]]:
    """Call ``GET /protocols`` on protocols.io for one query.

    Returns a list of raw protocol dicts (with ``match_type`` injected) or an
    empty list on any error. Never raises — degrades gracefully so the agent
    can still classify based on the queries that did succeed.
    """
    query = (query or "").strip()
    if not query:
        return []

    if token is None:
        try:
            token = _get_protocols_io_token()
        except EnvironmentError as exc:
            logger.warning("protocols.io token unavailable for query %r (%s): %s", query, match_type, exc)
            return []

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }
    base_url = f"{PROTOCOLS_IO_BASE_URL}/protocols"
    # APIs in the wild sometimes accept different search parameter names.
    # Try the required documented shape first, then compatibility fallbacks.
    param_candidates: list[dict[str, Any]] = [
        {
            "key": query,
            "filter": "public",
            "order_field": "relevance",
            "order_dir": "desc",
            "page_size": 10,
        },
        {
            "key": query,
            "filter": "public",
            "order_field": "published_on",
            "order_dir": "desc",
            "page_size": 10,
        },
        {
            "key": query,
            "filter": "public",
            "order_dir": "desc",
            "page_size": 10,
        },
        {
            "key": query,
            "filter": "public",
            "page_size": 10,
        },
        {
            "q": query,
            "filter": "public",
            "order_field": "published_on",
            "order_dir": "desc",
            "page_size": 10,
        },
        {
            "query": query,
            "filter": "public",
            "order_field": "published_on",
            "order_dir": "desc",
            "page_size": 10,
        },
    ]

    items: list[dict[str, Any]] = []
    got_successful_response = False
    last_status: int | None = None
    for params in param_candidates:
        try:
            response = requests.get(
                base_url,
                headers=headers,
                params=params,
                timeout=PROTOCOLS_IO_TIMEOUT_SECONDS,
            )
        except requests.RequestException as exc:
            logger.warning("protocols.io request failed for query %r (%s): %s", query, match_type, exc)
            return []

        if response.status_code >= 400:
            last_status = response.status_code
            continue

        try:
            payload = response.json()
        except ValueError:
            last_status = response.status_code
            continue

        maybe_items = payload.get("items") if isinstance(payload, dict) else None
        if isinstance(maybe_items, list):
            got_successful_response = True
            items = maybe_items
            break

    if not items:
        if got_successful_response:
            logger.info(
                "protocols.io returned no items for query %r (%s)",
                query,
                match_type,
            )
        else:
            logger.warning(
                "protocols.io returned HTTP %s or malformed payload for query %r (%s)",
                last_status if last_status is not None else "unknown",
                query,
                match_type,
            )
        return []

    results: list[dict[str, Any]] = []
    for item in items:
        if not isinstance(item, dict) or item.get("id") is None:
            continue
        item["match_type"] = match_type
        results.append(item)
    return results


# ---------------------------------------------------------------------------
# Deterministic confidence + recommended_action
# ---------------------------------------------------------------------------


_UNCERTAINTY_PHRASES = (
    "unclear",
    "not certain",
    "may be",
    "possibly",
    "cannot confirm",
    "limited",
    "tangential",
)


def _compute_confidence_score(
    *,
    query_a_count: int,
    query_b_count: int,
    query_c_count: int,
    total_unique: int,
    confidence_reasoning: str,
) -> float:
    if total_unique == 0:
        return 0.20

    score = 0.0
    if query_a_count >= 1:
        score += 0.30
    if query_b_count >= 1:
        score += 0.20
    if query_c_count >= 1:
        score += 0.15
    if total_unique >= 5:
        score += 0.20
    if total_unique >= 2:
        score += 0.10

    lowered = (confidence_reasoning or "").lower()
    if any(phrase in lowered for phrase in _UNCERTAINTY_PHRASES):
        score -= 0.15

    score = max(0.10, min(0.95, score))
    return round(score, 2)


def _recommended_action(novelty_signal: str, confidence_score: float) -> str:
    if novelty_signal == "exact_match_found":
        return (
            "A protocol matching this experiment was found on protocols.io. "
            "Review it before proceeding. If this is intentional replication, "
            "state that explicitly. If not, differentiate your approach."
        )
    if novelty_signal == "similar_work_exists" and confidence_score >= 0.60:
        return (
            "Related protocols exist. Review the references, cite relevant prior "
            "work in your plan, and explicitly state how your experiment differs "
            "or extends the existing approach."
        )
    if novelty_signal == "similar_work_exists" and confidence_score < 0.60:
        return (
            "Potentially related protocols found but match confidence is low. "
            "Manual literature review on protocols.io and PubMed recommended "
            "before committing to this experimental design."
        )
    if novelty_signal == "not_found" and confidence_score >= 0.55:
        return (
            "No directly matching protocol found. This combination appears novel. "
            "Proceed with experiment planning."
        )
    return (
        "Search returned limited results. This may indicate a novel experiment "
        "or a search coverage gap. Manual literature review strongly recommended."
    )


# ---------------------------------------------------------------------------
# Protocol-dict helpers
# ---------------------------------------------------------------------------


def _published_year(protocol: dict[str, Any]) -> int | None:
    ts = protocol.get("published_on")
    if not isinstance(ts, (int, float)) or ts <= 0:
        return None
    try:
        return datetime.fromtimestamp(float(ts), tz=timezone.utc).year
    except (OSError, OverflowError, ValueError):
        return None


def _author_names(protocol: dict[str, Any]) -> list[str]:
    raw = protocol.get("authors") or []
    if not isinstance(raw, list):
        return []
    names: list[str] = []
    for entry in raw:
        if isinstance(entry, dict):
            name = entry.get("name")
            if not name:
                first = (entry.get("first_name") or "").strip()
                last = (entry.get("last_name") or "").strip()
                name = (first + " " + last).strip()
            if name:
                names.append(str(name))
        elif isinstance(entry, str) and entry.strip():
            names.append(entry.strip())
    if len(names) > 3:
        names = names[:3] + ["et al."]
    return names


def _abstract_text(protocol: dict[str, Any]) -> str:
    text = protocol.get("description") or protocol.get("abstract")
    if not isinstance(text, str) or not text.strip():
        return "No abstract available"
    return text.strip()


def _protocol_url(protocol: dict[str, Any]) -> str:
    uri = (protocol.get("uri") or "").strip().lstrip("/")
    if not uri:
        return "https://www.protocols.io/"
    return f"https://www.protocols.io/{uri}"


def _to_reference(protocol: dict[str, Any], relevance_note: str) -> ProtocolReference:
    raw_match = protocol.get("match_type", "full_scope")
    if raw_match not in {"full_scope", "intervention_only", "system_method", "stub"}:
        raw_match = "full_scope"
    return ProtocolReference(
        title=str(protocol.get("title") or "Untitled protocol"),
        protocol_url=_protocol_url(protocol),
        authors=_author_names(protocol),
        published_year=_published_year(protocol),
        match_type=raw_match,
        relevance_note=relevance_note,
        is_stub=False,
    )


# ---------------------------------------------------------------------------
# LLM call
# ---------------------------------------------------------------------------


def _format_protocols_for_llm(protocols: list[dict[str, Any]]) -> str:
    lines: list[str] = []
    for idx, p in enumerate(protocols):
        abstract = _abstract_text(p)
        if len(abstract) > 300:
            abstract = abstract[:300]
        year = _published_year(p)
        year_text = str(year) if year is not None else "unknown"
        title = str(p.get("title") or "Untitled protocol")
        match_type = p.get("match_type", "full_scope")
        lines.append(
            f"[{idx}] (match_type={match_type}, year={year_text}) {title}\n"
            f"     abstract: {abstract}"
        )
    return "\n".join(lines) if lines else "(no protocols retrieved)"


def _classify_with_llm(
    hypothesis: StructuredHypothesis, protocols: list[dict[str, Any]]
) -> _LiteratureQCLLMOutput:
    client = get_client()

    user_message = (
        "STRUCTURED HYPOTHESIS\n"
        f"- intervention: {hypothesis.intervention}\n"
        f"- biological_system: {hypothesis.biological_system}\n"
        f"- comparator_or_control: {hypothesis.comparator_or_control}\n"
        f"- measurable_outcome: {hypothesis.measurable_outcome}\n"
        f"- experiment_type: {hypothesis.experiment_type}\n\n"
        "RETRIEVED PROTOCOLS (numbered list, 0-based indices):\n"
        f"{_format_protocols_for_llm(protocols)}\n\n"
        "Classify the novelty and select the most relevant protocols. "
        "Return top_reference_indices as a list of 0-based indices into the "
        "protocol list above, with relevance_notes in the same order."
    )

    return client.chat.completions.create(
        model=LLM_MODEL,
        response_model=_LiteratureQCLLMOutput,
        max_retries=LLM_MAX_RETRIES,
        temperature=0,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_message},
        ],
    )


# ---------------------------------------------------------------------------
# Stub mode
# ---------------------------------------------------------------------------


def _stub_literature_qc(hypothesis: StructuredHypothesis) -> LiteratureQCResult:
    intervention = (hypothesis.intervention or "").lower()
    if "trehalose" in intervention:
        signal = "similar_work_exists"
        confidence_score = 0.72
        return LiteratureQCResult(
            novelty_signal=signal,
            references=[
                ProtocolReference(
                    title="Trehalose-based cryopreservation of mammalian cells",
                    protocol_url="https://www.protocols.io/stub-reference-1",
                    authors=["Stub Author"],
                    published_year=2021,
                    match_type="stub",
                    relevance_note="Covers trehalose as a cryoprotectant in mammalian systems.",
                    is_stub=True,
                )
            ],
            confidence_score=confidence_score,
            explanation=(
                "Protocols using trehalose as a cryoprotectant exist on protocols.io, "
                "primarily in the context of cell preservation and lyophilization. "
                "No protocol was found combining trehalose with HeLa cells specifically "
                "using trypan blue viability as the primary endpoint."
            ),
            recommended_action=_recommended_action(signal, confidence_score),
            search_coverage="full",
        )

    signal = "not_found"
    confidence_score = 0.30
    return LiteratureQCResult(
        novelty_signal=signal,
        references=[],
        confidence_score=confidence_score,
        explanation="Stub mode active — no live search performed.",
        recommended_action=_recommended_action(signal, confidence_score),
        search_coverage="none",
    )


# ---------------------------------------------------------------------------
# Main entrypoint
# ---------------------------------------------------------------------------


def _build_queries(hypothesis: StructuredHypothesis) -> tuple[str, str, str]:
    """Return (query_a, query_b, query_c). Empty string means 'skip this query'."""
    query_a = (hypothesis.literature_search_hint or "").strip()
    if query_a == MISSING:
        query_a = ""

    intervention = hypothesis.intervention or ""
    query_b = "" if intervention == MISSING else intervention.strip()
    if len(query_b) > 60:
        query_b = query_b[:60]

    bio = "" if hypothesis.biological_system in (MISSING, "") else hypothesis.biological_system
    exp = "" if hypothesis.experiment_type in (MISSING, "") else hypothesis.experiment_type
    query_c = (bio + " " + exp).strip()

    return query_a, query_b, query_c


def _dedupe_protocols(*groups: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: dict[Any, dict[str, Any]] = {}
    for group in groups:
        for item in group:
            pid = item.get("id")
            if pid is None or pid in seen:
                continue
            seen[pid] = item
            if len(seen) >= MAX_UNIQUE_PROTOCOLS:
                return list(seen.values())
    return list(seen.values())


def _safe_failure(reason: str) -> LiteratureQCResult:
    return LiteratureQCResult(
        novelty_signal="not_found",
        references=[],
        confidence_score=0.10,
        explanation=f"Literature QC failed: {reason}",
        recommended_action="Manual literature review required — automated check failed.",
        search_coverage="none",
    )


def run_literature_qc_agent(hypothesis: StructuredHypothesis) -> LiteratureQCResult:
    """Run Literature QC for a structured hypothesis.

    Two execution modes:
      * stub mode (USE_STUB_AGENTS=true): deterministic, no network.
      * live mode: protocols.io search + OpenAI classification.
    """
    if USE_STUB_AGENTS:
        return _stub_literature_qc(hypothesis)

    token = _get_protocols_io_token()  # raises EnvironmentError if missing

    try:
        query_a, query_b, query_c = _build_queries(hypothesis)

        results_a = _search_protocols(query_a, "full_scope", token=token) if query_a else []
        results_b = _search_protocols(query_b, "intervention_only", token=token) if query_b else []
        results_c = _search_protocols(query_c, "system_method", token=token) if query_c else []

        ran_query_results: list[list[dict[str, Any]]] = []
        if query_a:
            ran_query_results.append(results_a)
        if query_b:
            ran_query_results.append(results_b)
        if query_c:
            ran_query_results.append(results_c)

        unique = _dedupe_protocols(results_a, results_b, results_c)
        total_unique = len(unique)

        if not ran_query_results or all(len(r) == 0 for r in ran_query_results):
            search_coverage: Literal["full", "partial", "none"] = "none"
        elif all(len(r) >= 1 for r in ran_query_results):
            search_coverage = "full"
        else:
            search_coverage = "partial"

        if total_unique == 0:
            novelty_signal: Literal[
                "not_found", "similar_work_exists", "exact_match_found"
            ] = "not_found"
            explanation = "No protocols found on protocols.io for this hypothesis."
            confidence_reasoning = "Search returned no results — cannot confirm novelty."
            top_indices: list[int] = []
            relevance_notes: list[str] = []
            sorted_top: list[dict[str, Any]] = []
        else:
            sorted_top = sorted(
                unique,
                key=lambda p: (
                    p.get("published_on") if isinstance(p.get("published_on"), (int, float)) else 0,
                    p.get("created_on") if isinstance(p.get("created_on"), (int, float)) else 0,
                ),
                reverse=True,
            )[:MAX_PROTOCOLS_FOR_LLM]

            llm_output = _classify_with_llm(hypothesis, sorted_top)
            novelty_signal = llm_output.novelty_signal
            explanation = llm_output.explanation
            confidence_reasoning = llm_output.confidence_reasoning
            top_indices = [i for i in llm_output.top_reference_indices if 0 <= i < len(sorted_top)]
            relevance_notes = list(llm_output.relevance_notes)

        confidence_score = _compute_confidence_score(
            query_a_count=len(results_a),
            query_b_count=len(results_b),
            query_c_count=len(results_c),
            total_unique=total_unique,
            confidence_reasoning=confidence_reasoning,
        )

        references: list[ProtocolReference] = []
        for slot, idx in enumerate(top_indices[:MAX_REFERENCES_RETURNED]):
            note = (
                relevance_notes[slot]
                if slot < len(relevance_notes) and relevance_notes[slot]
                else "Selected by classifier as relevant prior work."
            )
            references.append(_to_reference(sorted_top[idx], note))

        recommended_action = _recommended_action(novelty_signal, confidence_score)

        return LiteratureQCResult(
            novelty_signal=novelty_signal,
            references=references,
            confidence_score=confidence_score,
            explanation=explanation,
            recommended_action=recommended_action,
            search_coverage=search_coverage,
        )
    except Exception as exc:  # noqa: BLE001 — graceful degradation contract
        logger.exception("Literature QC pipeline failed.")
        return _safe_failure(str(exc))


# ---------------------------------------------------------------------------
# Adapter for the orchestrator (which still passes the StructuredHypothesis).
# ---------------------------------------------------------------------------


def run(hypothesis: StructuredHypothesis) -> LiteratureQCResult:
    return run_literature_qc_agent(hypothesis)


# ---------------------------------------------------------------------------
# CLI smoke test:  python -m app.agents.literature_qc
# ---------------------------------------------------------------------------


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    from app.agents.intake import DEMO_HYPOTHESIS, _stub_intake

    demo_hypothesis = _stub_intake(DEMO_HYPOTHESIS)
    result = run_literature_qc_agent(demo_hypothesis)
    print(json.dumps(result.model_dump(), indent=2))
    print(
        f"\nnovelty={result.novelty_signal}  "
        f"confidence={result.confidence_score:.2f}  "
        f"references={len(result.references)}  "
        f"coverage={result.search_coverage}"
    )
