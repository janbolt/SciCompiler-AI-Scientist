from __future__ import annotations

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from .orchestrator import get_saved_plan, regenerate_plan, run_demo_pipeline, store_scientist_feedback
from .schemas import DemoRunRequest, DemoRunResponse, FeedbackRequest, FeedbackResponse


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


@app.get("/plans/{plan_id}", response_model=DemoRunResponse)
def get_plan(plan_id: str) -> DemoRunResponse:
    saved = get_saved_plan(plan_id)
    if saved is None:
        raise HTTPException(status_code=404, detail="Plan not found")
    return saved


@app.post("/plans/{plan_id}/feedback", response_model=FeedbackResponse)
def save_feedback(plan_id: str, payload: FeedbackRequest) -> FeedbackResponse:
    return store_scientist_feedback(plan_id=plan_id, payload=payload)


@app.post("/plans/{plan_id}/regenerate", response_model=DemoRunResponse)
def regenerate(plan_id: str, payload: FeedbackRequest | None = None) -> DemoRunResponse:
    updated = regenerate_plan(plan_id=plan_id, payload=payload)
    if updated is None:
        raise HTTPException(status_code=404, detail="Plan not found")
    return updated

