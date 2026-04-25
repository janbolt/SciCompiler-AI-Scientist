from __future__ import annotations
from typing import Literal, Optional
from pydantic import BaseModel, Field
from uuid import UUID, uuid4
from datetime import datetime


class Reference(BaseModel):
    id: str
    title: str
    authors: list[str] = []
    year: Optional[int] = None
    doi: Optional[str] = None
    url: Optional[str] = None
    source: Optional[str] = None


class Hypothesis(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    raw_input: str
    organism_or_model: Optional[str] = None
    intervention: Optional[str] = None
    outcome: Optional[str] = None
    measurable_endpoint: Optional[str] = None
    expected_effect_size: Optional[str] = None
    mechanism: Optional[str] = None
    control_condition: Optional[str] = None
    experiment_type: Optional[str] = None
    constraints: dict = {}
    missing_fields: list[str] = []


NoveltySignal = Literal["not_found", "similar_work_exists", "exact_match_found"]


class LiteratureQCResult(BaseModel):
    novelty_signal: NoveltySignal
    confidence: float
    relevant_references: list[Reference] = []
    explanation: str
    recommended_action: str


class ProtocolCandidate(BaseModel):
    id: str
    title: str
    source: str
    url: Optional[str] = None
    match_score: float
    missing_steps: list[str] = []
    adaptation_need: str
    confidence: float


EvidenceType = Literal[
    "direct", "indirect", "correlative", "mechanistic", "contradictory", "unvalidated_assumption"
]


class EvidenceClaim(BaseModel):
    claim: str
    evidence_type: EvidenceType
    source_ids: list[str] = []
    strength: Literal["weak", "moderate", "strong"]
    relevance_to_plan: str


Severity = Literal["low", "moderate", "high", "critical"]
PlanAction = Literal["document_only", "modify_plan", "downgrade_to_pilot", "block_execution"]


class RiskItem(BaseModel):
    risk_id: str
    category: str
    description: str
    severity: Severity
    probability: float
    impact: str
    required_mitigation: str
    plan_action: PlanAction


class ProtocolStep(BaseModel):
    order: int
    title: str
    description: str
    duration_min: Optional[int] = None
    notes: Optional[str] = None


class MaterialItem(BaseModel):
    name: str
    supplier: Optional[str] = None
    catalog_number: Optional[str] = None
    quantity: Optional[str] = None
    notes: Optional[str] = None
    verified: bool = False


class BudgetItem(BaseModel):
    item_name: str
    supplier: Optional[str] = None
    catalog_number: Optional[str] = None
    quantity: float = 1
    unit_cost: float = 0
    total_cost: float = 0
    confidence: Literal["low", "medium", "high"] = "low"
    source: Optional[str] = None


class BudgetEstimate(BaseModel):
    items: list[BudgetItem] = []
    currency: str = "USD"
    total: float = 0


class TimelinePhase(BaseModel):
    name: str
    duration_days: int
    dependencies: list[str] = []
    responsible_role: Optional[str] = None
    risk_buffer_days: int = 0


class Timeline(BaseModel):
    phases: list[TimelinePhase] = []


class ValidationPlan(BaseModel):
    primary_endpoint: str
    secondary_endpoints: list[str] = []
    positive_control: Optional[str] = None
    negative_control: Optional[str] = None
    statistical_test: Optional[str] = None
    success_threshold: Optional[str] = None
    failure_conditions: list[str] = []


PlanMode = Literal["in_house", "cro_ready", "hybrid"]


class ExperimentPlan(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    title: str
    objective: str
    plan_mode: PlanMode = "in_house"
    protocol_steps: list[ProtocolStep] = []
    materials: list[MaterialItem] = []
    budget: BudgetEstimate = BudgetEstimate()
    timeline: Timeline = Timeline()
    validation: Optional[ValidationPlan] = None
    controls: list[str] = []
    risks: list[RiskItem] = []
    assumptions: list[str] = []
    decision_tree: Optional[dict] = None
    confidence_score: float = 0.0


class ScientistFeedback(BaseModel):
    plan_id: UUID
    section: Literal["protocol", "materials", "budget", "timeline", "validation", "risk", "overall"]
    original_text: str
    correction: str
    reason: Optional[str] = None
    experiment_type: Optional[str] = None
    domain_tags: list[str] = []
    severity: Severity = "moderate"


class GenerationRun(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    project_id: UUID
    input_hash: str
    model_provider: str
    model_name: str
    prompt_version: str
    output_version: str
    created_at: datetime = Field(default_factory=datetime.utcnow)
    latency_ms: int = 0
    status: Literal["ok", "error", "partial"] = "ok"


class DemoRunInput(BaseModel):
    scientific_question: str
    constraints: dict = {}


class DemoRunOutput(BaseModel):
    hypothesis: Hypothesis
    literature_qc: LiteratureQCResult
    protocol_candidates: list[ProtocolCandidate]
    evidence_claims: list[EvidenceClaim]
    risks: list[RiskItem]
    plan: ExperimentPlan
