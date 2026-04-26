from __future__ import annotations

from datetime import datetime, UTC

from app.schemas import FeedbackRecord, FeedbackRequest


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

