from __future__ import annotations

import re
from typing import Iterable

from .schemas import (
    BudgetEstimate,
    BudgetLineItem,
    ConfidenceLevel,
    CROReadyBrief,
    DemoRunRequest,
    EvidenceClaim,
    EvidenceType,
    ExperimentPlan,
    LiteratureQCResult,
    MaterialItem,
    NoveltySignal,
    PlanAction,
    ProtocolCandidate,
    ProtocolStep,
    Reference,
    RiskCategory,
    RiskItem,
    StructuredHypothesis,
    TimelineEstimate,
    TimelinePhase,
    ValidationPlan,
)


MISSING = "missing_required_field"


def _extract_after(text: str, prefix: str, stop_tokens: Iterable[str]) -> str | None:
    lower = text.lower()
    if prefix not in lower:
        return None
    start = lower.index(prefix) + len(prefix)
    candidate = text[start:].strip()
    stop_positions = [candidate.lower().find(token) for token in stop_tokens if token in candidate.lower()]
    stop_positions = [p for p in stop_positions if p >= 0]
    if stop_positions:
        candidate = candidate[: min(stop_positions)].strip(" ,.")
    return candidate or None


def intake_agent(request: DemoRunRequest) -> StructuredHypothesis:
    q = request.question.strip()
    q_lower = q.lower()

    organism = "HeLa cells" if "hela" in q_lower else MISSING
    experiment_type = "cell_freezing_cryopreservation" if "cryoprotectant" in q_lower or "freez" in q_lower else MISSING

    intervention = _extract_after(q, "replacing ", [" will ", " compared", " due to"]) or MISSING
    outcome = _extract_after(q, "will ", [" compared", " due to"]) or MISSING
    mechanism = _extract_after(q, "due to ", ["."]) or MISSING
    control_condition = _extract_after(q, "compared to ", [",", "."]) or MISSING

    endpoint = "post-thaw viability (%)" if "viability" in q_lower else MISSING
    match = re.search(r"(\d+(?:\.\d+)?)\s*(percentage points|%)", q_lower)
    expected_effect_size = f"{match.group(1)} {match.group(2)}" if match else MISSING

    hypothesis = StructuredHypothesis(
        raw_input=q,
        organism_or_model=organism,
        intervention=intervention,
        outcome=outcome,
        measurable_endpoint=endpoint,
        expected_effect_size=expected_effect_size,
        mechanism=mechanism,
        control_condition=control_condition,
        experiment_type=experiment_type,
        missing_fields=[],
    )
    missing_fields = [
        field_name
        for field_name, value in hypothesis.model_dump().items()
        if value == MISSING and field_name != "missing_fields"
    ]
    hypothesis.missing_fields = missing_fields
    return hypothesis


def literature_qc_agent(hypothesis: StructuredHypothesis) -> LiteratureQCResult:
    raw = hypothesis.raw_input.lower()
    if "hela" in raw and "trehalose" in raw and "dmso" in raw:
        novelty_signal = NoveltySignal.similar_work_exists
        refs = [
            Reference(
                title="Trehalose-enhanced cryopreservation of mammalian cells (candidate, verify)",
                source="semantic_scholar_stub",
                url="https://www.semanticscholar.org/",
            ),
            Reference(
                title="Optimization of HeLa post-thaw viability under modified cryomedia (candidate, verify)",
                source="pubmed_stub",
                url="https://pubmed.ncbi.nlm.nih.gov/",
            ),
        ]
        confidence = 0.72
        explanation = "Similar cryopreservation strategies are likely reported, but exact conditions appear variable."
        action = "Reuse established DMSO freezing backbone and test trehalose substitution as an adaptation."
    else:
        novelty_signal = NoveltySignal.not_found
        refs = []
        confidence = 0.45
        explanation = "No close match identified in the stubbed search index."
        action = "Proceed with a conservative pilot and stronger controls."

    return LiteratureQCResult(
        novelty_signal=novelty_signal,
        relevant_references=refs[:3],
        confidence=confidence,
        explanation=explanation,
        recommended_action=action,
    )


