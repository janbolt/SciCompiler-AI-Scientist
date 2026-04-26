from __future__ import annotations

import pytest

import app.agents.staffing as staffing_module
from app.agents.staffing import run as run_staffing
from app.schemas import StaffingPlan, StaffingRole


@pytest.fixture(autouse=True)
def _force_stub_agents(monkeypatch: pytest.MonkeyPatch) -> None:
    """Run the staffing agent purely in stub mode so tests stay offline."""
    monkeypatch.setattr(staffing_module, "USE_STUB_AGENTS", True)


def test_staffing_stub_runs() -> None:
    """The stub path must produce a valid StaffingPlan with a positive total cost."""
    result = run_staffing(
        hypothesis=None,
        plan=None,
        timeline=None,
        scientist_feedback="",
    )

    assert isinstance(result, StaffingPlan)
    assert len(result.roles) >= 1
    assert result.total_staffing_cost_eur > 0
    # Per-role totals must equal hours × rate (validator-recomputed).
    for role in result.roles:
        assert role.total_cost_eur == round(
            role.estimated_hours * role.hourly_rate_eur, 2
        )
    # Top-level total must equal sum of per-role totals.
    assert result.total_staffing_cost_eur == round(
        sum(r.total_cost_eur for r in result.roles), 2
    )


def test_staffing_cost_recomputed() -> None:
    """The @model_validator must overwrite obviously-wrong LLM totals."""
    plan = StaffingPlan(
        roles=[
            StaffingRole(
                role_title="Research Associate",
                required_skills=["cell culture"],
                phases_involved=["Pilot run"],
                estimated_hours=10.0,
                hourly_rate_eur=40.0,
                total_cost_eur=99999.0,  # intentionally wrong
            ),
            StaffingRole(
                role_title="Scientist",
                required_skills=["data analysis"],
                phases_involved=["Analysis"],
                estimated_hours=5.0,
                hourly_rate_eur=60.0,
                total_cost_eur=12345.0,  # intentionally wrong
            ),
        ],
        minimum_team_size=1,
        recommended_team_size=2,
        can_single_person_execute=True,
        total_staffing_cost_eur=88888.0,  # intentionally wrong
        cro_delegation_recommendation="Outsource flow cytometry phase to BioCRO.",
        staffing_notes="No biosafety concerns at BSL-1.",
    )

    # Per-role totals must be hours × rate, not the wrong 99999/12345 values.
    assert plan.roles[0].total_cost_eur == round(10.0 * 40.0, 2)  # 400.0
    assert plan.roles[1].total_cost_eur == round(5.0 * 60.0, 2)  # 300.0
    # Top-level total must be the sum of recomputed per-role totals.
    assert plan.total_staffing_cost_eur == round(400.0 + 300.0, 2)  # 700.0
