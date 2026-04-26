from __future__ import annotations

from datetime import UTC, datetime
import uuid

from app.agents.budget import run as _run_budget
from app.agents.cro import run as _run_cro
from app.agents.evidence import run as _run_evidence
from app.agents.intake import run_intake_agent as _run_intake_agent
from app.agents.literature_qc import run_literature_qc_agent as _run_literature_qc_agent
from app.agents.plan import run as _run_plan
from app.agents.protocol_retrieval import run as _run_protocol_retrieval
from app.agents.risk import run as _run_risk
from app.agents.timeline import run as _run_timeline
from app.agents.validation import run as _run_validation
from app.schemas import (
    DemoRunRequest,
    DemoRunResponse,
    FeedbackRecord,
    FeedbackRequest,
    FeedbackResponse,
    StructuredHypothesis,
)
from app.services.memory import (
    feedback_for_plan,
    load_plan,
    retrieve_prior_feedback,
    save_plan,
    store_feedback_record,
)


AGENT_ORDER = [
    "hypothesis",
    "literature_qc",
    "protocol_candidates",
    "evidence_claims",
    "risks",
    "plan",
    "budget",
    "timeline",
    "validation",
    "cro_ready_brief",
]

AGENT_DEPENDENCIES = {
    "hypothesis": [],
    "literature_qc": ["hypothesis"],
    "protocol_candidates": ["hypothesis", "literature_qc"],
    "evidence_claims": ["hypothesis", "literature_qc", "protocol_candidates"],
    "risks": ["hypothesis", "literature_qc", "protocol_candidates", "evidence_claims"],
    "plan": ["hypothesis", "literature_qc", "protocol_candidates", "evidence_claims", "risks"],
    "budget": ["hypothesis", "plan"],
    "timeline": ["hypothesis", "plan", "budget"],
    "validation": ["hypothesis", "plan"],
    "cro_ready_brief": ["hypothesis", "plan", "budget", "timeline", "validation"],
}


def _scientist_feedback_block(scientist_feedback: str) -> str:
    if not scientist_feedback:
        return ""
    return (
        "SCIENTIST FEEDBACK ON THIS SECTION:\n"
        f"{scientist_feedback}\n\n"
        "You MUST address every point in this feedback in your output.\n"
        "If you cannot fully address an item, state explicitly what was "
        "addressed and what was not, and why."
    )


def _inject_context_into_hypothesis(
    hypothesis: StructuredHypothesis,
    prior_context: str = "",
    scientist_feedback: str = "",
) -> StructuredHypothesis:
    blocks = [b for b in [prior_context, _scientist_feedback_block(scientist_feedback)] if b]
    if not blocks:
        return hypothesis
    merged = "\n\n".join(blocks)
    return hypothesis.model_copy(
        update={
            "literature_search_hint": f"{hypothesis.literature_search_hint}\n\n{merged}".strip(),
            "mechanistic_rationale": f"{hypothesis.mechanistic_rationale}\n\n{merged}".strip(),
        }
    )


def _build_prior_context(hypothesis: StructuredHypothesis, section: str) -> str:
    prior = retrieve_prior_feedback(hypothesis, section=section)
    if not prior:
        return ""
    return (
        "PRIOR SCIENTIST CORRECTIONS FOR SIMILAR EXPERIMENTS:\n"
        "A scientist has previously flagged these specific issues on similar "
        f"{hypothesis.experiment_type} experiments. You MUST implement each "
        "correction below in your output unless it directly contradicts the "
        "current hypothesis:\n"
        + "\n".join(f"{i + 1}. {c}" for i, c in enumerate(prior))
    )


def run_intake_agent(
    hypothesis: str,
    budget: str | None = None,
    timeline: str | None = None,
    execution_mode: str | None = None,
    prior_context: str = "",
    scientist_feedback: str = "",
):
    merged_hypothesis = hypothesis
    if prior_context:
        merged_hypothesis = f"{merged_hypothesis}\n\n{prior_context}"
    if scientist_feedback:
        merged_hypothesis = f"{merged_hypothesis}\n\n{_scientist_feedback_block(scientist_feedback)}"
    return _run_intake_agent(
        hypothesis=merged_hypothesis,
        budget=budget,
        timeline=timeline,
        execution_mode=execution_mode,
    )