def protocol_retrieval_agent(hypothesis: StructuredHypothesis) -> list[ProtocolCandidate]:
    return [
        ProtocolCandidate(
            title="Baseline DMSO freezing for adherent human cell lines (candidate)",
            source="atcc_stub",
            summary="Standard controlled-rate freezing with 10% DMSO and serum-containing medium.",
            confidence=0.78,
            adaptation_notes="Replace sucrose fraction with trehalose arm while preserving cooling rate and thaw handling.",
        ),
        ProtocolCandidate(
            title="Trehalose supplementation in cryopreservation media (candidate)",
            source="protocols_io_stub",
            summary="Trehalose dose exploration prior to large-batch freezing.",
            confidence=0.63,
            adaptation_notes="Run a concentration sweep pilot before committing to full-scale comparison.",
        ),
    ]


def evidence_agent(hypothesis: StructuredHypothesis, qc: LiteratureQCResult) -> list[EvidenceClaim]:
    claims: list[EvidenceClaim] = [
        EvidenceClaim(
            claim="Trehalose may improve membrane stabilization during freeze-thaw cycles.",
            evidence_type=EvidenceType.mechanistic_evidence,
            source_ids=["hypothesis_mechanism"],
            relevance_to_plan="Supports adding trehalose treatment arm.",
        ),
        EvidenceClaim(
            claim="Post-thaw viability is an interpretable primary endpoint for this cell model.",
            evidence_type=EvidenceType.direct_evidence,
            source_ids=["standard_cell_culture_practice"],
            relevance_to_plan="Defines main assay readout.",
        ),
        EvidenceClaim(
            claim="Assumed +15 percentage-point viability improvement may be optimistic.",
            evidence_type=EvidenceType.unvalidated_assumption,
            source_ids=["hypothesis_effect_size"],
            relevance_to_plan="Requires pilot threshold check before scale-up.",
        ),
    ]
    if qc.novelty_signal == NoveltySignal.similar_work_exists:
        claims.append(
            EvidenceClaim(
                claim="Related methods exist but differ in conditions and cell handling details.",
                evidence_type=EvidenceType.indirect_evidence,
                source_ids=["lit_qc_ref_1"],
                relevance_to_plan="Justifies adaptation notes and conservative controls.",
            )
        )
    return claims


def risk_agent(hypothesis: StructuredHypothesis, evidence: list[EvidenceClaim]) -> list[RiskItem]:
    return [
        RiskItem(
            risk_id="R1",
            category=RiskCategory.biological_assumptions,
            description="Trehalose uptake and protection may differ from expected mechanism in HeLa cells.",
            severity="moderate",
            probability=0.5,
            impact="Reduced effect size despite protocol execution quality.",
            required_mitigation="Add dose-response pilot arm and confirm osmotic tolerance.",
            plan_action=PlanAction.modify_plan,
        ),
        RiskItem(
            risk_id="R2",
            category=RiskCategory.technical_assumptions,
            description="Cooling-rate variability can dominate cryoprotectant effect differences.",
            severity="high",
            probability=0.6,
            impact="False attribution of viability differences to chemical composition.",
            required_mitigation="Use controlled-rate freezing and instrument log capture for each batch.",
            plan_action=PlanAction.modify_plan,
        ),
        RiskItem(
            risk_id="R3",
            category=RiskCategory.assay_readout_mismatch,
            description="Single viability readout may miss delayed apoptosis after thaw.",
            severity="moderate",
            probability=0.55,
            impact="Overstated treatment benefit.",
            required_mitigation="Include delayed 24h viability follow-up.",
            plan_action=PlanAction.modify_plan,
        ),
        RiskItem(
            risk_id="R4",
            category=RiskCategory.control_gaps,
            description="No explicit no-cryoprotectant stress control in baseline setup.",
            severity="moderate",
            probability=0.5,
            impact="Weak interpretation of treatment effects.",
            required_mitigation="Add no-cryoprotectant stress control and sham-freeze control.",
            plan_action=PlanAction.modify_plan,
        ),
        RiskItem(
            risk_id="R5",
            category=RiskCategory.replication_gaps,
            description="Single run risks batch artifacts.",
            severity="low",
            probability=0.4,
            impact="Low confidence in reproducibility.",
            required_mitigation="Document as minimum 3 biological replicates requirement.",
            plan_action=PlanAction.document_only,
        ),
    ]


