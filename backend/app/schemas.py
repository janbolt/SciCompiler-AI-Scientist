from __future__ import annotations

from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field


class ExecutionMode(str, Enum):
    in_house = "in_house"
    cro_ready = "cro_ready"
    hybrid = "hybrid"


class NoveltySignal(str, Enum):
    not_found = "not_found"
    similar_work_exists = "similar_work_exists"
    exact_match_found = "exact_match_found"


class EvidenceType(str, Enum):
    direct_evidence = "direct_evidence"
    indirect_evidence = "indirect_evidence"
    correlative_evidence = "correlative_evidence"
    mechanistic_evidence = "mechanistic_evidence"
    contradictory_evidence = "contradictory_evidence"
    unvalidated_assumption = "unvalidated_assumption"


class RiskCategory(str, Enum):
    biological_assumptions = "biological_assumptions"
    technical_assumptions = "technical_assumptions"
    model_system_risks = "model_system_risks"
    assay_readout_mismatch = "assay_readout_mismatch"
    confounders = "confounders"
    false_positive_risks = "false_positive_risks"
    false_negative_risks = "false_negative_risks"
    control_gaps = "control_gaps"
    replication_gaps = "replication_gaps"


class PlanAction(str, Enum):
    document_only = "document_only"
    modify_plan = "modify_plan"
    downgrade_to_pilot = "downgrade_to_pilot"
    block_execution = "block_execution"


class ConfidenceLevel(str, Enum):
    low = "low"
    medium = "medium"
    high = "high"


MissingRequiredField = Literal["missing_required_field"]


class RunConstraints(BaseModel):
    budget: str | None = None
    timeline: str | None = None
    execution_mode: ExecutionMode = ExecutionMode.in_house


class PriorFeedbackItem(BaseModel):
    """One scientist correction captured from the review UI and passed back to
    the generation layer so the backend can incorporate it as a few-shot signal."""
    experiment_type: str
    section: str  # "steps" | "materials" | "timeline"
    rating: int = Field(ge=1, le=5)
    note: str
    timestamp: str = ""


class DemoRunRequest(BaseModel):
    question: str
    constraints: RunConstraints = Field(default_factory=RunConstraints)
    prior_feedback: list[PriorFeedbackItem] = Field(default_factory=list)


class StructuredHypothesis(BaseModel):
    raw_input: str
    organism_or_model: str | MissingRequiredField
    intervention: str | MissingRequiredField
    outcome: str | MissingRequiredField
    measurable_endpoint: str | MissingRequiredField
    expected_effect_size: str | MissingRequiredField
    mechanism: str | MissingRequiredField
    control_condition: str | MissingRequiredField
    experiment_type: str | MissingRequiredField
    missing_fields: list[str]


class Reference(BaseModel):
    title: str
    source: str
    url: str | None = None
    year: int | None = None


class LiteratureQCResult(BaseModel):
    novelty_signal: NoveltySignal
    relevant_references: list[Reference]
    confidence: float = Field(ge=0.0, le=1.0)
    explanation: str
    recommended_action: str


class ProtocolCandidate(BaseModel):
    title: str
    source: str
    summary: str
    confidence: float = Field(ge=0.0, le=1.0)
    adaptation_notes: str


class EvidenceClaim(BaseModel):
    claim: str
    evidence_type: EvidenceType
    source_ids: list[str]
    relevance_to_plan: str


class RiskItem(BaseModel):
    risk_id: str
    category: RiskCategory
    description: str
    severity: Literal["low", "moderate", "high", "critical"]
    probability: float = Field(ge=0.0, le=1.0)
    impact: str
    required_mitigation: str
    plan_action: PlanAction


class ProtocolStep(BaseModel):
    step_number: int
    description: str
    linked_to: str


class MaterialItem(BaseModel):
    name: str
    supplier: str
    catalog_reference: str | Literal["verify_before_ordering"] | None = None
    quantity: str
    estimated_unit_cost: float | None = None
    confidence: ConfidenceLevel
    notes: str | None = None


class BudgetLineItem(BaseModel):
    item_name: str
    quantity: str
    unit_cost_estimate: float
    total_cost_estimate: float
    supplier: str
    catalog_reference: str | Literal["verify_before_ordering"] | None = None
    confidence: ConfidenceLevel