def run_literature_qc_agent(
    hypothesis: StructuredHypothesis,
    prior_context: str = "",
    scientist_feedback: str = "",
):
    return _run_literature_qc_agent(
        _inject_context_into_hypothesis(
            hypothesis,
            prior_context=prior_context,
            scientist_feedback=scientist_feedback,
        )
    )


def run_protocol_retrieval_agent(
    hypothesis: StructuredHypothesis,
    literature_qc=None,
    prior_context: str = "",
    scientist_feedback: str = "",
):
    candidates = _run_protocol_retrieval(
        _inject_context_into_hypothesis(
            hypothesis,
            prior_context=prior_context,
            scientist_feedback=scientist_feedback,
        )
    )
    return candidates, []


def run_evidence_agent(
    hypothesis: StructuredHypothesis,
    protocol_candidates,
    prior_context: str = "",
    scientist_feedback: str = "",
):
    _ = protocol_candidates
    return _run_evidence(
        _inject_context_into_hypothesis(
            hypothesis,
            prior_context=prior_context,
            scientist_feedback=scientist_feedback,
        ),
        protocol_candidates,
    )


def run_risk_agent(
    hypothesis: StructuredHypothesis,
    evidence_claims,
    prior_context: str = "",
    scientist_feedback: str = "",
):
    _ = evidence_claims
    return _run_risk(
        _inject_context_into_hypothesis(
            hypothesis,
            prior_context=prior_context,
            scientist_feedback=scientist_feedback,
        ),
        evidence_claims,
    )


def run_plan_agent(
    hypothesis: StructuredHypothesis,
    literature_qc,
    protocol_candidates,
    evidence_claims,
    risks,
    prior_context: str = "",
    scientist_feedback: str = "",
):
    _ = evidence_claims
    feedback_incorporated: list[str] = []
    if prior_context:
        feedback_incorporated.append(prior_context)
    if scientist_feedback:
        feedback_incorporated.append(_scientist_feedback_block(scientist_feedback))
    return _run_plan(
        _inject_context_into_hypothesis(hypothesis),
        risks,
        feedback_incorporated=feedback_incorporated,
        protocol_candidates=protocol_candidates,
        literature_qc=literature_qc,
    )


def run_budget_agent(
    hypothesis: StructuredHypothesis,
    plan,
    prior_context: str = "",
    scientist_feedback: str = "",
):
    combined_feedback_parts: list[str] = []
    if prior_context:
        combined_feedback_parts.append(prior_context)
    if scientist_feedback:
        combined_feedback_parts.append(scientist_feedback)
    combined_feedback = "\n\n".join(combined_feedback_parts)
    return _run_budget(
        hypothesis,
        plan,
        scientist_feedback=combined_feedback,
    )


def run_timeline_agent(
    hypothesis: StructuredHypothesis,
    plan,
    budget,
    prior_context: str = "",
    scientist_feedback: str = "",
):
    _ = budget
    combined_feedback_parts: list[str] = []
    if prior_context:
        combined_feedback_parts.append(prior_context)
    if scientist_feedback:
        combined_feedback_parts.append(scientist_feedback)
    combined_feedback = "\n\n".join(combined_feedback_parts)
    return _run_timeline(
        hypothesis,
        plan,
        scientist_feedback=combined_feedback,
    )


def run_validation_agent(
    hypothesis: StructuredHypothesis,
    plan,
    prior_context: str = "",
    scientist_feedback: str = "",
):
    _ = plan
    return _run_validation(
        _inject_context_into_hypothesis(
            hypothesis,
            prior_context=prior_context,
            scientist_feedback=scientist_feedback,
        )
    )


def run_cro_agent(
    hypothesis: StructuredHypothesis,
    plan,
    budget,
    timeline,
    validation,
    prior_context: str = "",
    scientist_feedback: str = "",
):
    _ = (hypothesis, budget, validation, prior_context, scientist_feedback)
    return _run_cro(plan, timeline)


def _confidence_score(protocol_conf: float, readiness_score: float) -> float:
    return round((protocol_conf + readiness_score) / 2.0, 2)