def _risk_mitigations(risks: list[RiskItem]) -> list[str]:
    return [f"{risk.risk_id}: {risk.required_mitigation}" for risk in risks if risk.plan_action == PlanAction.modify_plan]


def plan_agent(
    plan_id: str,
    hypothesis: StructuredHypothesis,
    risks: list[RiskItem],
    feedback_notes: list[str] | None = None,
) -> ExperimentPlan:
    mitigations = _risk_mitigations(risks)
    protocol = [
        ProtocolStep(
            step_number=1,
            description="Culture HeLa cells to consistent confluency before freezing.",
            linked_to="user_input",
        ),
        ProtocolStep(
            step_number=2,
            description="Prepare control (standard DMSO) and trehalose test cryomedia arms.",
            linked_to="hypothesis.intervention",
        ),
        ProtocolStep(
            step_number=3,
            description="Freeze using controlled-rate protocol and consistent vial fill volume.",
            linked_to="risk:R2",
        ),
        ProtocolStep(
            step_number=4,
            description="Thaw rapidly and measure immediate viability with blinded plate layout.",
            linked_to="validation.primary_endpoint",
        ),
        ProtocolStep(
            step_number=5,
            description="Measure 24h post-thaw viability to capture delayed cell death.",
            linked_to="risk:R3",
        ),
    ]

    next_step = len(protocol) + 1
    for mitigation in mitigations:
        protocol.append(
            ProtocolStep(
                step_number=next_step,
                description=f"Mitigation step: {mitigation}",
                linked_to="risk_mitigation",
            )
        )
        next_step += 1

    # Silently incorporate prior scientist corrections.
    # These are used as generation context — not surfaced as labelled steps.
    incorporated: list[str] = []
    for note in (feedback_notes or []):
        clean = note.split("] ", 1)[-1] if "] " in note else note
        incorporated.append(clean)

    assumptions = [
        "Trehalose concentration range is compatible with HeLa osmolality tolerance.",
        "Operator handling and thaw timing are standardized across arms.",
    ]
    if hypothesis.missing_fields:
        assumptions.append(f"Unspecified fields remain unresolved: {', '.join(hypothesis.missing_fields)}.")

    return ExperimentPlan(
        id=plan_id,
        objective="Evaluate whether trehalose substitution improves post-thaw HeLa viability against standard DMSO workflow.",
        experimental_design="Two-arm comparative cryopreservation study with pilot concentration sweep and replicate batches.",
        controls=[
            "Standard DMSO cryomedia control",
            "No-cryoprotectant stress control",
            "Sham-freeze handling control",
        ],
        step_by_step_protocol=protocol,
        assumptions=assumptions,
        decision_criteria=[
            "Advance if trehalose arm shows >=15 percentage-point improvement with acceptable variance.",
            "Downgrade to pilot optimization if improvement is between 5 and 15 percentage points.",
            "Stop if trehalose arm underperforms DMSO or increases delayed apoptosis.",
        ],
        risk_mitigations_applied=mitigations,
        feedback_incorporated=incorporated,
    )


