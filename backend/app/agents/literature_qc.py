"""Agent 2 of 11 — Literature QC Agent.

Three-layer search pipeline:

Layer 0 — Authenticated Semantic Scholar (100 req/s with API key).
Layer 1 — LLM-generated keyword queries replace raw field concatenation.
Layer 2 — OpenAlex added as a second source; results deduplicated by DOI.
Layer 3 — Training-knowledge fallback when both sources return nothing.

Execution modes:
- USE_STUB_AGENTS=true  → _stub_literature_qc, no network.
- Otherwise            → live: LLM query gen → S2 + OpenAlex → LLM classify
                          (or training-knowledge fallback if zero papers).
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


# ---------------------------------------------------------------------------
# Config / constants
# ---------------------------------------------------------------------------

SEMANTIC_SCHOLAR_BASE_URL = "https://api.semanticscholar.org/graph/v1"
SEMANTIC_SCHOLAR_TIMEOUT_SECONDS = 15
S2_API_KEY = os.getenv("SEMANTIC_SCHOLAR_API_KEY", "")

OPENALEX_BASE_URL = "https://api.openalex.org"
OPENALEX_MAILTO = "team@predictivebio.com"
OPENALEX_TIMEOUT_SECONDS = 15

MAX_UNIQUE_PAPERS = 12   # up from 8 — two sources now
MAX_PAPERS_FOR_LLM = 6   # up from 5
MAX_REFERENCES_RETURNED = 3

S2_FIELDS = "title,abstract,year,authors,externalIds,citationCount"


# ---------------------------------------------------------------------------
# LLM schema — query generation (Layer 1)
# ---------------------------------------------------------------------------


class _SearchQueriesLLM(BaseModel):
    full_scope_query: str = Field(
        ...,
        description=(
            "3-7 keywords combining the intervention/method, biological system, "
            "and key outcome. Example: 'trehalose cryopreservation HeLa viability'."
        ),
    )
    intervention_query: str = Field(
        ...,
        description=(
            "3-6 keywords focused on the method, compound, or organism alone. "
            "Example: 'trehalose cryoprotectant membrane stabilization'."
        ),
    )
    system_method_query: str = Field(
        ...,
        description=(
            "3-6 keywords combining the biological system and experiment class. "
            "Example: 'HeLa cells cryopreservation post-thaw viability'."
        ),
    )


_QUERY_GEN_SYSTEM = """\
You are a scientific librarian. Your only job is to convert a structured
experimental hypothesis into three short, keyword-only academic search queries
suitable for Semantic Scholar and OpenAlex.

Rules:
- No full sentences. Keywords only, separated by spaces.
- 3-7 words per query.
- Use the most specific scientific terminology present in the hypothesis.
- Do not include stop words (the, a, of, with, and).
- For organism names use the full binomial (e.g. 'Sporomusa ovata', not just 'bacteria').
"""


def _generate_search_queries(hypothesis: StructuredHypothesis) -> _SearchQueriesLLM:
    """Call the LLM to produce three clean keyword search queries."""
    client = get_client()

    user_message = (
        "Generate three keyword search queries for this hypothesis.\n\n"
        f"intervention: {hypothesis.intervention}\n"
        f"biological_system: {hypothesis.biological_system}\n"
        f"measurable_outcome: {hypothesis.measurable_outcome}\n"
        f"experiment_type: {hypothesis.experiment_type}\n"
        f"literature_search_hint: {hypothesis.literature_search_hint}\n"
    )

    return client.chat.completions.create(
        model=LLM_MODEL,
        response_model=_SearchQueriesLLM,
        max_retries=LLM_MAX_RETRIES,
        temperature=0,
        messages=[
            {"role": "system", "content": _QUERY_GEN_SYSTEM},
            {"role": "user", "content": user_message},
        ],
    )


# ---------------------------------------------------------------------------
# LLM schema — novelty classification (existing, unchanged)
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
# System prompt — classification
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """\
You are a senior wet-lab scientist evaluating whether a planned experiment
already exists in the scientific literature.

You will receive:
1. A structured hypothesis with these fields: intervention, biological_system,
   comparator_or_control, measurable_outcome, experiment_type.