def get_rerun_set(annotated_sections: list[str]) -> list[str]:
    if not annotated_sections:
        return []
    valid = [s for s in annotated_sections if s in AGENT_ORDER]
    if not valid:
        return []
    earliest_index = min(AGENT_ORDER.index(s) for s in valid)
    return AGENT_ORDER[earliest_index:]


# Map the frontend's review section names (set in ReviewPanel.tsx) to the
# backend agent stage that actually owns that section.
#   steps     → plan agent (protocol_steps come from the plan agent)
#   materials → budget agent (materials list lives on the budget output)
#   timeline  → timeline agent
# Anything else falls back to the plan agent so the feedback isn't silently
# dropped.
FRONTEND_SECTION_TO_AGENT: dict[str, str] = {
    "steps": "plan",
    "materials": "budget",
    "timeline": "timeline",
    "plan": "plan",
    "budget": "budget",
}


def _route_prior_feedback(prior_feedback) -> dict[str, list[str]]:
    """Group request.prior_feedback into per-agent scientist_feedback strings.

    Returns a dict keyed by agent stage name (matches AGENT_ORDER values used
    in the orchestrator wrappers) with a list of formatted feedback notes.
    """
    routed: dict[str, list[str]] = {}
    for fb in prior_feedback or []:
        if not fb.note or not fb.note.strip():
            continue
        agent = FRONTEND_SECTION_TO_AGENT.get(fb.section, "plan")
        routed.setdefault(agent, []).append(
            f"{fb.experiment_type} › {fb.section} (rating {fb.rating}/5): {fb.note.strip()}"
        )
    return routed


def run_demo_pipeline(request: DemoRunRequest, plan_id: str | None = None) -> DemoRunResponse:
    hypothesis = run_intake_agent(
        hypothesis=request.question,
        budget=None if request.constraints.budget == "missing_required_field" else request.constraints.budget,
        timeline=None if request.constraints.timeline == "missing_required_field" else request.constraints.timeline,
        execution_mode=request.constraints.execution_mode.value,
    )

    literature_qc = run_literature_qc_agent(
        hypothesis,
        prior_context=_build_prior_context(hypothesis, section="literature_qc"),
    )
    protocol_candidates, _procedures = run_protocol_retrieval_agent(
        hypothesis,
        literature_qc,
        prior_context=_build_prior_context(hypothesis, section="protocol_candidates"),
    )
    evidence_claims = run_evidence_agent(
        hypothesis,
        literature_qc,
        prior_context=_build_prior_context(hypothesis, section="evidence_claims"),
    )
    risks = run_risk_agent(
        hypothesis,
        literature_qc,
        prior_context=_build_prior_context(hypothesis, section="risks"),
    )

    resolved_plan_id = plan_id or str(uuid.uuid4())
    prior_feedback_for_plan = feedback_for_plan(resolved_plan_id)
    plan_feedback_notes_legacy = [
        f"{item.feedback} | requested: {', '.join(item.requested_changes) if item.requested_changes else 'none'}"
        for item in prior_feedback_for_plan
    ]

    # Group incoming review notes by the agent that actually owns each
    # section so feedback from the ReviewPanel's "materials" / "timeline" /
    # "steps" widgets reaches the right LLM.
    routed_feedback = _route_prior_feedback(request.prior_feedback)

    feedback_trace: list[str] = []

    plan_feedback_lines = list(plan_feedback_notes_legacy) + routed_feedback.get("plan", [])
    if plan_feedback_lines:
        feedback_trace.append(
            f"Plan agent received {len(plan_feedback_lines)} scientist note(s)."
        )

    plan = run_plan_agent(
        hypothesis,
        literature_qc,
        protocol_candidates,
        evidence_claims,
        risks,
        prior_context=_build_prior_context(hypothesis, section="plan"),
        scientist_feedback="\n".join(plan_feedback_lines),
    )

    budget_feedback_lines = routed_feedback.get("budget", [])
    if budget_feedback_lines:
        feedback_trace.append(
            f"Budget agent received {len(budget_feedback_lines)} scientist note(s) "
            "addressing materials / cost."
        )
    materials, budget = run_budget_agent(
        hypothesis,
        plan,
        prior_context=_build_prior_context(hypothesis, section="budget"),
        scientist_feedback="\n".join(budget_feedback_lines),
    )

    timeline_feedback_lines = routed_feedback.get("timeline", [])
    if timeline_feedback_lines:
        feedback_trace.append(
            f"Timeline agent received {len(timeline_feedback_lines)} scientist note(s) "
            "addressing duration / phasing."
        )
    timeline = run_timeline_agent(
        hypothesis,
        plan,
        budget,
        prior_context=_build_prior_context(hypothesis, section="timeline"),
        scientist_feedback="\n".join(timeline_feedback_lines),
    )

    validation = run_validation_agent(
        hypothesis,
        plan,
        prior_context=_build_prior_context(hypothesis, section="validation"),
    )
    cro_ready_brief = run_cro_agent(
        hypothesis,
        plan,
        budget,
        timeline,
        validation,
        prior_context=_build_prior_context(hypothesis, section="cro_ready_brief"),
    )

    real_protocol_candidates = [c for c in protocol_candidates if c.source_type != "stub"]
    avg_protocol_conf = (
        sum(item.confidence for item in real_protocol_candidates) / len(real_protocol_candidates)
        if real_protocol_candidates
        else literature_qc.confidence_score
    )

    feedback_was_incorporated = bool(plan_feedback_lines or budget_feedback_lines or timeline_feedback_lines)
    response = DemoRunResponse(
        plan_id=resolved_plan_id,
        hypothesis=hypothesis,
        literature_qc=literature_qc,
        protocol_candidates=protocol_candidates,
        evidence_claims=evidence_claims,
        risks=risks,
        plan=plan,
        materials=materials,
        budget=budget,
        timeline=timeline,
        validation=validation,
        cro_ready_brief=cro_ready_brief,
        confidence_score=_confidence_score(
            protocol_conf=avg_protocol_conf,
            readiness_score=plan.execution_readiness_score,
        ),
        feedback_incorporated=feedback_was_incorporated,
        feedback_trace=feedback_trace,
    )
    save_plan(resolved_plan_id, {"request": request.model_dump(mode="json"), "response": response.model_dump(mode="json")})
    return response


