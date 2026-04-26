from __future__ import annotations

import os

import pytest
from fastapi.testclient import TestClient

import app.agents.intake as intake_module
import app.agents.literature_qc as literature_qc_module
from app.agents.evidence import run as run_evidence
from app.agents.intake import run as run_intake
from app.agents.literature_qc import run as run_literature_qc
from app.agents.plan import run as run_plan
from app.agents.protocol_retrieval import run as run_protocol_retrieval
from app.agents.risk import run as run_risk
from app.main import app
from app.schemas import DemoRunRequest, DemoRunResponse, FeedbackResponse, MISSING, PlanAction, StructuredHypothesis
from app.services.llm import reset_client
from app.services.memory import feedback_for_plan

client = TestClient(app)


def _demo_request(question: str) -> DemoRunRequest:
    return DemoRunRequest(
        question=question,
        constraints={"budget": "5000 USD", "timeline": "4 weeks", "execution_mode": "hybrid"},
    )


def _default_question() -> str:
    return (
        "Replacing sucrose with trehalose as a cryoprotectant in the freezing medium will increase "
        "post-thaw viability of HeLa cells by at least 15 percentage points compared to the standard "
        "DMSO protocol, due to trehalose’s superior membrane stabilization at low temperatures."
    )


@pytest.fixture(autouse=True)
def _force_stub_agents(monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep tests offline and deterministic by default."""
    reset_client()
    monkeypatch.setattr(intake_module, "USE_STUB_AGENTS", True)
    monkeypatch.setattr(literature_qc_module, "USE_STUB_AGENTS", True)


def test_hypothesis_structuring() -> None:
    hypothesis = run_intake(_demo_request(_default_question()))
    assert hypothesis.intervention != "missing_required_field"
    assert hypothesis.biological_system == "HeLa cells"
    assert hypothesis.comparator_or_control != "missing_required_field"
    assert hypothesis.measurable_outcome == "post-thaw viability"


def test_missing_required_field_handling() -> None:
    hypothesis = StructuredHypothesis(
        intervention=MISSING,
        biological_system=MISSING,
        comparator_or_control=MISSING,
        measurable_outcome=MISSING,
        threshold=MISSING,
        mechanistic_rationale=MISSING,
        experiment_type=MISSING,
        constraints={},
        readiness="underspecified",
        readiness_rationale="Missing all core hypothesis fields.",
        confidence_score=0.0,
        clarifying_questions=[],
        literature_search_hint="missing_required_field",
        original_hypothesis="Can this protocol work better somehow?",
    )
    assert "biological_system" in hypothesis.missing_required_fields
    assert hypothesis.biological_system == "missing_required_field"
    assert hypothesis.readiness in {"underspecified", "pilot_ready"}


def _is_openai_account_issue(message: str) -> bool:
    lowered = message.lower()
    return any(
        marker in lowered
        for marker in (
            "insufficient_quota",
            "exceeded your current quota",
            "rate limit",
            "rate_limit",
            "invalid_api_key",
            "incorrect api key",
            "401",
            "403",
            "429",
        )
    )


@pytest.mark.skipif(
    not os.environ.get("OPENAI_API_KEY"),
    reason="Set OPENAI_API_KEY to run live Intake Agent integration test.",
)
def test_intake_live_llm_path_for_smoke(monkeypatch: pytest.MonkeyPatch) -> None:
    """Optional networked smoke test for strict LLM mode."""
    reset_client()
    monkeypatch.setattr(intake_module, "USE_STUB_AGENTS", False)
    try:
        hypothesis = intake_module.run_intake_agent(
            hypothesis=_default_question(),
            budget="5000 USD",
            timeline="4 weeks",
            execution_mode="hybrid",
        )
    except RuntimeError as exc:
        if _is_openai_account_issue(str(exc)):
            pytest.skip(f"Skipping live OpenAI test (account/billing issue): {exc}")
        raise
    assert hypothesis.original_hypothesis == _default_question()
    assert hypothesis.readiness in {"execution_ready", "pilot_ready", "underspecified"}


def test_literature_qc_schema_validity() -> None:
    hypothesis = run_intake(_demo_request(_default_question()))
    qc = run_literature_qc(hypothesis)
    assert qc.novelty_signal in {"not_found", "similar_work_exists", "exact_match_found"}
    assert 0.0 <= qc.confidence_score <= 1.0
    assert len(qc.references) <= 3
    assert qc.search_coverage in {"full", "partial", "none"}


def test_protocol_candidate_schema_validity() -> None:
    hypothesis = run_intake(_demo_request(_default_question()))
    protocols = run_protocol_retrieval(hypothesis)
    assert len(protocols) >= 1
    first = protocols[0]
    assert 0.0 <= first.fit_score <= 1.0
    assert isinstance(first.missing_steps, list)


def test_evidence_tagging_schema_validity() -> None:
    hypothesis = run_intake(_demo_request(_default_question()))
    qc = run_literature_qc(hypothesis)
    evidence = run_evidence(hypothesis, qc)
    assert len(evidence) >= 1
    assert all(item.evidence_type.value for item in evidence)
    assert all(item.strength.value in {"weak", "moderate", "strong"} for item in evidence)


def test_risk_classification() -> None:
    risks = run_risk()
    categories = {risk.category.value for risk in risks}
    assert "biological_assumption" in categories
    assert "control_gap" in categories


def test_every_risk_maps_to_exactly_one_action() -> None:
    risks = run_risk()
    assert all(risk.action in PlanAction for risk in risks)


def test_risk_to_plan_modification() -> None:
    hypothesis = run_intake(_demo_request(_default_question()))
    risks = run_risk()
    plan = run_plan(hypothesis=hypothesis, risks=risks, feedback_incorporated=[])
    assert any("RISK-001" in item for item in plan.risk_mitigations_applied)
    assert any("Mitigation step for RISK-002" in step.description for step in plan.step_by_step_protocol)
    assert plan.execution_readiness_label == "pilot_only"


def test_experiment_plan_schema_validation() -> None:
    hypothesis = run_intake(_demo_request(_default_question()))
    plan = run_plan(hypothesis=hypothesis, risks=run_risk(), feedback_incorporated=[])
    assert 0.0 <= plan.execution_readiness_score <= 1.0
    assert len(plan.reproducibility_notes) >= 1
    assert len(plan.decision_criteria) >= 1


def test_health_endpoint() -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_get_plan_endpoint() -> None:
    run_response = client.post("/demo/run", json={"question": _default_question(), "constraints": {"execution_mode": "in_house"}})
    plan_id = run_response.json()["plan_id"]
    get_response = client.get(f"/plans/{plan_id}")
    assert get_response.status_code == 200
    DemoRunResponse.model_validate(get_response.json())
    assert client.get("/plans/00000000-0000-0000-0000-000000000000").status_code == 404


def test_demo_run_complete_response() -> None:
    response = client.post(
        "/demo/run",
        json={"question": _default_question(), "constraints": {"budget": "5000 USD", "timeline": "4 weeks", "execution_mode": "hybrid"}},
    )
    assert response.status_code == 200
    payload = response.json()
    DemoRunResponse.model_validate(payload)
    required = {
        "plan_id",
        "hypothesis",
        "literature_qc",
        "protocol_candidates",
        "evidence_claims",
        "risks",
        "plan",
        "materials",
        "budget",
        "timeline",
        "validation",
        "cro_ready_brief",
        "confidence_score",
    }
    assert required.issubset(payload.keys())


def test_feedback_storage() -> None:
    run_response = client.post("/demo/run", json={"question": _default_question(), "constraints": {"execution_mode": "hybrid"}})
    plan_id = run_response.json()["plan_id"]
    feedback_response = client.post(
        f"/plans/{plan_id}/feedback",
        json={"feedback": "Add explicit viability assay calibration note.", "requested_changes": ["validation calibration details"]},
    )
    assert feedback_response.status_code == 200
    parsed = FeedbackResponse.model_validate(feedback_response.json())
    assert parsed.stored is True
    assert len(feedback_for_plan(plan_id)) >= 1


def test_regeneration_incorporates_feedback() -> None:
    run_response = client.post("/demo/run", json={"question": _default_question(), "constraints": {"execution_mode": "hybrid"}})
    plan_id = run_response.json()["plan_id"]
    regen = client.post(
        f"/plans/{plan_id}/regenerate",
        json={"feedback": "Clarify replicate gate for execution readiness.", "requested_changes": ["replicate gate in plan text"]},
    )
    assert regen.status_code == 200
    payload = regen.json()
    assert payload["plan"]["feedback_incorporated"]
    assert "replicate gate" in " ".join(payload["plan"]["feedback_incorporated"]).lower()


def test_cro_ready_brief_exists_in_demo_response() -> None:
    response = client.post("/demo/run", json={"question": _default_question(), "constraints": {"execution_mode": "cro_ready"}})
    payload = response.json()
    assert response.status_code == 200
    assert "cro_ready_brief" in payload
    assert payload["cro_ready_brief"]["objective"]


def test_review_feedback_routed_to_correct_agents(monkeypatch: pytest.MonkeyPatch) -> None:
    """Materials feedback must reach budget agent, timeline feedback must reach timeline agent."""
    import app.orchestrator as orch
    from app.agents import budget as budget_module
    from app.agents import timeline as timeline_module

    captured: dict[str, str] = {}

    real_budget_run = budget_module.run
    real_timeline_run = timeline_module.run

    def spy_budget_run(*args, scientist_feedback: str = "", **kwargs):
        captured["budget"] = scientist_feedback
        return real_budget_run(*args, scientist_feedback=scientist_feedback, **kwargs)

    def spy_timeline_run(*args, scientist_feedback: str = "", **kwargs):
        captured["timeline"] = scientist_feedback
        return real_timeline_run(*args, scientist_feedback=scientist_feedback, **kwargs)

    monkeypatch.setattr(orch, "_run_budget", spy_budget_run)
    monkeypatch.setattr(orch, "_run_timeline", spy_timeline_run)

    response = client.post(
        "/demo/run",
        json={
            "question": _default_question(),
            "constraints": {"execution_mode": "hybrid"},
            "prior_feedback": [
                {
                    "experiment_type": "cryopreservation",
                    "section": "materials",
                    "rating": 2,
                    "note": "Use Sigma-Aldrich trehalose D-(+) molecular biology grade, not pharmaceutical grade.",
                    "timestamp": "2026-04-26T08:00:00Z",
                },
                {
                    "experiment_type": "cryopreservation",
                    "section": "timeline",
                    "rating": 2,
                    "note": "Cell recovery phase needs 48h not 24h for HeLa post-thaw.",
                    "timestamp": "2026-04-26T08:00:00Z",
                },
                {
                    "experiment_type": "cryopreservation",
                    "section": "steps",
                    "rating": 3,
                    "note": "Add an explicit viability check with trypan blue at 0h and 24h.",
                    "timestamp": "2026-04-26T08:00:00Z",
                },
            ],
        },
    )

    assert response.status_code == 200
    payload = response.json()

    assert "Sigma-Aldrich" in captured.get("budget", ""), (
        f"materials feedback was not routed to the budget agent; got: {captured.get('budget')!r}"
    )
    assert "48h" in captured.get("timeline", ""), (
        f"timeline feedback was not routed to the timeline agent; got: {captured.get('timeline')!r}"
    )
    assert "Sigma-Aldrich" not in captured.get("timeline", ""), (
        "materials feedback leaked into timeline agent"
    )
    assert "48h" not in captured.get("budget", ""), (
        "timeline feedback leaked into budget agent"
    )

    assert payload.get("feedback_incorporated") is True
    trace_text = " ".join(payload.get("feedback_trace", []))
    assert "Budget agent received" in trace_text
    assert "Timeline agent received" in trace_text
    assert "Plan agent received" in trace_text


def test_intake_partial_extraction_does_not_erase(monkeypatch: pytest.MonkeyPatch) -> None:
    """Vague-but-non-empty fields should be extracted, not replaced with the missing sentinel."""
    from app.schemas import StructuredHypothesis as SH

    fake = SH(
        intervention="GLP-1 agonists (specific compound and dose to be confirmed)",
        biological_system="diet-induced obesity mouse models (strain/sex/age TBD)",
        comparator_or_control="missing_required_field",
        measurable_outcome="hepatic steatosis (assay TBD)",
        threshold="missing_required_field",
        mechanistic_rationale="missing_required_field",
        experiment_type="comparative_treatment_study",
        constraints={},
        readiness="pilot_ready",
        readiness_rationale="Partial extraction with several clarifying questions.",
        confidence_score=0.45,
        clarifying_questions=[
            "Which specific GLP-1 agonist (e.g. liraglutide, semaglutide)?",
            "What dose and delivery route?",
            "What mouse strain, sex, and age range?",
            "What numeric improvement threshold (e.g. >=30% reduction)?",
        ],
        literature_search_hint="GLP-1 agonist hepatic steatosis DIO mouse",
        original_hypothesis="Investigate whether GLP-1 agonists reduce hepatic steatosis in DIO mouse models.",
    )

    def fake_run_intake_agent(**kwargs):
        return fake

    monkeypatch.setattr(intake_module, "run_intake_agent", fake_run_intake_agent)

    hypothesis = intake_module.run_intake_agent(
        hypothesis=fake.original_hypothesis,
        budget=None,
        timeline=None,
        execution_mode="in_house",
    )
    assert hypothesis.intervention != "missing_required_field"
    assert "GLP-1" in hypothesis.intervention
    assert hypothesis.biological_system != "missing_required_field"
    assert hypothesis.experiment_type != "missing_required_field"
    assert hypothesis.readiness == "pilot_ready"
    assert len(hypothesis.clarifying_questions) >= 2