2. A list of papers retrieved from Semantic Scholar and/or OpenAlex, each with
   title, abstract, year, authors, and which search query found it.

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

_TRAINING_KNOWLEDGE_SYSTEM = """\
You are a senior wet-lab scientist. No papers were retrieved from academic
databases for this hypothesis (search returned zero results).

Assess the novelty of the hypothesis based on your training knowledge only.
Be explicitly honest that this is a training-data assessment, not backed by
live search results. Use hedge language throughout: 'likely', 'to my knowledge',
'based on training data', 'cannot confirm with certainty'.

For top_reference_indices and relevance_notes, return empty lists — you have
no paper list to cite.

Prefix your explanation with: "Based on training knowledge (no live papers retrieved):"
"""


# ---------------------------------------------------------------------------
# Semantic Scholar client (Layer 0 — authenticated)
# ---------------------------------------------------------------------------


def _search_semantic_scholar(query: str, match_type: str) -> list[dict[str, Any]]:
    """Query Semantic Scholar. Uses API key if available (100 req/s vs 1 req/s)."""
    query = (query or "").strip()
    if not query:
        return []

    url = f"{SEMANTIC_SCHOLAR_BASE_URL}/paper/search"
    params: dict[str, Any] = {
        "query": query,
        "fields": S2_FIELDS,
        "limit": 10,
    }
    headers: dict[str, str] = {}
    if S2_API_KEY:
        headers["x-api-key"] = S2_API_KEY

    try:
        response = requests.get(
            url, params=params, headers=headers,
            timeout=SEMANTIC_SCHOLAR_TIMEOUT_SECONDS,
        )
    except requests.RequestException as exc:
        logger.warning("S2 request failed for %r (%s): %s", query, match_type, exc)
        return []

    if response.status_code >= 400:
        logger.warning("S2 HTTP %s for %r (%s)", response.status_code, query, match_type)
        return []

    try:
        payload = response.json()
    except ValueError:
        logger.warning("S2 non-JSON for %r (%s)", query, match_type)
        return []

    papers = payload.get("data") if isinstance(payload, dict) else None
    if not isinstance(papers, list):
        return []

    results: list[dict[str, Any]] = []
    for paper in papers:
        if not isinstance(paper, dict) or not paper.get("paperId"):
            continue
        paper["match_type"] = match_type
        paper["_source"] = "s2"
        # Normalise DOI
        ext = paper.get("externalIds") or {}
        paper["_doi"] = (ext.get("DOI") or "").lower().strip()
        results.append(paper)

    return results


# ---------------------------------------------------------------------------
# OpenAlex client (Layer 2)
# ---------------------------------------------------------------------------


def _reconstruct_abstract(inverted_index: Any) -> str:
    """Convert OpenAlex inverted-index abstract to plain text."""
    if not isinstance(inverted_index, dict) or not inverted_index:
        return "No abstract available"
    positions: list[tuple[int, str]] = []
    for word, pos_list in inverted_index.items():
        if isinstance(pos_list, list):
            for pos in pos_list:
                positions.append((int(pos), word))
    positions.sort()
    return " ".join(w for _, w in positions)


