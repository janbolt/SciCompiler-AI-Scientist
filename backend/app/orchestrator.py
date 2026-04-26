from __future__ import annotations

import json
import time
import uuid
from pathlib import Path

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

_DEBUG_LOG_PATH = Path("/Users/janikludwig/Developer/PredictiveBio/.cursor/debug-323526.log")


def _debug_log(run_id: str, hypothesis_id: str, location: str, message: str, data: dict[str, object]) -> None:
    # region agent log
    payload = {
        "sessionId": "323526",
        "runId": run_id,
        "hypothesisId": hypothesis_id,
        "location": location,
        "message": message,
        "data": data,
        "timestamp": int(time.time() * 1000),
    }
    with _DEBUG_LOG_PATH.open("a", encoding="utf-8") as fp:
        fp.write(json.dumps(payload) + "\n")
    # endregion


def _confidence_score(protocol_conf: float, readiness_score: float) -> float:
    return round((protocol_conf + readiness_score) / 2.0, 2)


def run_demo_pipeline(request: DemoRunRequest, plan_id: str | None = None) -> DemoRunResponse:
    hypothesis = run_intake(request)
    literature_qc = run_literature_qc(hypothesis)
    protocol_candidates = run_protocol_retrieval(hypothesis)
    evidence_claims = run_evidence(hypothesis, literature_qc)
    risks = run_risk(hypothesis, literature_qc)

    resolved_plan_id = plan_id or str(uuid.uuid4())
    prior_feedback = feedback_for_plan(resolved_plan_id)
    feedback_notes = [
        f"{item.feedback} | requested: {', '.join(item.requested_changes) if item.requested_changes else 'none'}"
        for item in prior_feedback
    ]
    # Incorporate structured scientist reviews sent directly in the request body.
    # These come from the frontend's ReviewPanel (star ratings + notes) and are
    # stored in localStorage, then sent as prior_feedback on each generation call.
    for fb in request.prior_feedback:
        if fb.note.strip():
            feedback_notes.append(
                f"{fb.experiment_type} › {fb.section} (rating {fb.rating}/5): {fb.note}"
            )

    plan = run_plan(
        hypothesis=hypothesis,
        risks=risks,
        feedback_incorporated=feedback_notes,
        protocol_candidates=protocol_candidates,
        literature_qc=literature_qc,
    )
    materials, budget = run_budget(hypothesis, plan)
    timeline = run_timeline(hypothesis, plan)
    validation = run_validation(hypothesis)
    cro_ready_brief = run_cro(plan, timeline)

    real_protocol_candidates = [c for c in protocol_candidates if c.source_type != "stub"]
    avg_protocol_conf = (
        sum(item.confidence for item in real_protocol_candidates) / len(real_protocol_candidates)
        if real_protocol_candidates
        else literature_qc.confidence_score
    )
    final_conf = _confidence_score(
        protocol_conf=avg_protocol_conf,
        readiness_score=plan.execution_readiness_score,
    )
    # region agent log
    _debug_log(
        "run1",
        "H7",
        "orchestrator.py:run_demo_pipeline",
        "confidence_inputs_outputs",
        {
            "candidate_count": len(protocol_candidates),
            "real_candidate_count": len(real_protocol_candidates),
            "candidate_source_types": [c.source_type for c in protocol_candidates[:5]],
            "candidate_confidences": [round(c.confidence, 3) for c in protocol_candidates[:5]],
            "avg_protocol_conf": round(avg_protocol_conf, 3),
            "protocol_conf_source": "real_candidates" if real_protocol_candidates else "literature_qc_fallback",
            "execution_readiness_score": round(plan.execution_readiness_score, 3),
            "final_confidence_score": final_conf,
        },
    )
    # endregion
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
        confidence_score=final_conf,
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
        return None
    if payload is not None:
        store_feedback(create_feedback_record(plan_id, payload))
    request = DemoRunRequest.model_validate(stored_plan["request"])
    return run_demo_pipeline(request=request, plan_id=plan_id)
