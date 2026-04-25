from __future__ import annotations

import uuid

from .agents import (
    budget_agent,
    cro_brief_agent,
    evidence_agent,
    intake_agent,
    literature_qc_agent,
    materials_agent,
    plan_agent,
    protocol_retrieval_agent,
    risk_agent,
    timeline_agent,
    validation_agent,
)
from .schemas import DemoRunRequest, DemoRunResponse
from .store import add_feedback, get_feedback_for_plan, load_plan_run, save_plan_run


def _confidence_score(*scores: float) -> float:
    return round(sum(scores) / max(len(scores), 1), 2)


def run_demo_pipeline(request: DemoRunRequest, existing_plan_id: str | None = None) -> DemoRunResponse:
    hypothesis = intake_agent(request)
    literature_qc = literature_qc_agent(hypothesis)
    protocol_candidates = protocol_retrieval_agent(hypothesis)
    evidence_claims = evidence_agent(hypothesis, literature_qc)
    risks = risk_agent(hypothesis, evidence_claims)

    plan_id = existing_plan_id or str(uuid.uuid4())
    feedback = get_feedback_for_plan(plan_id) if existing_plan_id else []
    feedback_notes = [f"{f.section}: {f.correction}" for f in sorted(feedback, key=lambda x: (x.section, x.correction))]
    plan = plan_agent(plan_id=plan_id, hypothesis=hypothesis, risks=risks, feedback_notes=feedback_notes)

    materials = materials_agent()
    budget = budget_agent(materials)
    timeline = timeline_agent()
    validation = validation_agent()
    cro_ready_brief = cro_brief_agent(plan, timeline)

    response = DemoRunResponse(
        hypothesis=hypothesis,
        literature_qc=literature_qc,
        protocol_candidates=protocol_candidates,
        evidence_claims=evidence_claims,
        risks=risks,
        plan=plan,
        materials=materials,
        budget=budget,
        timeline=timeline,
        validation=validation,
        cro_ready_brief=cro_ready_brief,
        confidence_score=_confidence_score(
            literature_qc.confidence,
            sum(p.confidence for p in protocol_candidates) / len(protocol_candidates),
            0.7 if plan.risk_mitigations_applied else 0.5,
        ),
    )
    save_plan_run(plan_id, {"request": request.model_dump(), "response": response.model_dump()})
    return response


def store_feedback(plan_id: str, section: str, original_text: str, correction: str, reason: str, severity: str) -> None:
    from .schemas import ScientistFeedback

    add_feedback(
        ScientistFeedback(
            plan_id=plan_id,
            section=section,
            original_text=original_text,
            correction=correction,
            reason=reason,
            severity=severity,
        )
    )


def regenerate_plan(plan_id: str) -> DemoRunResponse | None:
    previous = load_plan_run(plan_id)
    if previous is None:
        return None
    request = DemoRunRequest.model_validate(previous["request"])
    return run_demo_pipeline(request=request, existing_plan_id=plan_id)

