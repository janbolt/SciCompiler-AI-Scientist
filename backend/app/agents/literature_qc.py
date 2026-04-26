"""Agent 2 of 11 — Literature QC Agent.

Searches Semantic Scholar (free public API, no key required) for papers
related to the hypothesis. Three queries are issued sequentially
(full_scope / intervention_only / system_method), results are deduplicated
by paperId, and an LLM classifies the novelty signal across three similarity
dimensions (intervention, biological system, experiment type).

Python — not the LLM — owns:
    * confidence_score  (deterministic scoring matrix)
    * recommended_action (deterministic lookup)
    * search_coverage   (computed from query result counts)

The LLM owns:
    * novelty_signal     (not_found | similar_work_exists | exact_match_found)
    * explanation        (2–3 sentences, dimension-by-dimension)
    * confidence_reasoning (used as a soft input into the score)
    * top_reference_indices + relevance_notes (which papers to surface)

Two execution modes:

- ``USE_STUB_AGENTS=true``  → ``_stub_literature_qc`` returns deterministic
  output without contacting any external API.
- Otherwise                 → live mode: Semantic Scholar REST + OpenAI via the
  shared instructor client (``Mode.TOOLS``).
"""

from __future__ import annotations

import json
import logging
import os
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


SEMANTIC_SCHOLAR_BASE_URL = "https://api.semanticscholar.org/graph/v1"
SEMANTIC_SCHOLAR_TIMEOUT_SECONDS = 15
MAX_UNIQUE_PAPERS = 8
MAX_PAPERS_FOR_LLM = 5
MAX_REFERENCES_RETURNED = 3

S2_FIELDS = "title,abstract,year,authors,externalIds,citationCount"


# ---------------------------------------------------------------------------
# LLM extraction model — only fields the LLM is allowed to fill in.
# ---------------------------------------------------------------------------


class _LiteratureQCLLMOutput(BaseModel):
    novelty_signal: Literal["not_found", "similar_work_exists", "exact_match_found"] = Field(
        ...,
        description=(
            "Classify the novelty of the hypothesis against the retrieved papers. "
            "Use 'exact_match_found' only when at least one paper covers BOTH the "
            "same/equivalent intervention AND the same/similar biological system. "
            "Use 'similar_work_exists' when there is meaningful prior art (same "
            "intervention on a related system, same compound class on the same "
            "system, or same experiment type with different intervention purpose). "
            "Use 'not_found' when retrieved papers are only peripherally related, "
            "or when no papers were retrieved."
        ),
    )
    explanation: str = Field(
        ...,
        description=(
            "2–3 sentences justifying the novelty_signal. Reason explicitly across "
            "three dimensions: (1) intervention, (2) biological system, (3) "
            "experiment type / assay. Reference papers by their bracketed index "
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
            "0-based indices into the paper list provided in the user message, "
            "for the most relevant papers. Maximum 3 indices. Empty list if no "
            "paper is relevant."
        ),
    )
    relevance_notes: list[str] = Field(
        default_factory=list,
        description=(
            "One short relevance note per index in top_reference_indices, in the "
            "same order. Each note must explain why that specific paper is "
            "relevant to THIS hypothesis (not a generic description)."
        ),
    )


# ---------------------------------------------------------------------------
# System prompt
# ---------------------------------------------------------------------------


SYSTEM_PROMPT = """\
You are a senior wet-lab scientist evaluating whether a planned experiment
already exists in the scientific literature.

You will receive:
1. A structured hypothesis with these fields: intervention, biological_system,
   comparator_or_control, measurable_outcome, experiment_type.
2. A list of papers retrieved from Semantic Scholar, each with title, abstract,
   year, authors, and which search query found it.

Your job is to classify the novelty of the hypothesis using exactly one of:

CLASSIFICATION RULES (read carefully — these are intentionally realistic):

exact_match_found:
  Use this when at least one retrieved paper covers BOTH:
    (a) the same or functionally equivalent intervention, AND
    (b) the same or very similar biological system or experimental context.
  The threshold and exact outcome do NOT need to match — papers rarely
  report exact success thresholds. Focus on whether the core experiment
  (what is being tested, on what system) is already described.

similar_work_exists:
  Use this when retrieved papers cover ONE of the following:
    (a) The same intervention applied to a different but related biological system, OR
    (b) A closely related intervention (same compound class, same technique family)
        applied to the same or similar biological system, OR
    (c) The same experimental type and assay in the same system, but for a
        different intervention purpose.

not_found:
  Use this when retrieved papers are only peripherally related —
  same general field but different technique, different compound class,
  different organism kingdom, or the results are clearly unrelated to
  the hypothesis dimensions.
  Also use this when NO papers were retrieved at all.

DIMENSION REASONING:
When classifying, explicitly reason across these three dimensions in your
explanation — this makes your decision auditable:
  1. Intervention dimension: is the same compound/method present in any paper?
  2. Biological system dimension: is the same or similar system present?
  3. Experiment type dimension: is the same assay or methodology described?

RULES:
- Never claim certainty you do not have. If papers are tangential, say so.
- Never invent paper details not in the provided list.
- If no papers were provided, classify as not_found and say so clearly.
- relevance_notes must explain specifically why that paper is relevant to
  THIS hypothesis — not a generic description of the paper.
- confidence_reasoning must reflect your genuine uncertainty, not just echo
  the novelty_signal.
"""


