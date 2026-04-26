from __future__ import annotations

import uuid

from app.agents import (
    create_feedback_record,
    run_budget,
    run_cro,
    run_evidence,
    run_intake,
    run_literature_qc,
    run_plan,
    run_protocol_retrieval,
    run_risk,
    run_timeline,
    run_validation,
    summarize_feedback,
)
from app.schemas import DemoRunRequest, DemoRunResponse, FeedbackRequest, FeedbackResponse
from app.services.memory import feedback_for_plan, load_plan, save_plan, store_feedback
from .adapters import to_frontend_plan
from .agents import (
    budget_agent,
    cro_brief_agent,
    evidence_agent,
    experiments_agent,
    intake_agent,
    literature_qc_agent,
    materials_agent,
    plan_agent,
    protocol_retrieval_agent,
    risk_agent,
    timeline_agent,
    validation_agent,
)
from .schemas import DemoRunRequest, DemoRunResponse, FrontendPlanData
from .store import add_feedback, get_feedback_for_plan, load_plan_run, save_plan_run


def _confidence_score(literature_conf: float, protocol_conf: float, readiness_score: float) -> float:
    return round((literature_conf + protocol_conf + readiness_score) / 3.0, 2)


def run_demo_pipeline(request: DemoRunRequest, plan_id: str | None = None) -> DemoRunResponse:
    hypothesis = run_intake(request)
    literature_qc = run_literature_qc(hypothesis)
    protocol_candidates = run_protocol_retrieval(hypothesis)
    evidence_claims = run_evidence(hypothesis, literature_qc)
    risks = run_risk()

    resolved_plan_id = plan_id or str(uuid.uuid4())
    prior_feedback = feedback_for_plan(resolved_plan_id)
    feedback_notes = [
        f"{item.feedback} | requested: {', '.join(item.requested_changes) if item.requested_changes else 'none'}"
        for item in prior_feedback
    ]
    plan_id = existing_plan_id or str(uuid.uuid4())

    # Merge stored plan-level feedback with incoming prior_feedback from the UI
    plan_feedback = get_feedback_for_plan(plan_id) if existing_plan_id else []
    plan_feedback_notes = [f"{f.section}: {f.correction}" for f in sorted(plan_feedback, key=lambda x: (x.section, x.correction))]

    # Prior feedback from the review panel: only carry corrections (rating ≤ 3)
    prior_notes = [
        f"[Prior review — {fb.experiment_type}, {fb.section}, rating {fb.rating}/5] {fb.note}"
        for fb in request.prior_feedback
        if fb.rating <= 3 and fb.note.strip()
    ]

    all_feedback_notes = plan_feedback_notes + prior_notes
    plan = plan_agent(plan_id=plan_id, hypothesis=hypothesis, risks=risks, feedback_notes=all_feedback_notes)

    plan = run_plan(hypothesis=hypothesis, risks=risks, feedback_incorporated=feedback_notes)
    materials, budget = run_budget()
    timeline = run_timeline()
    validation = run_validation(hypothesis)
    cro_ready_brief = run_cro(plan, timeline)

    avg_protocol_conf = sum(item.confidence for item in protocol_candidates) / len(protocol_candidates)
    response = DemoRunResponse(
        plan_id=resolved_plan_id,
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
            literature_conf=literature_qc.confidence_score,
            protocol_conf=avg_protocol_conf,
            readiness_score=plan.execution_readiness_score,
        ),
    )
    save_plan(resolved_plan_id, {"request": request.model_dump(mode="json"), "response": response.model_dump(mode="json")})
    return response


def store_scientist_feedback(plan_id: str, payload: FeedbackRequest) -> FeedbackResponse:
    record = create_feedback_record(plan_id, payload)
    store_feedback(record)
    return FeedbackResponse(plan_id=plan_id, stored=True, feedback_summary=summarize_feedback(payload))


def get_saved_plan(plan_id: str) -> DemoRunResponse | None:
    stored = load_plan(plan_id)
    if stored is None:
        return None
    return DemoRunResponse.model_validate(stored["response"])


def regenerate_plan(plan_id: str, payload: FeedbackRequest | None = None) -> DemoRunResponse | None:
    stored_plan = load_plan(plan_id)
    if stored_plan is None:
def run_frontend_pipeline(request: DemoRunRequest) -> FrontendPlanData:
    """
    Lightweight pipeline that returns the frontend-shaped PlanData JSON directly.
    Used by POST /demo/plan so the React app can replace MOCK_PLAN with live data.
    """
    hypothesis = intake_agent(request)
    literature_qc = literature_qc_agent(hypothesis)
    evidence_claims = evidence_agent(hypothesis, literature_qc)
    risks = risk_agent(hypothesis, evidence_claims)
    timeline = timeline_agent()

    # Prior feedback: only low-rated corrections become generation context
    prior_notes = [
        f"[Prior review — {fb.experiment_type}, {fb.section}, rating {fb.rating}/5] {fb.note}"
        for fb in request.prior_feedback
        if fb.rating <= 3 and fb.note.strip()
    ]

    experiments = experiments_agent(hypothesis, risks, feedback_notes=prior_notes)

    return to_frontend_plan(hypothesis, literature_qc, timeline, experiments)


def regenerate_plan(plan_id: str) -> DemoRunResponse | None:
    previous = load_plan_run(plan_id)
    if previous is None:
        return None
    if payload is not None:
        store_feedback(create_feedback_record(plan_id, payload))
    request = DemoRunRequest.model_validate(stored_plan["request"])
    return run_demo_pipeline(request=request, plan_id=plan_id)