def _search_openalex(query: str, match_type: str) -> list[dict[str, Any]]:
    """Query OpenAlex works search endpoint."""
    query = (query or "").strip()
    if not query:
        return []

    url = f"{OPENALEX_BASE_URL}/works"
    params: dict[str, Any] = {
        "search": query,
        "per-page": 10,
        "mailto": OPENALEX_MAILTO,
        "select": "id,doi,title,abstract_inverted_index,publication_year,cited_by_count,authorships",
    }

    try:
        response = requests.get(url, params=params, timeout=OPENALEX_TIMEOUT_SECONDS)
    except requests.RequestException as exc:
        logger.warning("OpenAlex request failed for %r (%s): %s", query, match_type, exc)
        return []

    if response.status_code >= 400:
        logger.warning("OpenAlex HTTP %s for %r (%s)", response.status_code, query, match_type)
        return []

    try:
        payload = response.json()
    except ValueError:
        logger.warning("OpenAlex non-JSON for %r (%s)", query, match_type)
        return []

    raw_papers = payload.get("results") if isinstance(payload, dict) else None
    if not isinstance(raw_papers, list):
        return []

    results: list[dict[str, Any]] = []
    for p in raw_papers:
        if not isinstance(p, dict):
            continue
        oa_id = p.get("id") or ""
        if not oa_id:
            continue

        doi_raw = (p.get("doi") or "").replace("https://doi.org/", "").lower().strip()

        # Reshape to the same dict shape the rest of the code expects
        authors: list[dict[str, str]] = []
        for a in (p.get("authorships") or [])[:4]:
            name = (a.get("author") or {}).get("display_name", "")
            if name:
                authors.append({"name": name})

        normalised: dict[str, Any] = {
            "paperId": oa_id,
            "title": p.get("title") or "Untitled",
            "abstract": _reconstruct_abstract(p.get("abstract_inverted_index")),
            "year": p.get("publication_year"),
            "authors": authors,
            "citationCount": p.get("cited_by_count"),
            "externalIds": {"DOI": doi_raw} if doi_raw else {},
            "match_type": match_type,
            "_source": "openalex",
            "_doi": doi_raw,
        }
        results.append(normalised)

    return results


# ---------------------------------------------------------------------------
# Deterministic helpers — confidence + recommended_action
# ---------------------------------------------------------------------------


_UNCERTAINTY_PHRASES = (
    "unclear",
    "not certain",
    "may be",
    "possibly",
    "cannot confirm",
    "limited",
    "tangential",
    "to my knowledge",
    "based on training",
)


def _compute_confidence_score(
    *,
    query_a_count: int,
    query_b_count: int,
    query_c_count: int,
    total_unique: int,
    confidence_reasoning: str,
    training_knowledge_only: bool = False,
) -> float:
    if training_knowledge_only:
        return 0.35

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

    return max(0.10, min(0.95, round(score, 2)))


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
    source = paper.get("_source", "s2")
    if paper_id:
        if source == "openalex":
            return paper_id  # OpenAlex IDs are already URLs
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
# LLM classification call
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
        source = p.get("_source", "s2")
        citations = p.get("citationCount")
        citation_text = f", citations={citations}" if isinstance(citations, int) else ""
        lines.append(
            f"[{idx}] (source={source}, match_type={match_type}, year={year_text}{citation_text}) {title}\n"
            f"     abstract: {abstract}"
        )
    return "\n".join(lines) if lines else "(no papers retrieved)"


def _classify_with_llm(
    hypothesis: StructuredHypothesis,
    papers: list[dict[str, Any]],
    system_prompt: str = SYSTEM_PROMPT,
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
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ],
    )


def _reason_from_training(hypothesis: StructuredHypothesis) -> _LiteratureQCLLMOutput:
    """Layer 3: LLM reasons from training knowledge when search returned nothing."""
    return _classify_with_llm(hypothesis, [], system_prompt=_TRAINING_KNOWLEDGE_SYSTEM)


# ---------------------------------------------------------------------------
# Deduplication — keyed on DOI, paperId as fallback (Layer 3)
# ---------------------------------------------------------------------------