# ---------------------------------------------------------------------------
# Semantic Scholar client
# ---------------------------------------------------------------------------


def _search_semantic_scholar(query: str, match_type: str) -> list[dict[str, Any]]:
    """Call the Semantic Scholar paper search endpoint for one query.

    Returns a list of raw paper dicts (with ``match_type`` and ``paperId``
    injected) or an empty list on any error. Never raises — degrades
    gracefully so the agent can still classify based on queries that succeed.
    """
    query = (query or "").strip()
    if not query:
        return []

    url = f"{SEMANTIC_SCHOLAR_BASE_URL}/paper/search"
    params: dict[str, Any] = {
        "query": query,
        "fields": S2_FIELDS,
        "limit": 10,
    }

    try:
        response = requests.get(url, params=params, timeout=SEMANTIC_SCHOLAR_TIMEOUT_SECONDS)
    except requests.RequestException as exc:
        logger.warning("Semantic Scholar request failed for query %r (%s): %s", query, match_type, exc)
        return []

    if response.status_code >= 400:
        logger.warning(
            "Semantic Scholar returned HTTP %s for query %r (%s)",
            response.status_code, query, match_type,
        )
        return []

    try:
        payload = response.json()
    except ValueError:
        logger.warning("Semantic Scholar returned non-JSON for query %r (%s)", query, match_type)
        return []

    papers = payload.get("data") if isinstance(payload, dict) else None
    if not isinstance(papers, list):
        logger.info("Semantic Scholar returned no data for query %r (%s)", query, match_type)
        return []

    results: list[dict[str, Any]] = []
    for paper in papers:
        if not isinstance(paper, dict) or not paper.get("paperId"):
            continue
        paper["match_type"] = match_type
        results.append(paper)

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
            "A paper matching this experiment was found in the scientific literature. "
            "Review it before proceeding. If this is intentional replication, "
            "state that explicitly. If not, differentiate your approach."
        )
    if novelty_signal == "similar_work_exists" and confidence_score >= 0.60:
        return (
            "Related publications exist. Review the references, cite relevant prior "
            "work in your plan, and explicitly state how your experiment differs "
            "or extends the existing approach."
        )
    if novelty_signal == "similar_work_exists" and confidence_score < 0.60:
        return (
            "Potentially related papers found but match confidence is low. "
            "Manual literature review on PubMed and bioRxiv recommended "
            "before committing to this experimental design."
        )
    if novelty_signal == "not_found" and confidence_score >= 0.55:
        return (
            "No directly matching publication found. This combination appears novel. "
            "Proceed with experiment planning."
        )
    return (
        "Search returned limited results. This may indicate a novel experiment "
        "or a search coverage gap. Manual literature review strongly recommended."
    )


# ---------------------------------------------------------------------------
# Paper-dict helpers
# ---------------------------------------------------------------------------


def _paper_year(paper: dict[str, Any]) -> int | None:
    year = paper.get("year")
    if isinstance(year, int) and year > 0:
        return year
    return None


def _paper_authors(paper: dict[str, Any]) -> list[str]:
    raw = paper.get("authors") or []
    if not isinstance(raw, list):
        return []
    names: list[str] = []
    for entry in raw:
        if isinstance(entry, dict):
            name = (entry.get("name") or "").strip()
            if name:
                names.append(name)
        elif isinstance(entry, str) and entry.strip():
            names.append(entry.strip())
    if len(names) > 3:
        names = names[:3] + ["et al."]
    return names


def _paper_url(paper: dict[str, Any]) -> str:
    ext_ids = paper.get("externalIds") or {}
    if isinstance(ext_ids, dict):
        doi = ext_ids.get("DOI")
        if doi:
            return f"https://doi.org/{doi}"
    paper_id = paper.get("paperId", "")
    if paper_id:
        return f"https://www.semanticscholar.org/paper/{paper_id}"
    return "https://www.semanticscholar.org/"


def _paper_abstract(paper: dict[str, Any]) -> str:
    text = paper.get("abstract")
    if not isinstance(text, str) or not text.strip():
        return "No abstract available"
    return text.strip()


def _s2_to_reference(paper: dict[str, Any], relevance_note: str) -> ProtocolReference:
    raw_match = paper.get("match_type", "full_scope")
    if raw_match not in {"full_scope", "intervention_only", "system_method", "stub"}:
        raw_match = "full_scope"
    return ProtocolReference(
        title=str(paper.get("title") or "Untitled paper"),
        protocol_url=_paper_url(paper),
        authors=_paper_authors(paper),
        published_year=_paper_year(paper),
        match_type=raw_match,
        relevance_note=relevance_note,
        is_stub=False,
    )


