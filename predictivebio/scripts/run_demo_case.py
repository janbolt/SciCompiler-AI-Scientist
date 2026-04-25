"""Run a benchmark hypothesis through the orchestrator."""
import asyncio, json, sys
from pathlib import Path
from core.schemas import DemoRunInput
from agents.orchestrator import run_pipeline


async def main():
    case_id = sys.argv[1] if len(sys.argv) > 1 else "crp"
    cases = json.loads((Path(__file__).parent.parent / "data/example_inputs/benchmark.json").read_text())
    case = next(c for c in cases if c["id"] == case_id)
    out = await run_pipeline(DemoRunInput(scientific_question=case["question"]))
    print(out.model_dump_json(indent=2))


if __name__ == "__main__":
    asyncio.run(main())
