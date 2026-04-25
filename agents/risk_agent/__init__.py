"""Identify failure modes; every risk maps to a required plan_action."""
import json
from core.schemas import ExperimentPlan, RiskItem
from core.llm import chat_json, FAST_MODEL

SYSTEM = """You are a senior scientist identifying failure modes in an experiment plan.
Categories to consider: biological_assumptions, technical_assumptions, model_system_risks,
assay_readout_mismatch, confounders, false_positive_risks, false_negative_risks,
control_gaps, replication_gaps, safety_compliance.

Every risk MUST map to a plan_action:
- document_only: low-severity, just note the assumption.
- modify_plan: moderate; require a concrete plan change (added control, dose-response, etc.).
- downgrade_to_pilot: high; replace full plan with pilot.
- block_execution: critical (pathogen work, human/animal subjects without IRB/IACUC, toxin
  production, hazardous synthesis, ecological release, clinical claims).

Return JSON: {"risks": [{
  "risk_id": "R1"...,
  "category": one of above,
  "description": short,
  "severity": "low"|"moderate"|"high"|"critical",
  "probability": 0.0-1.0,
  "impact": short,
  "required_mitigation": short imperative,
  "plan_action": one of the four
}]}
Identify 3-7 risks."""

USER = """Plan to assess:
{plan}

Identify risks now."""


async def run(plan: ExperimentPlan) -> list[RiskItem]:
    out = await chat_json(SYSTEM, USER.format(plan=plan.model_dump_json(indent=2)), model=FAST_MODEL)
    risks = []
    for i, r in enumerate((out.get("risks") or [])[:8], 1):
        try:
            risks.append(RiskItem(
                risk_id=r.get("risk_id") or f"R{i}",
                category=r.get("category", "technical_assumptions"),
                description=r["description"],
                severity=r.get("severity", "moderate"),
                probability=float(r.get("probability", 0.3)),
                impact=r.get("impact", ""),
                required_mitigation=r.get("required_mitigation", ""),
                plan_action=r.get("plan_action", "document_only"),
            ))
        except Exception:
            continue
    return risks
