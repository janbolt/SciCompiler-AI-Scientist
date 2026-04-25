"""Tag hypothesis claims with evidence types based on retrieved literature."""
import json
from core.schemas import Hypothesis, EvidenceClaim, ProtocolCandidate, Reference
from core.llm import chat_json, FAST_MODEL

SYSTEM = """You tag scientific claims by evidence quality.
For each substantive claim implicit in the hypothesis, classify the evidence as one of:
direct, indirect, correlative, mechanistic, contradictory, unvalidated_assumption.
Cite source_ids ONLY from the references list provided. If no references support a claim,
mark it as unvalidated_assumption with empty source_ids.

Return JSON: {"claims": [{
  "claim": short string,
  "evidence_type": one of the six,
  "source_ids": [string],
  "strength": "weak" | "moderate" | "strong",
  "relevance_to_plan": short string
}]}"""

USER = """Hypothesis:
{hypothesis}

Available references (id → title):
{refs}

Protocol candidates:
{protocols}

Tag the claims now (3-6 claims)."""


async def run(
    hypothesis: Hypothesis,
    refs: list[Reference],
    protocols: list[ProtocolCandidate],
) -> list[EvidenceClaim]:
    refs_summary = json.dumps([{"id": r.id, "title": r.title, "year": r.year} for r in refs], indent=2)
    protos_summary = json.dumps([{"title": p.title, "source": p.source} for p in protocols], indent=2)
    out = await chat_json(
        SYSTEM,
        USER.format(hypothesis=hypothesis.model_dump_json(indent=2), refs=refs_summary, protocols=protos_summary),
        model=FAST_MODEL,
    )
    claims = []
    for c in (out.get("claims") or [])[:8]:
        try:
            claims.append(EvidenceClaim(
                claim=c["claim"],
                evidence_type=c.get("evidence_type", "unvalidated_assumption"),
                source_ids=c.get("source_ids", []) or [],
                strength=c.get("strength", "weak"),
                relevance_to_plan=c.get("relevance_to_plan", ""),
            ))
        except Exception:
            continue
    return claims
