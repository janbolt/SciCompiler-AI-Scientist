"""Search literature (Europe PMC + preprints), then classify novelty."""
import json
from core.schemas import Hypothesis, LiteratureQCResult, Reference
from core.llm import chat_json, FAST_MODEL
from tools import pubmed, biorxiv

SYSTEM = """You are a scientific literature QC analyst.
Given a structured hypothesis and a list of literature hits with abstracts, decide whether
this exact experiment has been done before, whether similar work exists, or whether it is novel.
Use ONLY the provided hits — do not invent references. Pick at most 3 of the most relevant
hits by their `id` field.

Return JSON: {
  "novelty_signal": "exact_match_found" | "similar_work_exists" | "not_found",
  "confidence": 0.0-1.0,
  "relevant_reference_ids": [string],
  "explanation": short paragraph,
  "recommended_action": short imperative
}"""

USER = """Structured hypothesis:
{hypothesis}

Literature hits ({n} total):
{hits}

Classify novelty now."""


def _build_query(h: Hypothesis) -> str:
    parts = [h.intervention, h.outcome, h.organism_or_model, h.measurable_endpoint]
    q = " ".join(p for p in parts if p)
    return q or h.raw_input[:240]


async def run(hypothesis: Hypothesis) -> LiteratureQCResult:
    query = _build_query(hypothesis)
    pubmed_hits = await pubmed.search(query, limit=6)
    preprints = await biorxiv.search(query, limit=3)
    all_hits = pubmed_hits + preprints

    if not all_hits:
        return LiteratureQCResult(
            novelty_signal="not_found", confidence=0.4, relevant_references=[],
            explanation="No literature hits found via Europe PMC for the constructed query.",
            recommended_action="Generate a conservative exploratory plan with strong validation.",
        )

    summary = [{
        "id": h["id"], "title": h["title"], "year": h.get("year"),
        "source": h.get("source"), "abstract": (h.get("abstract") or "")[:500],
    } for h in all_hits]

    out = await chat_json(
        SYSTEM,
        USER.format(hypothesis=hypothesis.model_dump_json(indent=2), n=len(all_hits), hits=json.dumps(summary, indent=2)),
        model=FAST_MODEL,
    )

    by_id = {h["id"]: h for h in all_hits}
    refs = []
    for rid in (out.get("relevant_reference_ids") or [])[:3]:
        h = by_id.get(rid) or by_id.get(str(rid))
        if h:
            refs.append(Reference(
                id=str(h["id"]), title=h["title"], authors=h.get("authors", []),
                year=h.get("year"), doi=h.get("doi"), url=h.get("url"), source=h.get("source"),
            ))

    signal = out.get("novelty_signal", "similar_work_exists")
    if signal not in ("not_found", "similar_work_exists", "exact_match_found"):
        signal = "similar_work_exists"

    return LiteratureQCResult(
        novelty_signal=signal,
        confidence=float(out.get("confidence", 0.5)),
        relevant_references=refs,
        explanation=out.get("explanation", ""),
        recommended_action=out.get("recommended_action", ""),
    )
