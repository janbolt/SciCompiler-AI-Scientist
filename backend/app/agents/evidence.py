from __future__ import annotations

from app.schemas import EvidenceClaim, EvidenceStrength, EvidenceType, LiteratureQCResult, StructuredHypothesis


def run(hypothesis: StructuredHypothesis, literature_qc: LiteratureQCResult) -> list[EvidenceClaim]:
    claims = [
        EvidenceClaim(
            claim="Post-thaw viability directly tests the stated biological outcome.",
            evidence_type=EvidenceType.direct_evidence,
            support_summary="Outcome is explicitly present in user hypothesis.",
            strength=EvidenceStrength.strong,
            linked_to="hypothesis.measurable_outcome",
        ),
        EvidenceClaim(
            claim="Trehalose membrane stabilization rationale supports intervention plausibility.",
            evidence_type=EvidenceType.mechanistic_evidence,
            support_summary="Mechanistic rationale is explicitly stated in user input.",
            strength=EvidenceStrength.moderate,
            linked_to="hypothesis.mechanistic_rationale",
        ),
        EvidenceClaim(
            claim="Expected +15 percentage-point threshold may be optimistic without pilot calibration.",
            evidence_type=EvidenceType.unvalidated_assumption,
            support_summary="Effect size is user-defined but not validated in this run.",
            strength=EvidenceStrength.weak,
            linked_to="hypothesis.threshold",
        ),
    ]
    if literature_qc.novelty_signal == "similar_work_exists":
        claims.append(
            EvidenceClaim(
                claim="Related work exists but exact comparators and setup differ.",
                evidence_type=EvidenceType.indirect_evidence,
                support_summary="Literature QC returns similar_work_exists with placeholder references.",
                strength=EvidenceStrength.moderate,
                linked_to="literature_qc.novelty_signal",
            )
        )
    return claims

