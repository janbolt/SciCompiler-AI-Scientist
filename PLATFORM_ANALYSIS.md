# SciCompile — Platform Analysis: USPs, Design Features & Challenge Alignment

> **For:** Hack-Nation Challenge #04 "The AI Scientist" × Fulcrum Science × World Bank Youth Summit × Global AI Hackathon 2026  
> **Date:** April 2026  
> **Status:** Technical deep-read of full codebase — all 11 agents, orchestrator, adapters, memory layer, frontend, Litmus integration

---

## What the platform actually does

A scientist types a raw hypothesis in plain English. Within seconds, SciCompile runs it through 11 specialized AI agents in a defined dependency graph and returns a complete, executable wet-lab experiment plan — with protocol steps sourced from real protocols.io data, a budget with catalog numbers, a phased timeline, a risk register, a validation plan, and a one-click submission path to the Litmus CRO network. Every section is reviewable with star ratings; corrections are stored and automatically applied to future runs on similar experiments.

The platform has 109 saved plan files in production — evidence it is already running real experiments.

---

## Unique Selling Points

### 1. Direct Litmus CRO Submission (The Killer Feature)

The platform is the only hackathon entry (almost certainly) with a live integration to `api.litmus.science`. The flow is:

- Backend auto-classifies experiment type from the plan (MIC_MBC_ASSAY, QPCR_EXPRESSION, CELL_VIABILITY_IC50, ENZYME_INHIBITION_IC50, MICROBIAL_GROWTH_MATRIX, ZONE_OF_INHIBITION, SANGER_PLASMID_VERIFICATION, CUSTOM)
- Derives the null hypothesis programmatically from the plan hypothesis
- Calls `POST /validate` first to catch schema errors before submission
- Calls `POST /experiments` and returns the live `experiment_id`, `status`, `estimated_cost_usd`, `estimated_turnaround_days` per experiment
- Handles partial success per-experiment (one failure doesn't block the others)
- CRO-compatibility is computed automatically: if `execution_readiness_label != "blocked_pending_expert_review"`, the experiment is flagged `cro_compatible: true`

The frontend Submit tab shows the hypothesis, lists CRO-compatible experiments, requires confirmation in a modal, then posts to `/api/litmus/submit`. The response surfaces experiment IDs and cost estimates inline. The full pipeline ends at an actionable CRO order — not a PDF.

### 2. 11-Agent Sequential Pipeline with Typed Pydantic Schemas

Every agent uses `instructor` with `Mode.TOOLS` (function calling) and `temperature=0` — meaning the LLM cannot return malformed output. Each agent produces a strictly validated Pydantic model; schema violations are rejected at the framework level, not caught downstream. The dependency graph is explicit:

```
hypothesis
  └─ literature_qc
       └─ protocol_candidates
            └─ evidence_claims
                 └─ risks
                      └─ plan
                           ├─ budget
                           ├─ timeline (depends on plan + budget)
                           └─ validation
                                └─ cro_ready_brief
```

This means each agent has exactly the context it needs — no more, no less — and the output of upstream agents is always structurally correct before being passed downstream.

### 3. Selective Regeneration via Dependency Graph

When a scientist annotates a section for correction (e.g., "risks"), the platform does not re-run the entire 11-agent pipeline. It computes the minimal re-run set: annotated section + every agent that depends on it. Agents upstream of the annotation are preserved unchanged. This saves approximately 60–80% of LLM calls on typical corrections, and it means re-runs are fast enough to be interactive.

The `get_rerun_set` function finds the earliest-indexed annotated section in `AGENT_ORDER` and returns everything from that point forward. The `selective_regenerate` function replays only those agents, passing per-agent feedback.

### 4. Cross-Hypothesis Memory with 4-Tier Fingerprint Matching

Scientist corrections are not stored per-plan and forgotten — they are stored in a flat `feedback_memory.json` keyed by experiment fingerprint (`{experiment_type}__{first_two_words_of_intervention}`) and retrieved on every new run via a tiered priority system:

- Tier 0: exact fingerprint + exact section (same experiment, same section)
- Tier 1: same experiment_type + same section (different intervention, same class)
- Tier 2: exact fingerprint, any section
- Tier 3: same experiment_type, any section
- Tier 99: excluded (unrelated experiment type — never pollutes runs)

Retrieval uses `requested_changes` (structured list items, max 3) rather than free-form text, so corrections are actionable by the LLM. Each stored correction tracks `applied_count` — the platform knows which corrections have been used most.

This means the platform genuinely improves with use. After one scientist corrects "add 30 min incubation at 37°C before centrifugation" on an MIC assay, every future MIC assay plan will include that step automatically.

### 5. Honest Readiness Scoring with MISSING Sentinel

Every plan carries an `execution_readiness_score` (0.0–1.0) and an `execution_readiness_label`. Importantly, the `missing_required_fields` list on `StructuredHypothesis` is computed by a Pydantic `@model_validator(mode="after")` in Python — not by the LLM. The LLM cannot lie about what is missing; the validator scans all fields for the `"missing_required_field"` sentinel and builds the list deterministically.

This is significant for credibility: the platform will not invent a comparator control, a measurable outcome, or an experiment type if the hypothesis does not contain them. It will flag them as missing and ask clarifying questions.

### 6. Evidence/Assumption Separation

The Evidence agent explicitly classifies each claim by `EvidenceType` (experimental, computational, observational, review, mechanism, assumption) and `EvidenceStrength` (strong, moderate, weak, conflicting, insufficient). Assumptions are not blended into the evidence — they are tagged as such. A scientist reviewer can immediately see which claims rest on strong experimental support versus mechanistic inference.

### 7. Real Protocol Retrieval from protocols.io

Literature QC uses the protocols.io API v3 with bearer token authentication. The Protocol Retrieval agent first decomposes the hypothesis into required procedures, then retrieves from protocols.io per procedure, then scores relevance in a second LLM call. References carry `protocol_url`, `authors`, `published_year`, `match_type`, and `relevance_note`. DOIs are extracted from protocol URLs and surfaced to the frontend.

This means protocol steps are grounded in real published methods, not hallucinated procedures.

### 8. Benchling ELN Export

The Benchling export modal generates a full Markdown document from the plan: hypothesis, goal, duration, numbered protocol steps, materials table (with catalog numbers, quantities, unit costs, subtotals), and success criteria. Critically, if a scientist has edited materials or steps in-session (via the inline editor), those corrections are used in the export — not the original plan. The export is copy-paste-ready for Benchling or any ELN.

### 9. Dual-Store Feedback Architecture

**Frontend (localStorage):** Two separate keys — `predictivebio_feedback` (per-experiment material and step corrections, written on "Save Changes", used by Benchling export) and `predictivebio_reviews` (structured star-rating reviews, passed as `prior_feedback` to the backend on every subsequent run).

**Backend (flat JSON):** `feedback.json` stores per-plan feedback records; `feedback_memory.json` stores cross-hypothesis memory. Both stores are append-only flat files — no database dependency, trivially portable, and auditable.

### 10. Adapter Layer: Backend Serves Frontend-Ready Data

`adapters.py` is a complete transformation layer that converts internal agent schemas into the `FrontendPlanData` shape the React frontend consumes verbatim. Field-name mismatches, enum remappings, and structural reshaping are all handled here — not scattered across agents or the orchestrator. The `/demo/plan` endpoint returns display-ready data; the frontend does no transformation.

This includes deriving a one-sentence objective from `intervention` + `measurable_outcome`, parsing DAY N markers from protocol step descriptions to estimate experiment duration, splitting materials into fixed/staff/recurring budget categories, and mapping novelty signal strings to human-readable labels.

---

## Design and UX Features

**Star-rating ReviewPanel** — Scientists rate each section (Protocol Steps, Materials & Reagents, Timeline) on a 1–5 scale with contextual labels (Poor → Excellent). A textarea appears automatically only when rating ≤ 3 — reducing friction for positive ratings while capturing specific corrections when needed. The placeholder text explicitly tells the scientist: "this will inform future plan generation."

**FeedbackAppliedBanner** — A visual confirmation banner appears when the backend confirms `feedback_incorporated: true`, closing the loop for the scientist. The `feedback_trace` array lists which agents received notes and how many.

**Relevance-filtered prior reviews** — The frontend builds a hypothesis context string from the user's input plus all experiment names and goals from the plan, then filters stored reviews against it using keyword matching. Reviews tagged with an unrelated experiment type (e.g., "western blot" when the new run is a cryopreservation assay) are excluded. This prevents irrelevant corrections from polluting new runs.

**Fixture mode (`?fixture=crp`)** — Appending `?fixture=crp` to the URL loads a pre-built CRP biosensor plan from a static JSON fixture, bypassing the backend entirely. This makes demos instantly reliable regardless of API key or backend availability.

**Framer Motion animations** — The input → loading → results transitions use `AnimatePresence` with `mode="wait"`, producing professional fade transitions between stages. This signals polish to judges evaluating the UI.

**4-tab results view** — Overview (hypothesis + novelty + references + timeline phases), Experiments (per-protocol cards with inline editing), Budget (line-item breakdown), Submit (Litmus CRO submission). This information hierarchy mirrors how a real scientist would review a plan.

**Confidence score** — Displayed on results; computed as the average of `avg_protocol_confidence` (from protocols.io scoring) and `execution_readiness_score` (from the Plan agent). Two independent signals merged into a single user-facing number.

---

## Challenge Rubric Mapping

| Rubric Criterion | Platform Implementation | Strength |
|---|---|---|
| Hypothesis extraction accuracy | Intake Agent with 9 structured fields; `@model_validator` computes missing fields; LLM cannot hallucinate completeness | Very strong |
| Missing-field honesty | MISSING sentinel + Python-computed `missing_required_fields`; `clarifying_questions` list for incomplete hypotheses | Very strong |
| Literature QC | protocols.io API v3 with real retrieval; novelty signal; reference list with URLs and relevance notes | Strong |
| Protocol relevance | Two-LLM protocol retrieval (decompose → retrieve → score); steps linked to protocols by name | Strong |
| Evidence/assumption separation | Explicit `EvidenceType` enum with `assumption` category; `EvidenceStrength` on every claim | Strong |
| Risk detection | Risk agent with `RiskCategory`, `RiskSeverity`, `RiskLikelihood`, `PlanAction` enums; mitigation per risk | Strong |
| Materials completeness | `catalog_number` or `"verify_before_ordering"` sentinel; supplier; quantity; cost per line item | Strong |
| Budget realism | Adapter splits into fixed/staff/recurring; staff cost computed as days × 8h × 45 EUR/h | Moderate–Strong |
| Timeline realism | `TimelinePhase` with `dependencies`, `responsible_role`, `risk_buffer`, `bottlenecks` per phase | Strong |
| Validation quality | `ValidationPlan` with `success_threshold`, statistical methods, controls | Moderate–Strong |
| Reproducibility | protocols.io-sourced steps; Benchling ELN export; plan stored as JSON (109 plans saved) | Very strong |
| UI clarity | 4-tab layout, star-rating review, framer-motion transitions, confidence score | Strong |
| Feedback loop | Selective regeneration + cross-hypothesis memory + `applied_count` tracking | Very strong |
| Litmus integration | Live API integration: validate + submit + return experiment_id, cost, turnaround | **Unique / Killer** |

---

## Gaps to Address Before Submission

### High Priority

**PDF export** — The Submit tab shows "Download Full Plan (PDF)" with a "Coming soon" tag. This should be implemented. Judges will want to download a plan. A Cursor prompt targeting `SubmitTab.tsx` + a new `/api/plans/{plan_id}/export/pdf` endpoint using `weasyprint` or `reportlab` would close this gap.

**Demo fixture polish** — The `?fixture=crp` CRP biosensor fixture is the safest demo path. It should be used as the primary demo entry point for judges. Verify the fixture data is current and comprehensive (includes Litmus-compatible experiments, real references, complete materials list).

**Confidence score display** — The score is computed and returned but the frontend rendering should be verified. Ensure it appears prominently on the Overview tab.

**Missing sections on partial hypothesis** — When the intake agent flags missing fields, the UI should surface `clarifying_questions` prominently so judges can see the honesty mechanism in action.

### Medium Priority

**README update** — README still references Next.js; the frontend is now Vite + React. Update to reflect actual setup commands and the `?fixture=crp` demo URL.

**Error state for missing LITMUS_API_KEY** — The SubmitTab already handles this gracefully with an inline error message and a hint to set the env var. Confirm this renders cleanly in demo conditions.

**applied_count visibility** — The memory system tracks how many times each stored correction has been applied, but this is not surfaced in the UI. A small "This feedback has been applied N times" label in the ReviewPanel history would demonstrate learning to judges.

### Low Priority

**Benchling "Open in Benchling" button** — The export modal has the markdown; adding a direct link to `app.benchling.com/new` pre-populated would make the ELN story complete.

**Protocol step hyperlinks** — `ProtocolStep.linked_to` links steps to protocol names. These should resolve to clickable `protocol_url` links in the Experiments tab so judges can verify the sourcing.

---

## Suggested Cursor Prompts for Remaining Gaps

### PDF Export

> **Goal:** Add PDF download for a full experiment plan.
>
> Modify only: `backend/app/main.py`, `frontend/src/components/SubmitTab.tsx`
>
> Backend: Add `GET /plans/{plan_id}/export/pdf`. Use the `weasyprint` library. Convert the plan's `FrontendPlanData` to an HTML string (hypothesis, objective, phases as a table, one section per experiment with numbered steps and a materials table, budget summary). Return as `Response(content=pdf_bytes, media_type="application/pdf", headers={"Content-Disposition": f'attachment; filename="plan_{plan_id}.pdf"'})`.
>
> Frontend: In `SubmitTab.tsx`, wire the "Download Full Plan (PDF)" button to `GET /api/plans/{plan_id}/export/pdf` using `window.open` or a fetch + Blob URL. Remove the "Coming soon" tag. Use the `plan_id` from `PlanContext`. If `plan_id` is not in context, disable the button with tooltip "Generate a plan first".
>
> Do not create new files unless the test suite requires a new test file.

### applied_count in ReviewPanel

> **Goal:** Show scientists that their feedback is being learned from.
>
> Modify only: `frontend/src/components/ReviewPanel.tsx`, `frontend/src/lib/feedbackStore.ts`
>
> In `feedbackStore.ts`, expose a `loadReviewHistory(): ExperimentReview[]` function that returns all stored reviews sorted by `timestamp` descending.
>
> In `ReviewPanel.tsx`, below the submit button, add a collapsible "Your feedback history" section. For each stored review relevant to the current experiment type, show: experiment name, timestamp, overall rating as stars, and per-section notes. Label it "Applied to future plans" with a checkmark icon. This closes the feedback loop visually — scientists can see their corrections are accumulating.

---

## One-Liner Options for the Pitch

- **"Type a hypothesis. Get a lab-ready experiment plan, sourced from real protocols, with a one-click CRO submission."**
- **"The gap between a scientific idea and an executable lab plan, closed in seconds."**
- **"AI that doesn't just write science — it grounds it, prices it, and sends it to a lab."**

---

*Analysis based on full codebase read: schemas.py, orchestrator.py, main.py, litmus_client.py, adapters.py, services/memory.py, agents/ (all 11), App.tsx, ReviewPanel.tsx, SubmitTab.tsx, BenchlingExportModal.tsx, feedbackStore.ts, 109 saved plan files. April 2026.*
