from fastapi import APIRouter
from core.schemas import ScientistFeedback
from agents import review_agent

router = APIRouter(prefix="/plans", tags=["plans"])


@router.post("/{plan_id}/feedback")
async def submit_feedback(plan_id: str, feedback: ScientistFeedback):
    await review_agent.store(feedback)
    return {"ok": True}


@router.post("/{plan_id}/regenerate")
async def regenerate(plan_id: str):
    return {"plan_id": plan_id, "status": "stub"}


@router.get("/{plan_id}/export")
async def export(plan_id: str):
    return {"plan_id": plan_id, "format": "markdown", "content": "(stub)"}
