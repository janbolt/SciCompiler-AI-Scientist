from fastapi import APIRouter
from core.schemas import DemoRunInput, DemoRunOutput
from agents.orchestrator import run_pipeline

router = APIRouter(prefix="/demo", tags=["demo"])


@router.post("/run", response_model=DemoRunOutput)
async def demo_run(inp: DemoRunInput):
    return await run_pipeline(inp)
