from __future__ import annotations

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from .orchestrator import regenerate_plan, run_demo_pipeline, store_feedback
from .schemas import DemoRunRequest, DemoRunResponse, ScientistFeedbackInput


app = FastAPI(title="PredictiveBio Demo API", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/demo/run", response_model=DemoRunResponse)
def demo_run(request: DemoRunRequest) -> DemoRunResponse:
    return run_demo_pipeline(request)


@app.post("/plans/{plan_id}/feedback")
def save_feedback(plan_id: str, feedback: ScientistFeedbackInput) -> dict[str, str]:
    store_feedback(
        plan_id=plan_id,
        section=feedback.section,
        original_text=feedback.original_text,
        correction=feedback.correction,
        reason=feedback.reason,
        severity=feedback.severity,
    )
    return {"status": "stored", "plan_id": plan_id}


@app.post("/plans/{plan_id}/regenerate", response_model=DemoRunResponse)
def regenerate(plan_id: str) -> DemoRunResponse:
    updated = regenerate_plan(plan_id)
    if updated is None:
        raise HTTPException(status_code=404, detail="Plan not found")
    return updated

