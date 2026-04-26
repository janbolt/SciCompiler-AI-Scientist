from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field, model_validator


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


class EvidenceStrength(str, Enum):
    weak = "weak"
    moderate = "moderate"
    strong = "strong"


class RiskCategory(str, Enum):
    biological_assumption = "biological_assumption"
    technical_assumption = "technical_assumption"
    model_system_risk = "model_system_risk"
    assay_readout_mismatch = "assay_readout_mismatch"
    confounder = "confounder"
    false_positive_risk = "false_positive_risk"
    false_negative_risk = "false_negative_risk"
    control_gap = "control_gap"
    replication_gap = "replication_gap"
    safety_or_compliance = "safety_or_compliance"


class PlanAction(str, Enum):
    document_only = "document_only"
    modify_plan = "modify_plan"
    downgrade_to_pilot = "downgrade_to_pilot"
    block_execution = "block_execution"


class ConfidenceLevel(str, Enum):
    low = "low"
    medium = "medium"
    high = "high"


class RiskSeverity(str, Enum):
    low = "low"
    medium = "medium"
    high = "high"
    critical = "critical"


class RiskLikelihood(str, Enum):
    low = "low"
    medium = "medium"
    high = "high"


MISSING = "missing_required_field"
MissingRequiredField = Literal["missing_required_field"]
ReadinessLevel = Literal["execution_ready", "pilot_ready", "underspecified"]


class RunConstraints(BaseModel):
    budget: str | MissingRequiredField = "missing_required_field"
    timeline: str | MissingRequiredField = "missing_required_field"
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


_CORE_HYPOTHESIS_FIELDS: tuple[str, ...] = (
    "intervention",
    "biological_system",
    "comparator_or_control",
    "measurable_outcome",
    "threshold",
    "mechanistic_rationale",
    "experiment_type",
)


class StructuredHypothesis(BaseModel):
    intervention: str
    biological_system: str
    comparator_or_control: str
    measurable_outcome: str
    threshold: str
    mechanistic_rationale: str
    experiment_type: str
    constraints: dict[str, str] = Field(default_factory=dict)
    readiness: ReadinessLevel
    readiness_rationale: str
    confidence_score: float = Field(ge=0.0, le=1.0)
    clarifying_questions: list[str] = Field(default_factory=list)
    literature_search_hint: str

    original_hypothesis: str = ""
    missing_required_fields: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def _compute_missing_required_fields(self) -> "StructuredHypothesis":
        self.missing_required_fields = [
            name for name in _CORE_HYPOTHESIS_FIELDS if getattr(self, name) == MISSING
        ]
        return self


class ReferenceItem(BaseModel):
    title: str
    source_type: Literal["placeholder_seed_reference", "verified_reference"]
    source: str
    note: str
    url: str | None = None


class ProtocolReference(BaseModel):
    title: str
    protocol_url: str
    authors: list[str] = Field(default_factory=list)
    published_year: int | None = None
    match_type: Literal["full_scope", "intervention_only", "system_method", "stub"]
    relevance_note: str
    is_stub: bool = False


class LiteratureQCResult(BaseModel):
    novelty_signal: Literal["not_found", "similar_work_exists", "exact_match_found"]
    references: list[ProtocolReference] = Field(default_factory=list)
    confidence_score: float = Field(ge=0.0, le=1.0)
    explanation: str
    recommended_action: str
    search_coverage: Literal["full", "partial", "none"]


class ProtocolCandidate(BaseModel):
    protocol_name: str
    source_type: str
    fit_score: float = Field(ge=0.0, le=1.0)
    confidence: float = Field(ge=0.0, le=1.0)
    adaptation_notes: str
    missing_steps: list[str]
    limitations: list[str]
    raw_steps: list[str] = Field(default_factory=list)
    protocol_url: str = ""


class EvidenceClaim(BaseModel):
    claim: str
    evidence_type: EvidenceType
    support_summary: str
    strength: EvidenceStrength
    linked_to: str


class RiskItem(BaseModel):
    risk_id: str
    category: RiskCategory
    description: str
    severity: RiskSeverity
    likelihood: RiskLikelihood
    mitigation: str
    action: PlanAction


class ProtocolStep(BaseModel):
    step_number: int
    description: str
    linked_to: str


class ExperimentPlan(BaseModel):
    objective: str
    experimental_design: str
    controls: list[str]
    step_by_step_protocol: list[ProtocolStep]
    assumptions: list[str]
    decision_criteria: list[str]
    risk_mitigations_applied: list[str]
    reproducibility_notes: list[str]
    execution_readiness_score: float = Field(ge=0.0, le=1.0)
    execution_readiness_label: Literal["execution_ready_after_review", "pilot_only", "blocked_pending_expert_review"]
    feedback_incorporated: list[str] = Field(default_factory=list)


class MaterialItem(BaseModel):
    item_name: str
    supplier: str
    catalog_number: str | Literal["verify_before_ordering"] | None = None
    quantity: str
    confidence: ConfidenceLevel
    uncertainty_note: str | None = None


class BudgetLineItem(BaseModel):
    item_name: str
    quantity: str
    unit_cost_estimate: float
    total_cost_estimate: float
    confidence: ConfidenceLevel
    uncertainty_note: str | None = None


class BudgetEstimate(BaseModel):
    currency: str = "USD"
    line_items: list[BudgetLineItem]
    estimated_total_cost: float
    uncertainty_notes: list[str]


class TimelinePhase(BaseModel):
    phase_name: str
    duration_estimate: str
    dependencies: list[str]
    responsible_role: str
    risk_buffer: str
    bottlenecks: list[str]


class TimelineEstimate(BaseModel):
    phases: list[TimelinePhase]
    total_duration_estimate: str


class ValidationPlan(BaseModel):
    primary_endpoint: str
    secondary_endpoints: list[str]
    success_threshold: str
    failure_conditions: list[str]
    suggested_statistical_comparison: str
    minimum_replicates_or_design_note: str


class CROReadyBrief(BaseModel):
    objective: str
    scope_of_work: list[str]
    sample_count: str
    required_assays: list[str]
    deliverables: list[str]
    qc_requirements: list[str]
    timeline_request: str
    materials_responsibility: str
    questions_for_cro: list[str]


class DemoRunResponse(BaseModel):
    plan_id: str
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


class FeedbackRequest(BaseModel):
    feedback: str
    requested_changes: list[str] = Field(default_factory=list)
    section: str = "overall_plan"
    severity: Literal["low", "medium", "high"] = "medium"


class FeedbackResponse(BaseModel):
    plan_id: str
    stored: bool
    feedback_summary: str


class FeedbackRecord(BaseModel):
    plan_id: str
    feedback: str
    requested_changes: list[str]
    section: str
    severity: Literal["low", "medium", "high"]
    created_at: datetime


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
    confidence_score: float = Field(default=0.0, ge=0.0, le=1.0)


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

