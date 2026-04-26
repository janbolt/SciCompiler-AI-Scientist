from __future__ import annotations

from fastapi.testclient import TestClient

from app.agents import intake_agent, literature_qc_agent, plan_agent, risk_agent
from app.main import app
from app.schemas import DemoRunRequest, DemoRunResponse, PlanAction, StructuredHypothesis


client = TestClient(app)


def _request(question: str) -> DemoRunRequest:
    return DemoRunRequest(
        question=question,
        constraints={"budget": "5000 USD", "timeline": "4 weeks", "execution_mode": "in_house"},
    )


def test_hypothesis_structuring() -> None:
    hypothesis = intake_agent(
        _request(
            "Replacing sucrose with trehalose as a cryoprotectant in the freezing medium "
            "will increase post-thaw viability of HeLa cells by at least 15 percentage points "
            "compared to the standard DMSO protocol, due to trehalose membrane stabilization."
        )
    )
    assert hypothesis.organism_or_model == "HeLa cells"
    assert hypothesis.expected_effect_size != "missing_required_field"


def test_literature_qc_schema_validity() -> None:
    hypothesis = intake_agent(_request("Trehalose improves HeLa post-thaw viability versus DMSO."))
    qc = literature_qc_agent(hypothesis)
    assert 0.0 <= qc.confidence <= 1.0
    assert qc.novelty_signal.value in {"not_found", "similar_work_exists", "exact_match_found"}


def test_risk_classification() -> None:
    hypothesis = intake_agent(_request("Trehalose improves HeLa post-thaw viability versus DMSO."))
    risks = risk_agent(hypothesis, [])
    categories = {risk.category.value for risk in risks}
    assert "biological_assumptions" in categories
    assert all(r.plan_action in PlanAction for r in risks)


def test_risk_to_plan_modification() -> None:
    hypothesis = intake_agent(_request("Trehalose improves HeLa post-thaw viability versus DMSO."))
    risks = risk_agent(hypothesis, [])
    plan = plan_agent(plan_id="p1", hypothesis=hypothesis, risks=risks, feedback_notes=None)
    assert any("R1" in mitigation for mitigation in plan.risk_mitigations_applied)
    assert any("Mitigation step" in step.description for step in plan.step_by_step_protocol)


def test_experiment_plan_schema_validation() -> None:
    hypothesis = StructuredHypothesis(
        raw_input="x",
        organism_or_model="HeLa cells",
        intervention="trehalose arm",
        outcome="higher viability",
        measurable_endpoint="viability",
        expected_effect_size="15 percentage points",
        mechanism="membrane stabilization",
        control_condition="DMSO",
        experiment_type="cell_freezing_cryopreservation",
        missing_fields=[],
    )
    plan = plan_agent(plan_id="plan-schema", hypothesis=hypothesis, risks=[], feedback_notes=[])
    assert plan.id == "plan-schema"
    assert len(plan.step_by_step_protocol) >= 1


def test_missing_required_field_handling() -> None:
    hypothesis = intake_agent(_request("Test if this idea works better somehow."))
    assert "organism_or_model" in hypothesis.missing_fields
    assert hypothesis.organism_or_model == "missing_required_field"


def test_demo_run_complete_response() -> None:
    response = client.post(
        "/demo/run",
        json={
            "question": (
                "Replacing sucrose with trehalose as a cryoprotectant in the freezing medium "
                "will increase post-thaw viability of HeLa cells by at least 15 percentage points "
                "compared to the standard DMSO protocol, due to trehalose membrane stabilization."
            ),
            "constraints": {"budget": "5000 USD", "timeline": "4 weeks", "execution_mode": "hybrid"},
        },
    )
    assert response.status_code == 200
    payload = response.json()
    DemoRunResponse.model_validate(payload)
    expected_keys = {
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
    assert expected_keys.issubset(payload.keys())

