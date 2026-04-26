from __future__ import annotations

from app.schemas import ProtocolCandidate, StructuredHypothesis


def run(hypothesis: StructuredHypothesis) -> list[ProtocolCandidate]:
    return [
        ProtocolCandidate(
            protocol_name="Baseline controlled-rate HeLa cryopreservation workflow",
            source_type="atcc_style_method_stub",
            fit_score=0.84,
            confidence=0.78,
            adaptation_notes="Retain baseline cooling/thaw handling while swapping sucrose condition with trehalose arm.",
            missing_steps=["Exact freeze container model", "Cryomedia preparation SOP version"],
            limitations=["Seed protocol only, not a verified proprietary SOP."],
        ),
        ProtocolCandidate(
            protocol_name="Trehalose concentration screen before scale-up",
            source_type="protocols_io_style_stub",
            fit_score=0.73,
            confidence=0.69,
            adaptation_notes="Run pilot concentration sweep to reduce false negatives from poor trehalose dosing.",
            missing_steps=["Exact concentration series", "Plate randomization template"],
            limitations=["Designed as pilot backbone, not final full-scale method."],
        ),
    ]