def _dedupe_papers(*groups: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Deduplicate across S2 + OpenAlex results by DOI, then paperId."""
    seen_doi: set[str] = set()
    seen_pid: set[str] = set()
    result: list[dict[str, Any]] = []

    for group in groups:
        for item in group:
            doi = item.get("_doi", "")
            pid = item.get("paperId", "")

            if doi and doi in seen_doi:
                continue
            if pid and pid in seen_pid:
                continue

            if doi:
                seen_doi.add(doi)
            if pid:
                seen_pid.add(pid)

            result.append(item)
            if len(result) >= MAX_UNIQUE_PAPERS:
                return result

    return result


# ---------------------------------------------------------------------------
# Safe failure
# ---------------------------------------------------------------------------


def _safe_failure(reason: str) -> LiteratureQCResult:
    return LiteratureQCResult(
        novelty_signal="not_found",
        references=[],
        confidence_score=0.10,
        explanation=f"Literature QC failed: {reason}",
        recommended_action="Manual literature review required — automated check failed.",
        search_coverage="none",
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


def run_literature_qc_agent(hypothesis: StructuredHypothesis) -> LiteratureQCResult:
    """Run Literature QC for a structured hypothesis.

    Pipeline:
      1. LLM generates three clean keyword search queries.
      2. Both Semantic Scholar (authenticated) and OpenAlex are queried.
      3. Results are deduplicated by DOI → LLM classifies novelty.
      4. If zero papers found, LLM reasons from training knowledge instead.
    """
    if USE_STUB_AGENTS:
        return _stub_literature_qc(hypothesis)

    try:
        # Layer 1 — LLM-generated queries
        try:
            queries = _generate_search_queries(hypothesis)
            query_a = queries.full_scope_query.strip()
            query_b = queries.intervention_query.strip()
            query_c = queries.system_method_query.strip()
            logger.info("Generated queries: a=%r  b=%r  c=%r", query_a, query_b, query_c)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Query generation LLM failed, falling back to hint: %s", exc)
            hint = (hypothesis.literature_search_hint or "").strip()
            query_a = "" if hint == MISSING else hint
            query_b = (hypothesis.intervention or "").strip()[:80]
            bio = hypothesis.biological_system if hypothesis.biological_system not in (MISSING, "") else ""
            exp = hypothesis.experiment_type if hypothesis.experiment_type not in (MISSING, "") else ""
            query_c = (bio + " " + exp).strip()

        # Layer 0 + 2 — Dual-source search (S2 authenticated + OpenAlex)
        s2_a = _search_semantic_scholar(query_a, "full_scope") if query_a else []
        s2_b = _search_semantic_scholar(query_b, "intervention_only") if query_b else []
        s2_c = _search_semantic_scholar(query_c, "system_method") if query_c else []

        oa_a = _search_openalex(query_a, "full_scope") if query_a else []
        oa_b = _search_openalex(query_b, "intervention_only") if query_b else []
        oa_c = _search_openalex(query_c, "system_method") if query_c else []

        # Track per-query hit counts for confidence scoring (combine both sources)
        count_a = len(s2_a) + len(oa_a)
        count_b = len(s2_b) + len(oa_b)
        count_c = len(s2_c) + len(oa_c)

        # Deduplicate across all six result sets
        unique = _dedupe_papers(s2_a, oa_a, s2_b, oa_b, s2_c, oa_c)
        total_unique = len(unique)

        # search_coverage based on whether any query returned anything
        queries_run = sum([bool(query_a), bool(query_b), bool(query_c)])
        queries_hit = sum([count_a > 0, count_b > 0, count_c > 0])

        if queries_run == 0 or (count_a + count_b + count_c) == 0:
            search_coverage: Literal["full", "partial", "none"] = "none"
        elif queries_hit == queries_run:
            search_coverage = "full"
        else:
            search_coverage = "partial"

        # Layer 3 — fallback or normal classification
        training_knowledge_only = False
        confidence_reasoning = ""

        if total_unique == 0:
            # No papers at all — reason from training knowledge
            training_knowledge_only = True
            llm_output = _reason_from_training(hypothesis)
            novelty_signal = llm_output.novelty_signal
            explanation = llm_output.explanation
            confidence_reasoning = llm_output.confidence_reasoning
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
            query_a_count=count_a,
            query_b_count=count_b,
            query_c_count=count_c,
            total_unique=total_unique,
            confidence_reasoning=confidence_reasoning,
            training_knowledge_only=training_knowledge_only,
        )

        references: list[ProtocolReference] = []
        for slot, idx in enumerate(top_indices[:MAX_REFERENCES_RETURNED]):
            note = (
                relevance_notes[slot]
                if slot < len(relevance_notes) and relevance_notes[slot]
                else "Selected by classifier as relevant prior work."
            )
            references.append(_s2_to_reference(sorted_top[idx], note))

        return LiteratureQCResult(
            novelty_signal=novelty_signal,
            references=references,
            confidence_score=confidence_score,
            explanation=explanation,
            recommended_action=_recommended_action(novelty_signal, confidence_score),
            search_coverage=search_coverage,
        )

    except Exception as exc:  # noqa: BLE001
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
