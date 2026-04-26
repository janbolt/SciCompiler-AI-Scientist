from __future__ import annotations

from app.schemas import CROReadyBrief, ExperimentPlan, TimelineEstimate


def run(plan: ExperimentPlan, timeline: TimelineEstimate) -> CROReadyBrief:
    return CROReadyBrief(
        objective=plan.objective,
        scope_of_work=[
            "Execute pilot-first HeLa cryopreservation comparison between DMSO baseline and trehalose arm.",
            "Deliver replicate-confirmed viability analysis and mitigation traceability report.",
        ],
        sample_count="At least 3 biological replicates per arm",
        required_assays=["Immediate post-thaw viability", "24h follow-up viability"],
        deliverables=["Raw assay tables", "QC log", "Analysis summary", "Deviation report"],
        qc_requirements=["Controlled-rate freeze log", "Lot traceability", "Blinded run annotation"],
        timeline_request=timeline.total_duration_estimate,
        materials_responsibility="CRO to quote and confirm all materials before ordering.",
        questions_for_cro=[
            "Can you support controlled-rate freezing logs in each run?",
            "Can you include replicate-level batch metadata in the final report?",
        ],
    )

