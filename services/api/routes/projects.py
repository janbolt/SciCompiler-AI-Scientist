from fastapi import APIRouter
from core.schemas import Hypothesis, LiteratureQCResult, ExperimentPlan
from agents import intake_agent, literature_qc_agent
from agents.orchestrator import run_pipeline
from core.schemas import DemoRunInput

router = APIRouter(prefix="/projects", tags=["projects"])


@router.post("")
async def create_project():
    return {"project_id": "stub"}


@router.post("/{project_id}/hypothesis", response_model=Hypothesis)
async def submit_hypothesis(project_id: str, payload: dict):
    return await intake_agent.run(payload.get("raw_input", ""), payload.get("constraints"))


@router.post("/{project_id}/literature-qc", response_model=LiteratureQCResult)
async def lit_qc(project_id: str, hypothesis: Hypothesis):
    return await literature_qc_agent.run(hypothesis)


@router.post("/{project_id}/plans/generate")
async def generate_plan(project_id: str, payload: DemoRunInput):
    return await run_pipeline(payload)


@router.get("/{project_id}/plans/{plan_id}")
async def get_plan(project_id: str, plan_id: str):
    return {"project_id": project_id, "plan_id": plan_id}