def store_scientist_feedback(plan_id: str, payload: FeedbackRequest) -> FeedbackResponse:
    record = FeedbackRecord(
        plan_id=plan_id,
        feedback=payload.feedback,
        requested_changes=payload.requested_changes,
        section=payload.section or "overall_plan",
        severity=payload.severity,
        created_at=datetime.now(UTC),
    )
    store_feedback_record(record)
    summary = payload.feedback
    if payload.requested_changes:
        summary = f"{payload.feedback} | requested_changes={len(payload.requested_changes)}"
    return FeedbackResponse(plan_id=plan_id, stored=True, feedback_summary=summary)


def get_saved_plan(plan_id: str) -> DemoRunResponse | None:
    stored = load_plan(plan_id)
    if stored is None:
        return None
    return DemoRunResponse.model_validate(stored["response"])


def regenerate_plan(plan_id: str, payload: FeedbackRequest | None = None) -> DemoRunResponse | None:
    stored_plan = load_plan(plan_id)
    if stored_plan is None:
        return None
    if payload is not None:
        store_feedback_record(
            FeedbackRecord(
                plan_id=plan_id,
                feedback=payload.feedback,
                requested_changes=payload.requested_changes,
                section=payload.section or "overall_plan",
                severity=payload.severity,
                created_at=datetime.now(UTC),
            )
        )
    request = DemoRunRequest.model_validate(stored_plan["request"])
    return run_demo_pipeline(request=request, plan_id=plan_id)


