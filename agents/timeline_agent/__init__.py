"""Build a phased timeline with dependencies and risk buffers."""
import json
from core.schemas import ExperimentPlan, Timeline, TimelinePhase
from core.llm import chat_json, FAST_MODEL

SYSTEM = """You estimate realistic experiment timelines. Output 4-8 phases with explicit
dependencies (by phase name) and a risk_buffer in days.

Return JSON: {"phases": [{
  "name": str, "duration_days": int, "dependencies": [str],
  "responsible_role": str|null, "risk_buffer_days": int
}]}"""

USER = """Plan steps:
{steps}

Plan mode: {mode}

Generate the timeline."""


async def run(plan: ExperimentPlan) -> Timeline:
    out = await chat_json(
        SYSTEM,
        USER.format(
            steps=json.dumps([{"order": s.order, "title": s.title, "duration_min": s.duration_min} for s in plan.protocol_steps], indent=2),
            mode=plan.plan_mode,
        ),
        model=FAST_MODEL,
    )
    phases = []
    for p in (out.get("phases") or [])[:10]:
        try:
            phases.append(TimelinePhase(
                name=p["name"], duration_days=int(p.get("duration_days", 1)),
                dependencies=p.get("dependencies", []) or [],
                responsible_role=p.get("responsible_role"),
                risk_buffer_days=int(p.get("risk_buffer_days", 0)),
            ))
        except Exception:
            continue
    return Timeline(phases=phases)