def materials_agent() -> list[MaterialItem]:
    return [
        MaterialItem(
            name="HeLa cell line",
            supplier="ATCC candidate supplier",
            catalog_reference="verify_before_ordering",
            quantity="1 vial",
            estimated_unit_cost=450.0,
            confidence=ConfidenceLevel.medium,
            notes="Exact catalog must be verified before ordering.",
        ),
        MaterialItem(
            name="DMSO, cell culture grade",
            supplier="Thermo Fisher candidate supplier",
            catalog_reference="verify_before_ordering",
            quantity="500 mL",
            estimated_unit_cost=85.0,
            confidence=ConfidenceLevel.medium,
        ),
        MaterialItem(
            name="Trehalose",
            supplier="Sigma-Aldrich candidate supplier",
            catalog_reference="verify_before_ordering",
            quantity="100 g",
            estimated_unit_cost=120.0,
            confidence=ConfidenceLevel.low,
            notes="Purity grade and lot constraints to verify.",
        ),
    ]


def budget_agent(materials: list[MaterialItem]) -> BudgetEstimate:
    line_items = [
        BudgetLineItem(
            item_name=m.name,
            quantity=m.quantity,
            unit_cost_estimate=float(m.estimated_unit_cost or 0.0),
            total_cost_estimate=float(m.estimated_unit_cost or 0.0),
            supplier=m.supplier,
            catalog_reference=m.catalog_reference,
            confidence=m.confidence,
        )
        for m in materials
    ]
    line_items.append(
        BudgetLineItem(
            item_name="Consumables and assay reagents buffer",
            quantity="1 package",
            unit_cost_estimate=350.0,
            total_cost_estimate=350.0,
            supplier="local_core_facility_estimate",
            catalog_reference=None,
            confidence=ConfidenceLevel.low,
        )
    )
    total = sum(item.total_cost_estimate for item in line_items)
    return BudgetEstimate(
        line_items=line_items,
        estimated_total_cost=total,
        notes="Costs are directional for demo use. Verify quotations before procurement.",
    )


def timeline_agent() -> TimelineEstimate:
    phases = [
        TimelinePhase(
            phase_name="Setup and reagent verification",
            estimated_duration_days=3,
            dependencies=[],
            responsible_role="Research associate",
            risk_buffer_days=1,
        ),
        TimelinePhase(
            phase_name="Pilot dose-response freeze-thaw run",
            estimated_duration_days=5,
            dependencies=["Setup and reagent verification"],
            responsible_role="Scientist",
            risk_buffer_days=2,
        ),
        TimelinePhase(
            phase_name="Main replicate experiment",
            estimated_duration_days=7,
            dependencies=["Pilot dose-response freeze-thaw run"],
            responsible_role="Scientist",
            risk_buffer_days=2,
        ),
        TimelinePhase(
            phase_name="Analysis and go/no-go review",
            estimated_duration_days=3,
            dependencies=["Main replicate experiment"],
            responsible_role="PI",
            risk_buffer_days=1,
        ),
    ]
    return TimelineEstimate(phases=phases, estimated_total_days=sum(p.estimated_duration_days + p.risk_buffer_days for p in phases))


def validation_agent() -> ValidationPlan:
    return ValidationPlan(
        primary_endpoint="Post-thaw viability percentage at 0h and 24h.",
        secondary_endpoints=["Cell recovery count", "Morphology score", "Batch-to-batch variance"],
        success_threshold="Trehalose arm improves 24h viability by >=15 percentage points over DMSO.",
        failure_conditions=[
            "Improvement <5 percentage points after three biological replicates.",
            "Trehalose arm shows increased delayed apoptosis markers.",
        ],
        suggested_statistical_comparison="Two-sided t-test or Mann-Whitney U (depending on normality) with replicate-level analysis.",
    )


