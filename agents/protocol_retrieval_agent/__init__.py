"""Identify well-established protocol backbones for the hypothesis.
Note: returns LLM-suggested protocol categories. Sources are cited only when
the LLM is confident; specific URLs/DOIs are NOT invented."""
import json
from core.schemas import Hypothesis, ProtocolCandidate
from core.llm import chat_json, FAST_MODEL

SYSTEM = """You are a protocol-retrieval expert with deep knowledge of repositories:
protocols.io, Bio-protocol, Nature Protocols, JOVE, OpenWetWare, ATCC, Addgene, MIQE (qPCR),
and major vendor application notes (Thermo, Sigma, Promega, Qiagen, IDT).

Given a structured hypothesis, propose 2-4 well-established protocol backbones that would
serve as the foundation. For each, identify: the canonical method category, the most likely
source repository, missing steps that need adaptation, and confidence.

CRITICAL: Do NOT invent specific protocol URLs, DOIs, or catalog numbers. Cite only the
repository name. If unsure, set confidence low and note "verify before use".

Return JSON: {"candidates": [{
  "id": short slug,
  "title": method name,
  "source": repository name,
  "url": null,
  "match_score": 0.0-1.0,
  "missing_steps": [string],
  "adaptation_need": short string,
  "confidence": 0.0-1.0
}]}"""

USER = """Hypothesis:
{hypothesis}

Propose protocol candidates now."""


async def run(hypothesis: Hypothesis) -> list[ProtocolCandidate]:
    out = await chat_json(
        SYSTEM, USER.format(hypothesis=hypothesis.model_dump_json(indent=2)), model=FAST_MODEL,
    )
    candidates = []
    for c in (out.get("candidates") or [])[:4]:
        try:
            candidates.append(ProtocolCandidate(
                id=str(c.get("id", "")) or c.get("title", "candidate")[:32],
                title=c.get("title", ""),
                source=c.get("source", "unknown"),
                url=c.get("url"),
                match_score=float(c.get("match_score", 0.5)),
                missing_steps=c.get("missing_steps", []) or [],
                adaptation_need=c.get("adaptation_need", ""),
                confidence=float(c.get("confidence", 0.5)),
            ))
        except Exception:
            continue
    return candidates