# ---------------------------------------------------------------------------
# LLM call
# ---------------------------------------------------------------------------


def _format_papers_for_llm(papers: list[dict[str, Any]]) -> str:
    lines: list[str] = []
    for idx, p in enumerate(papers):
        abstract = _paper_abstract(p)
        if len(abstract) > 300:
            abstract = abstract[:300]
        year = _paper_year(p)
        year_text = str(year) if year is not None else "unknown"
        title = str(p.get("title") or "Untitled paper")
        match_type = p.get("match_type", "full_scope")
        citations = p.get("citationCount")
        citation_text = f", citations={citations}" if isinstance(citations, int) else ""
        lines.append(
            f"[{idx}] (match_type={match_type}, year={year_text}{citation_text}) {title}\n"
            f"     abstract: {abstract}"
        )
    return "\n".join(lines) if lines else "(no papers retrieved)"


def _classify_with_llm(
    hypothesis: StructuredHypothesis, papers: list[dict[str, Any]]
) -> _LiteratureQCLLMOutput:
    client = get_client()

    user_message = (
        "STRUCTURED HYPOTHESIS\n"
        f"- intervention: {hypothesis.intervention}\n"
        f"- biological_system: {hypothesis.biological_system}\n"
        f"- comparator_or_control: {hypothesis.comparator_or_control}\n"
        f"- measurable_outcome: {hypothesis.measurable_outcome}\n"
        f"- experiment_type: {hypothesis.experiment_type}\n\n"
        "RETRIEVED PAPERS (numbered list, 0-based indices):\n"
        f"{_format_papers_for_llm(papers)}\n\n"
        "Classify the novelty and select the most relevant papers. "
        "Return top_reference_indices as a list of 0-based indices into the "
        "paper list above, with relevance_notes in the same order."
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
                    protocol_url="https://www.semanticscholar.org/paper/stub-reference-1",
                    authors=["Stub Author"],
                    published_year=2021,
                    match_type="stub",
                    relevance_note="Covers trehalose as a cryoprotectant in mammalian systems.",
                    is_stub=True,
                )
            ],
            confidence_score=confidence_score,
            explanation=(
                "Papers using trehalose as a cryoprotectant exist in the literature, "
                "primarily in the context of cell preservation and lyophilization. "
                "No paper was found combining trehalose with HeLa cells specifically "
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
    if len(query_b) > 80:
        query_b = query_b[:80]

    bio = "" if hypothesis.biological_system in (MISSING, "") else hypothesis.biological_system
    exp = "" if hypothesis.experiment_type in (MISSING, "") else hypothesis.experiment_type
    query_c = (bio + " " + exp).strip()

    return query_a, query_b, query_c


def _dedupe_papers(*groups: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: dict[Any, dict[str, Any]] = {}
    for group in groups:
        for item in group:
            pid = item.get("paperId")
            if pid is None or pid in seen:
                continue
            seen[pid] = item
            if len(seen) >= MAX_UNIQUE_PAPERS:
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
      * live mode: Semantic Scholar search + OpenAI classification.
    """
    if USE_STUB_AGENTS:
        return _stub_literature_qc(hypothesis)

    try:
        query_a, query_b, query_c = _build_queries(hypothesis)

        results_a = _search_semantic_scholar(query_a, "full_scope") if query_a else []
        results_b = _search_semantic_scholar(query_b, "intervention_only") if query_b else []
        results_c = _search_semantic_scholar(query_c, "system_method") if query_c else []

        ran_query_results: list[list[dict[str, Any]]] = []
        if query_a:
            ran_query_results.append(results_a)
        if query_b:
            ran_query_results.append(results_b)
        if query_c:
            ran_query_results.append(results_c)

        unique = _dedupe_papers(results_a, results_b, results_c)
        total_unique = len(unique)

        if not ran_query_results or all(len(r) == 0 for r in ran_query_results):
            search_coverage: Literal["full", "partial", "none"] = "none"
        elif all(len(r) >= 1 for r in ran_query_results):
            search_coverage = "full"
        else:
            search_coverage = "partial"

        confidence_reasoning = ""

        if total_unique == 0:
            novelty_signal: Literal[
                "not_found", "similar_work_exists", "exact_match_found"
            ] = "not_found"
            explanation = "No papers found on Semantic Scholar for this hypothesis."
            confidence_reasoning = "Search returned no results — cannot confirm novelty."
            top_indices: list[int] = []
            relevance_notes: list[str] = []
            sorted_top: list[dict[str, Any]] = []
        else:
            sorted_top = sorted(
                unique,
                key=lambda p: (p.get("citationCount") or 0, p.get("year") or 0),
                reverse=True,
            )[:MAX_PAPERS_FOR_LLM]

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
            references.append(_s2_to_reference(sorted_top[idx], note))

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
# Adapter for the orchestrator.
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