def selective_regenerate(
    existing_plan: DemoRunResponse,
    hypothesis: StructuredHypothesis,
    rerun_set: list[str],
    feedback_map: dict[str, str],
) -> tuple[DemoRunResponse, list[str]]:
    plan_data = existing_plan.model_dump()
    feedback_trace: list[str] = []

    current = {
        "hypothesis": existing_plan.hypothesis,
        "literature_qc": existing_plan.literature_qc,
        "protocol_candidates": existing_plan.protocol_candidates,
        "evidence_claims": existing_plan.evidence_claims,
        "risks": existing_plan.risks,
        "plan": existing_plan.plan,
        "budget": existing_plan.budget,
        "timeline": existing_plan.timeline,
        "validation": existing_plan.validation,
        "cro_ready_brief": existing_plan.cro_ready_brief,
    }

    for section in AGENT_ORDER:
        if section not in rerun_set:
            continue

        fb = feedback_map.get(section, "")
        trace_suffix = f": {fb[:100]}" if fb else ""

        if section == "hypothesis":
            req = existing_plan.hypothesis
            result = run_intake_agent(
                hypothesis=req.original_hypothesis,
                budget=req.constraints.get("budget"),
                timeline=req.constraints.get("timeline"),
                execution_mode=req.constraints.get("execution_mode"),
                scientist_feedback=fb,
            )
            current["hypothesis"] = result
            plan_data["hypothesis"] = result.model_dump()
            feedback_trace.append(f"Intake Agent re-ran{trace_suffix}")

        elif section == "literature_qc":
            result = run_literature_qc_agent(current["hypothesis"], scientist_feedback=fb)
            current["literature_qc"] = result
            plan_data["literature_qc"] = result.model_dump()
            feedback_trace.append(f"Literature QC Agent re-ran{trace_suffix}")

        elif section == "protocol_candidates":
            candidates, procedures = run_protocol_retrieval_agent(
                current["hypothesis"], current["literature_qc"], scientist_feedback=fb
            )
            current["protocol_candidates"] = candidates
            plan_data["protocol_candidates"] = [c.model_dump() for c in candidates]
            if procedures:
                plan_data["required_procedures"] = [p.model_dump() for p in procedures]
            feedback_trace.append(f"Protocol Retrieval Agent re-ran{trace_suffix}")

        elif section == "evidence_claims":
            result = run_evidence_agent(
                current["hypothesis"], current["literature_qc"], scientist_feedback=fb
            )
            current["evidence_claims"] = result
            plan_data["evidence_claims"] = [e.model_dump() for e in result]
            feedback_trace.append(f"Evidence Agent re-ran{trace_suffix}")

        elif section == "risks":
            result = run_risk_agent(
                current["hypothesis"], current["literature_qc"], scientist_feedback=fb
            )
            current["risks"] = result
            plan_data["risks"] = [r.model_dump() for r in result]
            feedback_trace.append(f"Risk Agent re-ran{trace_suffix}")

        elif section == "plan":
            result = run_plan_agent(
                current["hypothesis"],
                current["literature_qc"],
                current["protocol_candidates"],
                current["evidence_claims"],
                current["risks"],
                scientist_feedback=fb,
            )
            current["plan"] = result
            plan_data["plan"] = result.model_dump()
            feedback_trace.append(f"Plan Agent re-ran{trace_suffix}")

        elif section == "budget":
            mats, result = run_budget_agent(
                current["hypothesis"], current["plan"], scientist_feedback=fb
            )
            current["budget"] = result
            plan_data["materials"] = [m.model_dump() for m in mats]
            plan_data["budget"] = result.model_dump()
            feedback_trace.append(f"Budget Agent re-ran{trace_suffix}")

        elif section == "timeline":
            result = run_timeline_agent(
                current["hypothesis"], current["plan"], current["budget"], scientist_feedback=fb
            )
            current["timeline"] = result
            plan_data["timeline"] = result.model_dump()
            feedback_trace.append(f"Timeline Agent re-ran{trace_suffix}")

        elif section == "validation":
            result = run_validation_agent(
                current["hypothesis"], current["plan"], scientist_feedback=fb
            )
            current["validation"] = result
            plan_data["validation"] = result.model_dump()
            feedback_trace.append(f"Validation Agent re-ran{trace_suffix}")

        elif section == "cro_ready_brief":
            result = run_cro_agent(
                current["hypothesis"],
                current["plan"],
                current["budget"],
                current["timeline"],
                current["validation"],
                scientist_feedback=fb,
            )
            current["cro_ready_brief"] = result
            plan_data["cro_ready_brief"] = result.model_dump()
            feedback_trace.append(f"CRO Agent re-ran{trace_suffix}")

    updated_plan = DemoRunResponse(**plan_data)
    return updated_plan, feedback_trace