def experiments_agent(
    hypothesis: StructuredHypothesis,
    risks: list[RiskItem],
    feedback_notes: list[str] | None = None,
) -> "list":
    """
    Produces a list of FrontendExperiment objects — steps and materials grouped
    per experiment.  This is the primary output consumed by the frontend's
    Experiments tab.  The stub implementation is tailored to the cryopreservation
    demo hypothesis; an LLM-backed version would derive experiments dynamically.
    """
    from .schemas import FrontendExperiment, FrontendMaterial

    # Incorporate any scientist feedback notes as additional step text
    correction_steps: list[str] = []
    for note in (feedback_notes or []):
        clean = note.split("] ", 1)[-1] if "] " in note else note
        correction_steps.append(f"[Scientist correction incorporated] {clean}")

    exp1 = FrontendExperiment(
        id="exp-01",
        name="Cell Culture & Cryomedia Preparation",
        duration="3 days",
        cro_compatible=False,
        goal="Culture HeLa cells to consistent confluency and prepare both cryoprotectant arms before freezing.",
        success_criteria="Cells at 80–90% confluency; cryomedia prepared fresh and osmolality confirmed within ±10 mOsm/kg of target.",
        steps=[
            "Culture HeLa cells in DMEM + 10% FBS + 1% Pen/Strep at 37°C, 5% CO₂. Passage to T-75 flasks 72h before freezing.",
            "Confirm confluency at 80–90% by brightfield microscopy on day of harvest.",
            "Prepare Control cryomedia: DMEM + 10% FBS + 10% DMSO (standard arm).",
            "Prepare Trehalose cryomedia: DMEM + 10% FBS + 100 mM trehalose (test arm). Verify osmolality with osmometer.",
            "Trypsinize cells, count with hemocytometer (target 2×10⁶ cells/ml), resuspend in respective cryomedia.",
            "Aliquot 1 ml per cryovial. Label blinded (operator unaware of arm assignment).",
            *correction_steps,
        ],
        materials=[
            FrontendMaterial(name="HeLa cell line (ATCC CCL-2)", catalog="CCL-2", supplier="ATCC", qty="1 vial", unit_cost_eur=450.0, total_eur=450.0),
            FrontendMaterial(name="DMEM, high glucose", catalog="11965092", supplier="Thermo Fisher", qty="500 ml", unit_cost_eur=14.0, total_eur=14.0),
            FrontendMaterial(name="Fetal Bovine Serum", catalog="10270106", supplier="Thermo Fisher", qty="100 ml", unit_cost_eur=65.0, total_eur=65.0),
            FrontendMaterial(name="DMSO, cell culture grade", catalog="D2650", supplier="Sigma-Aldrich", qty="50 ml", unit_cost_eur=42.0, total_eur=42.0),
            FrontendMaterial(name="Trehalose dihydrate", catalog="T9531", supplier="Sigma-Aldrich", qty="5 g", unit_cost_eur=28.0, total_eur=28.0),
            FrontendMaterial(name="Cryogenic vials (2 ml)", catalog="5000-0012", supplier="Nunc", qty="50 vials", unit_cost_eur=0.6, total_eur=30.0),
        ],
    )

    exp2 = FrontendExperiment(
        id="exp-02",
        name="Controlled-Rate Freeze & Storage",
        duration="2 days",
        cro_compatible=True,
        goal="Freeze cell suspensions under controlled rate (−1°C/min) to minimize ice crystal formation, then store in LN₂.",
        success_criteria="Cooling log confirms −1°C/min rate through −80°C; all vials transferred to LN₂ within 15 min of reaching −80°C.",
        steps=[
            "Pre-chill isopropanol-filled controlled-rate freezing container (Mr. Frosty) to 4°C for 30 min.",
            "Place labelled cryovials into container; transfer to −80°C freezer immediately.",
            "Freeze overnight at −1°C/min rate. Verify log from thermal logger attached to representative vial.",
            "Next day: transfer vials to liquid nitrogen dewar. Record vial positions in cryogenic inventory.",
            "Store at −196°C for minimum 7 days before thaw to simulate realistic biobanking conditions.",
        ],
        materials=[
            FrontendMaterial(name="Mr. Frosty controlled-rate freezing container", catalog="5100-0001", supplier="Nunc", qty="1 unit", unit_cost_eur=85.0, total_eur=85.0),
            FrontendMaterial(name="Thermal data logger (mini)", catalog="EL-USB-1", supplier="EasyLog", qty="1 unit", unit_cost_eur=38.0, total_eur=38.0),
            FrontendMaterial(name="Liquid nitrogen dewar (bench-top)", catalog="lab_equipment", supplier="Core Facility", qty="1 use", unit_cost_eur=50.0, total_eur=50.0),
        ],
    )

    exp3 = FrontendExperiment(
        id="exp-03",
        name="Post-Thaw Viability Assessment",
        duration="2 days",
        cro_compatible=True,
        goal="Quantify immediate (0h) and delayed (24h) post-thaw viability to capture both acute and apoptotic cell death.",
        success_criteria="Trehalose arm shows ≥15 percentage-point improvement in 24h viability over DMSO control (p<0.05, unpaired t-test, n=3 biological replicates).",
        steps=[
            "Remove vials from LN₂; thaw rapidly in 37°C water bath for 60–90 s with gentle agitation. Do not exceed 2 min.",
            "Transfer contents dropwise to 10 ml warm DMEM. Centrifuge 300×g, 5 min. Aspirate supernatant.",
            "Resuspend pellet in 1 ml DMEM. Count viable cells by trypan blue exclusion (hemocytometer). Record 0h viability.",
            "Plate cells in 6-well plates at 5×10⁴/well. Culture 24h at 37°C, 5% CO₂.",
            "At 24h: harvest cells by trypsinization. Stain with propidium iodide (1 μg/ml) and Annexin V-FITC. Analyze by flow cytometry.",
            "Calculate % live (PI⁻/Annexin V⁻) per well. Average across duplicate wells per animal replicate.",
            "Perform unpaired two-tailed t-test between DMSO and trehalose arms. α=0.05.",
        ],
        materials=[
            FrontendMaterial(name="Trypan Blue Solution 0.4%", catalog="15250061", supplier="Thermo Fisher", qty="100 ml", unit_cost_eur=18.0, total_eur=18.0),
            FrontendMaterial(name="Annexin V-FITC / PI Apoptosis Kit", catalog="V13242", supplier="Thermo Fisher", qty="1 kit", unit_cost_eur=240.0, total_eur=240.0),
            FrontendMaterial(name="6-well cell culture plates", catalog="140675", supplier="Thermo Fisher", qty="4 plates", unit_cost_eur=8.0, total_eur=32.0),
            FrontendMaterial(name="Flow cytometer access (core)", catalog="core_service", supplier="Core Facility", qty="4 hours", unit_cost_eur=45.0, total_eur=180.0),
        ],
    )

    return [exp1, exp2, exp3]


def cro_brief_agent(plan: ExperimentPlan, timeline: TimelineEstimate) -> CROReadyBrief:
    return CROReadyBrief(
        objective=plan.objective,
        scope_of_work=[
            "Run comparative cryopreservation test between standard DMSO and trehalose-modified media.",
            "Execute pilot concentration sweep followed by replicate confirmation.",
        ],
        sample_count="Minimum 3 biological replicates per arm",
        required_assays=["Immediate post-thaw viability", "24h viability follow-up"],
        deliverables=["Raw viability data", "QC log", "Summary report with statistical comparison"],
        qc_requirements=["Controlled-rate freeze logs", "Blinded sample annotation", "Replicate traceability"],
        timeline_request=f"Target completion in approximately {timeline.estimated_total_days} days including risk buffers.",
        questions_for_cro=[
            "Can you support controlled-rate freezing instrumentation logs?",
            "Which viability assay kit do you recommend for 24h delayed apoptosis sensitivity?",
        ],
    )

