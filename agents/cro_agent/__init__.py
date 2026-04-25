"""Render the final plan as a CRO-ready RFQ brief."""
from core.schemas import ExperimentPlan


async def run(plan: ExperimentPlan) -> dict:
    return {
        "objective": plan.objective,
        "scope_of_work": [s.title for s in plan.protocol_steps],
        "sample_count": None,
        "required_assays": [v for v in [plan.validation.primary_endpoint] + (plan.validation.secondary_endpoints if plan.validation else [])] if plan.validation else [],
        "deliverables": ["Raw data", "Analysis report", "QC metrics"],
        "qc_requirements": plan.controls,
        "timeline_request_days": sum(p.duration_days + p.risk_buffer_days for p in plan.timeline.phases) or None,
        "questions_for_cro": [
            "Confirm catalog numbers and supplier availability before kickoff",
            "Confirm sample-size calculation matches the success threshold",
        ],
    }
