from __future__ import annotations

from datetime import UTC, datetime

from app.orchestrator import AGENT_ORDER, get_rerun_set, selective_regenerate
from app.schemas import (
    DemoRunResponse,
    FeedbackRecord,
    FeedbackRequest,
    RegenerateResponse,
    ScientistReview,
    StructuredHypothesis,
)
from app.services.memory import store_feedback, store_to_memory


def run_scientist_review(
    plan_id: str,
    review: ScientistReview,
    existing_plan: DemoRunResponse,
    hypothesis: StructuredHypothesis,
) -> RegenerateResponse:
    store_feedback(plan_id, review)
    store_to_memory(hypothesis, review)

    annotated_sections = [a.section.value for a in review.annotations]
    rerun_set = get_rerun_set(annotated_sections)
    unchanged_set = [s for s in AGENT_ORDER if s not in rerun_set]

    feedback_map: dict[str, str] = {}
    for annotation in review.annotations:
        section_val = annotation.section.value
        parts = [annotation.feedback_text]
        if annotation.requested_changes:
            parts.append("Requested changes:")
            parts.extend(f"- {c}" for c in annotation.requested_changes)
        parts.append(f"Severity: {annotation.severity}")
        combined = "\n".join(parts)
        if section_val in feedback_map:
            feedback_map[section_val] += "\n\n" + combined
        else:
            feedback_map[section_val] = combined

    if review.global_feedback:
        for section in rerun_set:
            note = f"Global feedback: {review.global_feedback}"
            feedback_map[section] = (feedback_map.get(section, "") + "\n\n" + note).strip()

    updated_plan, feedback_trace = selective_regenerate(
        existing_plan=existing_plan,
        hypothesis=hypothesis,
        rerun_set=rerun_set,
        feedback_map=feedback_map,
    )

    updated_plan.feedback_incorporated = True
    updated_plan.feedback_trace = feedback_trace

    return RegenerateResponse(
        plan_id=plan_id,
        updated_plan=updated_plan,
        feedback_incorporated=True,
        regenerated_sections=rerun_set,
        unchanged_sections=unchanged_set,
        feedback_trace=feedback_trace,
        stored_to_memory=True,
    )


def create_record(plan_id: str, payload: FeedbackRequest) -> FeedbackRecord:
    return FeedbackRecord(
        plan_id=plan_id,
        feedback=payload.feedback,
        requested_changes=payload.requested_changes,
        section=payload.section or "overall_plan",
        severity=payload.severity,
        created_at=datetime.now(UTC),
    )


def summarize(payload: FeedbackRequest) -> str:
    if payload.requested_changes:
        return f"{payload.feedback} | requested_changes={len(payload.requested_changes)}"
    return payload.feedback

