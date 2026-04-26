from __future__ import annotations

import httpx
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from .orchestrator import get_saved_plan, regenerate_plan, run_demo_pipeline, store_scientist_feedback
from .schemas import DemoRunRequest, DemoRunResponse, FeedbackRequest, FeedbackResponse
from . import litmus_client
from .litmus_client import classify_experiment_type
from .orchestrator import regenerate_plan, run_demo_pipeline, run_frontend_pipeline, store_feedback
from .schemas import (
    DemoRunRequest,
    DemoRunResponse,
    FrontendPlanData,
    LitmusSubmitRequest,
    LitmusSubmitResponse,
    LitmusSubmitResult,
    ScientistFeedbackInput,
)


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
@app.post("/demo/plan", response_model=FrontendPlanData)
def demo_plan(request: DemoRunRequest) -> FrontendPlanData:
    """
    Returns a FrontendPlanData JSON that the React app can consume directly —
    same shape as the TypeScript PlanData type, no adapter needed on the client.
    """
    return run_frontend_pipeline(request)


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
def regenerate(plan_id: str, payload: FeedbackRequest | None = None) -> DemoRunResponse:
    updated = regenerate_plan(plan_id=plan_id, payload=payload)
    if updated is None:
        raise HTTPException(status_code=404, detail="Plan not found")
    return updated


@app.post("/litmus/submit", response_model=LitmusSubmitResponse)
def litmus_submit(request: LitmusSubmitRequest) -> LitmusSubmitResponse:
    """
    Validate and submit selected CRO-compatible experiments to Litmus Science.
    The API key is read server-side from the LITMUS_API_KEY env var.
    Returns per-experiment results including live experiment_id, cost, and turnaround.
    """
    try:
        litmus_client._api_key()  # raises RuntimeError if key not configured
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    # Filter to only the requested experiments
    selected = [e for e in request.experiments if e.id in request.experiment_ids]
    if not selected:
        raise HTTPException(status_code=400, detail="No matching experiments found for given experiment_ids.")

    results: list[LitmusSubmitResult] = []
    for exp in selected:
        exp_type = classify_experiment_type(exp.name, exp.goal)
        try:
            response = litmus_client.submit_experiment(
                hypothesis=request.hypothesis,
                experiment_name=exp.name,
                experiment_goal=exp.goal,
            )
            results.append(LitmusSubmitResult(
                experiment_name=exp.name,
                experiment_type=exp_type,
                litmus_experiment_id=response.get("experiment_id"),
                status=response.get("status", "open"),
                estimated_cost_usd=response.get("estimated_cost_usd"),
                estimated_turnaround_days=response.get("estimated_turnaround_days"),
            ))
        except httpx.HTTPStatusError as exc:
            results.append(LitmusSubmitResult(
                experiment_name=exp.name,
                experiment_type=exp_type,
                status="error",
                error=f"Litmus API error {exc.response.status_code}: {exc.response.text[:200]}",
            ))
        except RuntimeError as exc:
            results.append(LitmusSubmitResult(
                experiment_name=exp.name,
                experiment_type=exp_type,
                status="error",
                error=str(exc),
            ))

    errors = sum(1 for r in results if r.status == "error")
    return LitmusSubmitResponse(
        results=results,
        total_submitted=len(results) - errors,
        total_errors=errors,
    )

