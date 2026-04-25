"""Draft and revise the operational ExperimentPlan."""
import json
from core.schemas import (
    Hypothesis, LiteratureQCResult, ProtocolCandidate, EvidenceClaim,
    RiskItem, ExperimentPlan, ProtocolStep, MaterialItem,
)
from core.llm import chat_json, PLAN_MODEL

DRAFT_SYSTEM = """You are a senior PI writing an operationally-runnable experiment plan.
Generate a concrete, step-by-step protocol with materials. Quality bar: a real lab
should be able to pick this up Monday and start running it Friday.

Hard rules:
- Do not invent specific catalog numbers (leave catalog_number null and set verified=false
  unless you are confident; if you suggest one, mark it as a candidate).
- Do not invent citations.
- Steps must include concentrations, volumes, times, temperatures where applicable.
- For qPCR work, comply with MIQE.

Return JSON: {
  "title": short string,
  "objective": one sentence,
  "plan_mode": "in_house" | "cro_ready" | "hybrid",
  "protocol_steps": [{"order": int, "title": str, "description": str, "duration_min": int|null, "notes": str|null}],
  "materials": [{"name": str, "supplier": str|null, "catalog_number": str|null, "quantity": str|null, "notes": str|null, "verified": false}],
  "controls": [str],
  "assumptions": [str],
  "confidence_score": 0.0-1.0
}"""

DRAFT_USER = """Hypothesis:
{hypothesis}

Literature QC: novelty={novelty}, action={action}
Top references: {refs}

Protocol candidates: {protocols}

Tagged evidence: {evidence}

Draft the plan now."""

REVISE_SYSTEM = """You are revising a draft experiment plan based on identified risks.
For each risk with plan_action != document_only, you MUST modify the plan accordingly:
- modify_plan: add controls, QC, pilot, orthogonal readout, dose-response, or rescue.
- downgrade_to_pilot: replace full plan with a cheap pilot version.
- block_execution: replace protocol_steps with a single "expert review required" step
  and set plan_mode='cro_ready'.

Return the SAME schema as the draft, but mutated to reflect the risk actions. Add a final
field "risk_modifications": [string] listing the changes you made."""

REVISE_USER = """Current draft:
{draft}

Risks (each with required plan_action):
{risks}

Revise the plan now."""


def _to_plan(out: dict, hypothesis: Hypothesis) -> ExperimentPlan:
    steps = [ProtocolStep(**{k: v for k, v in s.items() if k in {"order", "title", "description", "duration_min", "notes"}})
             for s in (out.get("protocol_steps") or [])]
    mats = [MaterialItem(**{k: v for k, v in m.items() if k in {"name", "supplier", "catalog_number", "quantity", "notes", "verified"}})
            for m in (out.get("materials") or [])]
    return ExperimentPlan(
        title=out.get("title") or f"Plan: {hypothesis.intervention or hypothesis.raw_input[:60]}",
        objective=out.get("objective", hypothesis.raw_input),
        plan_mode=out.get("plan_mode", "in_house") if out.get("plan_mode") in ("in_house", "cro_ready", "hybrid") else "in_house",
        protocol_steps=steps,
        materials=mats,
        controls=out.get("controls", []) or [],
        assumptions=out.get("assumptions", []) or [],
        confidence_score=float(out.get("confidence_score", 0.5)),
    )


async def draft(
    hypothesis: Hypothesis,
    qc: LiteratureQCResult,
    protocols: list[ProtocolCandidate],
    evidence: list[EvidenceClaim],
) -> ExperimentPlan:
    user = DRAFT_USER.format(
        hypothesis=hypothesis.model_dump_json(indent=2),
        novelty=qc.novelty_signal,
        action=qc.recommended_action,
        refs=json.dumps([{"id": r.id, "title": r.title, "year": r.year} for r in qc.relevant_references], indent=2),
        protocols=json.dumps([p.model_dump() for p in protocols], indent=2),
        evidence=json.dumps([e.model_dump() for e in evidence], indent=2),
    )
    out = await chat_json(DRAFT_SYSTEM, user, model=PLAN_MODEL)
    return _to_plan(out, hypothesis)


async def revise(plan: ExperimentPlan, risks: list[RiskItem]) -> ExperimentPlan:
    if not risks:
        plan.risks = []
        return plan
    user = REVISE_USER.format(
        draft=plan.model_dump_json(indent=2),
        risks=json.dumps([r.model_dump() for r in risks], indent=2),
    )
    out = await chat_json(REVISE_SYSTEM, user, model=PLAN_MODEL)
    revised = _to_plan(out, type("H", (), {"intervention": None, "raw_input": plan.objective})())
    revised.id = plan.id
    revised.risks = risks
    revised.assumptions = list(set(revised.assumptions + (out.get("risk_modifications") or [])))
    return revised
