from __future__ import annotations

from app.schemas import ExperimentPlan, PlanAction, ProtocolStep, RiskItem, StructuredHypothesis


def run(hypothesis: StructuredHypothesis, risks: list[RiskItem], feedback_incorporated: list[str]) -> ExperimentPlan:
    controls = [hypothesis.comparator_or_control]
    protocol_steps = [
        ProtocolStep(step_number=1, description="Standardize HeLa culture conditions before freezing.", linked_to="user_input"),
        ProtocolStep(step_number=2, description="Prepare baseline DMSO and trehalose cryomedia arms.", linked_to="hypothesis.intervention"),
        ProtocolStep(step_number=3, description="Freeze with controlled-rate process and log batch metadata.", linked_to="reproducibility"),
        ProtocolStep(step_number=4, description="Measure immediate post-thaw viability.", linked_to="validation.primary_endpoint"),
    ]
    risk_mitigations_applied: list[str] = []

    label = "execution_ready_after_review"
    execution_readiness_score = 0.78
    decision_criteria = [
        "Proceed if trehalose arm improves viability by threshold and no contradictory safety flags appear.",
        "Request scientist review before execution approval.",
    ]

    for risk in risks:
        if risk.action == PlanAction.modify_plan:
            risk_mitigations_applied.append(f"{risk.risk_id}: {risk.mitigation}")
            protocol_steps.append(
                ProtocolStep(
                    step_number=len(protocol_steps) + 1,
                    description=f"Mitigation step for {risk.risk_id}: {risk.mitigation}",
                    linked_to=f"risk:{risk.risk_id}",
                )
            )
            if "control" in risk.mitigation.lower():
                controls.extend(["no-cryoprotectant stress control", "sham-freeze handling control"])
        elif risk.action == PlanAction.downgrade_to_pilot:
            risk_mitigations_applied.append(f"{risk.risk_id}: downgraded to pilot ({risk.mitigation})")
            label = "pilot_only"
            execution_readiness_score = min(execution_readiness_score, 0.62)
            decision_criteria.append("Pilot-only mode: do not scale to full run until replicate criteria are met.")
        elif risk.action == PlanAction.block_execution:
            risk_mitigations_applied.append(f"{risk.risk_id}: execution blocked ({risk.mitigation})")
            label = "blocked_pending_expert_review"
            execution_readiness_score = 0.25
            decision_criteria.append("Execution blocked pending expert scientific review.")

    protocol_steps.append(
        ProtocolStep(
            step_number=len(protocol_steps) + 1,
            description="Measure delayed viability at 24h to detect latent post-thaw damage.",
            linked_to="risk_assay_readout_guardrail",
        )
    )

    return ExperimentPlan(
        objective="Assess whether trehalose substitution increases post-thaw HeLa viability versus standard DMSO protocol.",
        experimental_design="Controlled comparative cryopreservation with pilot-first gating and replicate requirement.",
        controls=list(dict.fromkeys(controls)),
        step_by_step_protocol=protocol_steps,
        assumptions=[
            "Cell handling and thaw timing are standardized across arms.",
            "Cryomedia preparation follows local SOP with documented version.",
        ],
        decision_criteria=decision_criteria,
        risk_mitigations_applied=risk_mitigations_applied,
        reproducibility_notes=[
            "Record operator, passage number, reagent lot, freeze curve, and thaw timestamps per batch.",
            "Maintain identical viability assay window and plate layout across comparator and intervention arms.",
        ],
        execution_readiness_score=execution_readiness_score,
        execution_readiness_label=label,  # type: ignore[arg-type]
        feedback_incorporated=feedback_incorporated,
    )

