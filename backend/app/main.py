from __future__ import annotations

import logging

import httpx
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

logger = logging.getLogger(__name__)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s | %(message)s",
)
for _name in ("app", "app.agents", "app.agents.intake", "app.agents.plan", "app.services.llm"):
    logging.getLogger(_name).setLevel(logging.INFO)

from . import litmus_client
from .adapters import demo_response_to_frontend
from .agents.review import run_scientist_review
from .litmus_client import classify_experiment_type
from .orchestrator import (
    get_saved_plan,
    run_demo_pipeline,
    store_scientist_feedback,
)
from .schemas import (
    DemoRunRequest,
    DemoRunResponse,
    FeedbackRequest,
    FeedbackResponse,
    FrontendPlanData,
    LitmusSubmitRequest,
    LitmusSubmitResponse,
    LitmusSubmitResult,
    RegenerateResponse,
    ScientistReview,
    SectionAnnotation,
    SectionName,
)
from .services.memory import load_plan, save_plan


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


def _classify_pipeline_failure(exc: Exception) -> tuple[int, str, str]:
    """Map a pipeline RuntimeError into (status_code, reason_code, user_message).

    The frontend uses ``reason_code`` to render an actionable error state; the
    user_message is the human-readable detail surfaced in the toast/banner.
    """
    text = f"{exc} {exc!r}".lower()
    if any(t in text for t in ("connecterror", "apiconnectionerror", "connection error", "gaierror", "nodename")):
        return (
            502,
            "llm_unreachable",
            "Backend could not reach the LLM provider (DNS/network error). "
            "Check your internet connection or set USE_STUB_AGENTS=true to run offline.",
        )
    if any(t in text for t in ("invalid_api_key", "invalid api key", "401", "unauthorized")):
        return (
            502,
            "llm_unauthorized",
            "Backend rejected by the LLM provider (invalid API key). "
            "Update OPENAI_API_KEY in backend/.env and restart the server.",
        )
    if any(t in text for t in ("rate_limit", "429", "quota", "insufficient_quota")):
        return (
            502,
            "llm_rate_limited",
            "LLM provider rate-limited or out of quota. Try again in a moment "
            "or check your OpenAI account billing.",
        )
    if "proxyerror" in text or "403" in text:
        return (
            502,
            "llm_proxy_blocked",
            "A proxy/firewall is blocking outbound requests to the LLM provider. "
            "Bypass the proxy or set USE_STUB_AGENTS=true.",
        )
    return (500, "pipeline_error", f"Pipeline failed: {exc}")


@app.post("/demo/plan", response_model=FrontendPlanData)
def demo_plan(request: DemoRunRequest) -> FrontendPlanData:
    """Run the agent pipeline and shape the response for the React frontend.

    On any pipeline failure we return a structured JSON error (status 502/500)
    with an actionable ``reason`` code and ``detail`` message so the frontend
    can render an error state instead of silently falling back to mock data.
    """
    try:
        result = run_demo_pipeline(request)
    except RuntimeError as exc:
        status, reason, message = _classify_pipeline_failure(exc)
        logger.error("demo_plan failed: reason=%s detail=%s", reason, exc)
        raise HTTPException(
            status_code=status,
            detail={"reason": reason, "message": message, "question": request.question},
        ) from exc
    except Exception as exc:
        logger.exception("demo_plan crashed unexpectedly")
        raise HTTPException(
            status_code=500,
            detail={"reason": "unexpected_error", "message": str(exc), "question": request.question},
        ) from exc
    return demo_response_to_frontend(result)


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
    stored = load_plan(plan_id)
    if stored is None:
        raise HTTPException(status_code=404, detail="Plan not found")

    existing_plan = DemoRunResponse.model_validate(stored["response"])
    section_value = payload.section if payload and payload.section else "plan"
    try:
        section = SectionName(section_value)
    except ValueError:
        section = SectionName.PLAN

    review = ScientistReview(
        plan_id=plan_id,
        annotations=[
            SectionAnnotation(
                section=section,
                feedback_text=payload.feedback if payload else "",
                requested_changes=payload.requested_changes if payload else [],
                severity="major",
            )
        ],
        global_feedback="",
        reviewer_note="",
    )

    response = run_scientist_review(
        plan_id=plan_id,
        review=review,
        existing_plan=existing_plan,
        hypothesis=existing_plan.hypothesis,
    )
    save_plan(
        plan_id,
        {
            "request": stored.get("request", {}),
            "response": response.updated_plan.model_dump(mode="json"),
        },
    )
    return response.updated_plan


@app.post("/plans/{plan_id}/review", response_model=RegenerateResponse)
def review_plan(plan_id: str, review: ScientistReview) -> RegenerateResponse:
    stored = load_plan(plan_id)
    if stored is None:
        raise HTTPException(status_code=404, detail="Plan not found")

    existing_plan = DemoRunResponse.model_validate(stored["response"])
    response = run_scientist_review(
        plan_id=plan_id,
        review=review,
        existing_plan=existing_plan,
        hypothesis=existing_plan.hypothesis,
    )
    save_plan(
        plan_id,
        {
            "request": stored.get("request", {}),
            "response": response.updated_plan.model_dump(mode="json"),
        },
    )
    return response


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