class BudgetEstimate(BaseModel):
    currency: str = "USD"
    line_items: list[BudgetLineItem]
    estimated_total_cost: float
    notes: str


class TimelinePhase(BaseModel):
    phase_name: str
    estimated_duration_days: int
    dependencies: list[str]
    responsible_role: str
    risk_buffer_days: int


class TimelineEstimate(BaseModel):
    phases: list[TimelinePhase]
    estimated_total_days: int


class ValidationPlan(BaseModel):
    primary_endpoint: str
    secondary_endpoints: list[str]
    success_threshold: str
    failure_conditions: list[str]
    suggested_statistical_comparison: str


class ExperimentPlan(BaseModel):
    id: str
    objective: str
    experimental_design: str
    controls: list[str]
    step_by_step_protocol: list[ProtocolStep]
    assumptions: list[str]
    decision_criteria: list[str]
    risk_mitigations_applied: list[str]
    feedback_incorporated: list[str] = Field(default_factory=list)


class CROReadyBrief(BaseModel):
    objective: str
    scope_of_work: list[str]
    sample_count: str
    required_assays: list[str]
    deliverables: list[str]
    qc_requirements: list[str]
    timeline_request: str
    questions_for_cro: list[str]


class DemoRunResponse(BaseModel):
    hypothesis: StructuredHypothesis
    literature_qc: LiteratureQCResult
    protocol_candidates: list[ProtocolCandidate]
    evidence_claims: list[EvidenceClaim]
    risks: list[RiskItem]
    plan: ExperimentPlan
    materials: list[MaterialItem]
    budget: BudgetEstimate
    timeline: TimelineEstimate
    validation: ValidationPlan
    cro_ready_brief: CROReadyBrief
    confidence_score: float = Field(ge=0.0, le=1.0)


class ScientistFeedbackInput(BaseModel):
    section: str
    original_text: str
    correction: str
    reason: str
    severity: Literal["low", "medium", "high"] = "medium"


class ScientistFeedback(ScientistFeedbackInput):
    plan_id: str


# ── Frontend-shaped models ────────────────────────────────────────────────────
# These mirror the TypeScript PlanData types the frontend consumes directly.
# The /demo/plan endpoint returns FrontendPlanData so the UI can drop MOCK_PLAN.

class FrontendMaterial(BaseModel):
    name: str
    catalog: str
    supplier: str
    qty: str
    unit_cost_eur: float
    total_eur: float


class FrontendExperiment(BaseModel):
    id: str
    name: str
    duration: str
    cro_compatible: bool
    goal: str
    success_criteria: str
    steps: list[str]
    materials: list[FrontendMaterial]


class FrontendReference(BaseModel):
    citation: str
    doi: str


class FrontendBudgetLine(BaseModel):
    item: str
    cost_eur: float


class FrontendBudget(BaseModel):
    fixed: list[FrontendBudgetLine]
    staff: list[FrontendBudgetLine]
    recurring: list[FrontendBudgetLine]
    total_eur: float


class FrontendPhase(BaseModel):
    name: str
    days: int


class FrontendPlanData(BaseModel):
    hypothesis: str
    objective: str
    novelty_signal: Literal["not found", "similar work exists", "exact match found"]
    references: list[FrontendReference]
    phases: list[FrontendPhase]
    experiments: list[FrontendExperiment]
    budget: FrontendBudget


# ── Litmus submission schemas ──────────────────────────────────────────────────

class LitmusSubmitRequest(BaseModel):
    """Sent by the React frontend to POST /litmus/submit."""
    hypothesis: str
    experiment_ids: list[str]  # which experiments to submit (by id)
    experiments: list[FrontendExperiment]  # full experiment objects for mapping


class LitmusSubmitResult(BaseModel):
    """Result for a single submitted experiment."""
    experiment_name: str
    experiment_type: str
    litmus_experiment_id: str | None = None
    status: str
    estimated_cost_usd: float | None = None
    estimated_turnaround_days: int | None = None
    error: str | None = None


class LitmusSubmitResponse(BaseModel):
    """Returned to the React frontend after submission."""
    results: list[LitmusSubmitResult]
    total_submitted: int
    total_errors: int

