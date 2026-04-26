from __future__ import annotations

from app.schemas import TimelineEstimate, TimelinePhase


def run() -> TimelineEstimate:
    return TimelineEstimate(
        phases=[
            TimelinePhase(
                phase_name="Protocol finalization and reagent verification",
                duration_estimate="3 days",
                dependencies=[],
                responsible_role="Research associate",
                risk_buffer="1 day",
                bottlenecks=["Supplier confirmation"],
            ),
            TimelinePhase(
                phase_name="Pilot cryopreservation run",
                duration_estimate="5 days",
                dependencies=["Protocol finalization and reagent verification"],
                responsible_role="Scientist",
                risk_buffer="2 days",
                bottlenecks=["Cryomedia concentration tuning"],
            ),
            TimelinePhase(
                phase_name="Replicate confirmation run",
                duration_estimate="7 days",
                dependencies=["Pilot cryopreservation run"],
                responsible_role="Scientist",
                risk_buffer="2 days",
                bottlenecks=["Biological replicate scheduling"],
            ),
            TimelinePhase(
                phase_name="Analysis and review gate",
                duration_estimate="3 days",
                dependencies=["Replicate confirmation run"],
                responsible_role="PI",
                risk_buffer="1 day",
                bottlenecks=["Statistical review turnaround"],
            ),
        ],
        total_duration_estimate="21 days (including risk buffers)",
    )

