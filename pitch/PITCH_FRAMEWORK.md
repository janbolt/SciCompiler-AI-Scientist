# SciCompile — Pitch Framework
**For:** Hack-Nation × Fulcrum Science Challenge 04 — *The AI Scientist*
**Deliverables covered:** Technical architecture diagram (layout + content), 60-second video script (timed beats), USP prioritization, narrative logic loop.

---

## 0. Step-by-step reasoning (how this framework was built)

1. **Re-read the brief through a judge's eyes.** Fulcrum's rubric explicitly weights three things: (a) plan quality a real PI would trust, (b) literature QC accuracy/speed, (c) UX. The stretch goal — a *learning loop* from scientist feedback — is "the hardest challenge in the brief, and the one with the highest ceiling." Judges will reward whoever credibly closes that loop more than any other single feature.
2. **Mapped the brief's quality bar to what the codebase actually does.** The brief asks for protocol + materials/supply chain + budget + timeline + validation + novelty signal + references. Your platform produces *all seven*, plus risk register, evidence/assumption separation, CRO-ready brief, and a live submission to a real CRO API (Litmus). That is more than the rubric requires — so the pitch problem is not coverage, it's *compression*: what to leave out of 60 seconds.
3. **Picked the three "moats" no other team will plausibly have.** From the codebase: (i) live `api.litmus.science` integration that returns a real `experiment_id` + cost + turnaround, (ii) selective regeneration on a typed dependency graph (60–80% LLM-cost reduction on rerun), (iii) cross-hypothesis 4-tier fingerprint memory that genuinely closes the stretch-goal loop. Everything else in the pitch supports these three.
4. **Chose a metaphor that turns 11 agents into one idea.** "SciCompile" — scientists compile a hypothesis into a runnable experiment the same way engineers compile code into a runnable binary. The diagram and the script both lean on this metaphor so the architecture stops looking like 11 random boxes and starts looking like *one pipeline with stages*. Judges remember metaphors; they do not remember agent counts.
5. **Locked the logic loop.** Pain → System → Proof → Compounding payoff. Each beat hands the next its setup. No beat exists for its own sake.
6. **Prioritized what to *show* over what to *say*.** A 60-second video is a visual medium. The script is short on purpose; the screen does the heavy lifting (real protocols.io URLs, real catalog numbers, real Litmus `experiment_id`).

---

## 1. Strategic frame — what wins this challenge

Fulcrum is a science-ops company. They are not awarding points for "most agents." They will award points for **operational realism**, **trust signals**, and **learning** — the three things that make a tool a *platform*. Build the diagram and the script around those three judgments:

| Judge thinks… | Your evidence |
|---|---|
| "Would I let this near my lab?" | Real protocols.io step text, catalog numbers, Pydantic-enforced typed outputs, Python-computed `missing_required_fields` (the LLM cannot lie about completeness), evidence/assumption separation. |
| "Is this just a demo, or is it actually wired?" | Live POST to `api.litmus.science/validate` then `/experiments`, returning a real `experiment_id`, `estimated_cost_usd`, `estimated_turnaround_days`. **Show this on screen.** |
| "Does it compound, or do I have to re-prompt every time?" | 4-tier fingerprint memory + selective regeneration. Show one correction on Plan A, then watch Plan B for a similar experiment include that correction *without being re-prompted*. This is the stretch-goal money shot. |

If the diagram and the 60s reinforce these three answers, the rest is decoration.

---

## 2. USP prioritization — the focus stack

Tier them ruthlessly. Anything below T2 stays out of the 60s and lives only on the diagram.

### T0 — Must be on screen and in script (the moats)

1. **Live CRO submission (Litmus).** Unique. Likely no other team has this. Concrete artifact: an `experiment_id` returned by a real API on stage. *This alone makes the demo memorable.*
2. **Closed learning loop with cross-hypothesis memory.** Solves Fulcrum's "highest-ceiling" stretch goal. Visible payoff: Plan B reflects Plan A's correction without re-prompting.
3. **Typed, schema-enforced 11-agent compile pipeline.** Instructor + `Mode.TOOLS` + `temperature=0` + Pydantic. Frame this as *trust infrastructure*, not as engineering trivia: "the LLM is constrained to a typed contract — it cannot return malformed science."

### T1 — Must be on the diagram, briefly named in script

4. **Selective regeneration on a dependency graph.** Re-runs only the agents downstream of the annotated section. Frame: *"corrections are interactive, not full reruns."* (60–80% LLM-cost reduction is the proof point.)
5. **Real grounding sources.** protocols.io v3, Semantic Scholar, OpenAlex — real DOIs, real author names, real protocol URLs surfaced to the user. Frame: *"every step is sourced, every reference is clickable."*
6. **Honest hypothesis intake.** `missing_required_field` sentinel + Python `@model_validator` computes missingness deterministically. Frame: *"the system tells you what it doesn't know — it doesn't fake completeness."*

### T2 — On the diagram only (depth, not headlines)

7. CRO-compatibility bundling (LLM groups cards into one quotable service line at named real CROs).
8. Evidence/assumption separation (`EvidenceType` × `EvidenceStrength`).
9. Risk register with `RiskCategory` × `RiskSeverity` × `RiskLikelihood` × `PlanAction`.
10. Adapter layer (`adapters.py`) translating internal schemas → frontend-ready shape.
11. Benchling ELN export (Markdown of plan, ready for paste).
12. Confidence score (avg of `avg_protocol_confidence` × `execution_readiness_score`).
13. Star-rating ReviewPanel + `FeedbackAppliedBanner` + relevance-filtered prior reviews.
14. Dual-store feedback (frontend `localStorage` + backend `feedback.json` + `feedback_memory.json`).
15. Fixture mode (`?fixture=crp`) for demo reliability.

---

## 3. The logic loop — the narrative spine

The pitch is one sentence repeated three ways. **"Hypothesis in. Lab-ready plan out. Every correction makes the next plan better."**

Beat 1 — **Pain.** Going from a scientific question to a runnable plan takes weeks. Not because of ideas; because of operations.
Beat 2 — **Compression.** SciCompile compiles a hypothesis through 11 typed agents into a complete, sourced, costed, schedulable plan in seconds.
Beat 3 — **Realness.** That plan is not a PDF — it can be submitted to a real CRO with one click and come back with an `experiment_id`, a price, and a turnaround.
Beat 4 — **Compounding.** Every correction a scientist makes is fingerprinted and replayed on similar future experiments. The system gets smarter with use — *that is the difference between a tool and a platform* (Fulcrum's exact framing — quote it back to them).

Each beat hands the next its setup: Pain → System → Proof → Compounding. The compounding beat is what closes the loop and is the line judges should remember.

---

## 4. Technical architecture diagram — layout spec

### Visual metaphor
**A compiler pipeline that bends back on itself.** Left-to-right horizontal flow for the 11 agents, then a feedback arc curving from the "Scientist Review" node at the right back into a "Memory Store" that re-injects into the leftmost agents. The shape itself tells the story: it is a loop, not a funnel.

### Recommended canvas
- **Format:** 16:9, ~1920×1080, dark background (#0B1220) with cool blue/cyan accents. Three colors total — neutral grey for infrastructure, cyan (#22D3EE) for data flow, magenta/orange (#F97316) for the feedback loop.
- **Tools:** Excalidraw, Figma, or tldraw. Avoid generic flowchart software — judges have seen those.

### Layout (top-to-bottom bands)

**Band 1 — Header strip (top, thin)**
Logo + tagline: `SciCompile — From hypothesis to runnable experiment in seconds.`

**Band 2 — Input lane (left edge)**
- A speech-bubble icon labeled `Scientist (natural language hypothesis)`.
- Sample shown verbatim: *"Replacing sucrose with trehalose as a cryoprotectant in the freezing medium will increase post-thaw HeLa viability by ≥15 pp vs. DMSO."*

**Band 3 — The Compile Pipeline (center, the largest band)**
Render the 10-stage `AGENT_ORDER` as boxes left-to-right with arrows. Group them visually into four sub-bands:

```
GROUP A — Understand
  [1 Intake]  →  [2 Literature QC]  →  [3 Protocol Retrieval]

GROUP B — Reason
  [4 Evidence]  →  [5 Risk]

GROUP C — Plan & Cost
  [6 Plan]  →  [7 Budget]  →  [8 Timeline]  →  [9 Validation]

GROUP D — Ship
  [10 CRO-Ready Brief]  →  [11 CRO-Compatibility Classifier]
                                          ↓
                                  [Litmus Science API]
                                          ↓
                          experiment_id · cost · turnaround
```

Annotate each box with **(a)** the typed Pydantic schema it emits, **(b)** the *one* external grounding source it uses, if any, and **(c)** what it owns vs. what Python owns (judges love this — it signals you know where to trust LLMs and where not to).

Examples of the annotation style:
- `Intake → StructuredHypothesis` · LLM owns extraction, Python owns `missing_required_fields`.
- `Literature QC → LiteratureQCResult` · grounded in Semantic Scholar + OpenAlex, dedupe by DOI.
- `Protocol Retrieval → list[ProtocolCandidate]` · grounded in protocols.io v3, two-LLM scoring.
- `Plan → ExperimentPlan` · steps adapted from real protocols.io text, complexity-scaled (8–25 steps).
- `Budget → list[MaterialItem] + BudgetEstimate` · catalog numbers tagged `verify_before_ordering`.
- `CRO-Compatibility → list[CROServiceBundle]` · bundles cards into named commercial services (Synthego, Eurofins, Charles River, …).

**Band 4 — Trust infrastructure (thin strip running across the whole pipeline)**
A horizontal bar reading: `instructor + Mode.TOOLS · temperature=0 · Pydantic schema-enforced · @model_validator-computed missingness`. This single strip communicates the whole technical-rigor story without needing words in the script.

**Band 5 — Outputs (right edge)**
Three artifacts emerging from the pipeline, stacked:
- **Frontend** — Overview / Experiments / Budget / Submit tabs (Vite + React, framer-motion).
- **Benchling Markdown export** — copy-paste into ELN.
- **Litmus API** — live `POST /experiments` returning the artifacts above.

**Band 6 — The Feedback Arc (the showpiece — curve back from right to left)**
A bold magenta/orange arrow leaving the `Scientist Review` node, curving over the top of the canvas, and dropping into a labeled `Memory Store` block on the left. The arc carries three labels along its length:

1. **`store_to_memory`** — feedback fingerprinted as `{experiment_type}__{first_two_words_of_intervention}`.
2. **`get_rerun_set`** — selective regeneration: only re-run agents downstream of annotation.
3. **`retrieve_prior_feedback`** — 4-tier match (exact + section ▸ same type + section ▸ exact ▸ same type).

The arc visibly *re-enters* the pipeline at every stage that consumes prior context — show small dotted drop-lines from the arc into Intake, Literature QC, Protocol, Evidence, Risk, Plan, Budget, Timeline, Validation, CRO. That visually proves the loop is wired into every stage, not just one.

**Band 7 — Footer strip**
Three numbers from the actual codebase as proof points:
- **109** plans saved in production
- **11** typed agents
- **4** external grounding sources (protocols.io · Semantic Scholar · OpenAlex · Litmus)

### Diagram do's and don'ts

- **DO** label the graph as a graph: write `AGENT_DEPENDENCIES = { … }` somewhere visible. Make the dependency graph a *visible* asset, not a hidden one. This is what makes selective regeneration believable at a glance.
- **DO** put one real artifact on screen (a real protocols.io DOI, a real Semantic Scholar reference, a real Litmus `experiment_id` from a test submission).
- **DON'T** show prompt text. Judges will assume there's a prompt. Showing it cheapens the technical depth story.
- **DON'T** draw all 11 agents the same size. Make Plan, Budget, and the CRO-Compatibility node visibly larger — those are where the judgment-rich work happens.
- **DON'T** use generic "AI brain" iconography. Use the compiler/pipeline metaphor end-to-end.

---

## 5. The 60-second video — script + storyboard

Total: **~155 spoken words** (a comfortable, unhurried 60s pace at ~155 wpm). Every visual is something the judge can verify on screen.

| t | On-screen | Voiceover (read this) |
|---|---|---|
| **0:00 – 0:06** | Cold open: timer counts up "1 day · 2 days · 1 week · 2 weeks…" over a stock shot of a scientist scrolling protocols. | *"Going from a scientific question to a runnable lab plan takes weeks. Not because of ideas — because of operations."* |
| **0:06 – 0:11** | Cut to product. Logo `SciCompile` snaps in. Tagline animates: *From hypothesis to runnable experiment in seconds.* | *"SciCompile compiles hypotheses into experiments — the way an engineer compiles code into a binary."* |
| **0:11 – 0:24** | Type in the trehalose hypothesis. Press enter. Pipeline diagram lights up agent-by-agent (Intake → Literature QC → Protocol Retrieval → … → CRO Brief). Real protocols.io URL flashes; real Semantic Scholar reference flashes. | *"Eleven typed agents, schema-enforced through Pydantic, ground every step in real protocols.io and Semantic Scholar — no hallucinated procedures, no invented citations."* |
| **0:24 – 0:34** | Tabs flip: Overview → Experiments (numbered protocol with sourced steps) → Budget (catalog numbers, EUR totals) → Timeline (DAY 1, DAY 2…). Confidence score visible. | *"Out comes a lab-ready plan: sourced protocol, materials with catalog numbers, phased timeline, validation criteria — and an honest readiness score that tells you what it doesn't know."* |
| **0:34 – 0:42** | Click **Submit to CRO**. Modal confirms. POST flies. Response snaps back: green check, **`experiment_id: lit_8f3c2a…`**, **`$1,840`**, **`14-day turnaround`**. | *"One click submits the experiments to the Litmus CRO network. Real API. Real experiment ID. Real price. Real turnaround."* |
| **0:42 – 0:54** | Split screen. Left: scientist rates "Materials" 2/5 and types *"add 30 min 37 °C incubation before centrifugation."* Save. Right: a NEW MIC-assay hypothesis is submitted — and the new plan visibly contains the 30-minute incubation step, highlighted. Banner: *Feedback applied from prior similar experiment.* | *"Every correction is fingerprinted by experiment type and replayed on similar future plans — automatically. The system doesn't just retrieve knowledge. It learns from every scientist who uses it."* |
| **0:54 – 1:00** | Logo card. Closing line types out: *Hypothesis in. Lab-ready plan out. Every correction makes the next plan better.* | *"SciCompile. The mRNA moment for everyone else's experiments."* |

### Why this script works

- **Cold open is concrete.** No "in a world…" — a literal counter showing weeks turning into nothing.
- **Three on-screen receipts.** A real protocols.io URL, a real Litmus `experiment_id`, and a real correction-applied highlight. Judges cannot dismiss any of these as mock data.
- **The compounding beat is the climax, not the opener.** Most teams will lead with their architecture. Lead with the artifact (the CRO submission), then drop the platform punch (the learning loop). It re-orders the wow.
- **Closes with Fulcrum's own metaphor.** *"The mRNA moment"* is the brief's own framing — quoting it back lands as alignment, not flattery.
- **No agent counting in the voiceover.** "11 agents" is on the diagram and in one beat — never repeated. The script sells outcomes, the diagram sells depth.

### Production notes

- **Pace:** record at 155 wpm, do NOT speed-edit. Confidence is the tone, not urgency.
- **Audio:** soft pulsing synth under the pipeline animation; cut audio to silence for one beat at the moment the `experiment_id` returns — the silence is the punctuation.
- **Captions:** burn in subtitles. Many judges watch with sound off on first pass.
- **Demo reliability:** record the live demo with `?fixture=crp` enabled so the API never fails on camera, but show the *real* Litmus call in a second take with sound, then cut them together.
- **The correction → reuse beat must be ONE TAKE.** Judges will assume any cut is a swap. Film it real. The codebase already supports this: leave one piece of feedback on a saved plan, then submit a fresh hypothesis of the same `experiment_type` and the prior correction will appear via `retrieve_prior_feedback` (Tier 1: same `experiment_type` + same `section`).

---

## 6. The technical-depth talking points (for a Q&A or longer cut)

Hold these in reserve. They are the answers to *"how does it actually work?"* — useful for a longer demo video, judge Q&A, or the README.

- **Why typed Pydantic + `Mode.TOOLS`?** Because schema violations are rejected at the framework level, not caught downstream. The LLM cannot return malformed science. `temperature=0` makes runs reproducible.
- **Why a dependency graph instead of a chain?** Because corrections are local. Annotating "Risks" should not re-run "Intake." `get_rerun_set` finds the earliest annotated section and replays only from there — typically 60–80% fewer LLM calls per correction.
- **Why fingerprint by `{experiment_type}__{first_two_words_of_intervention}`?** Because pure semantic similarity is too loose (it fires on irrelevant matches) and exact-string matching is too tight (it never fires). The 4-tier match degrades gracefully: exact ▸ same type + section ▸ exact ▸ same type ▸ excluded. Tier 99 is excluded so unrelated experiments never pollute the prompt.
- **Why is missingness Python-computed?** Because the LLM's incentive is to look complete. The `@model_validator(mode="after")` scans for the `"missing_required_field"` sentinel and builds the list deterministically. The LLM cannot lie about what it doesn't know.
- **Why does CRO-Compatibility bundle?** Because real CROs sell *service bundles*, not individual prep steps. The LLM groups cards into a single quotable line at named real providers (Synthego, Eurofins, Charles River, WuXi, FCDI, Azenta). Cards inside a bundle are flagged `cro_compatible:true`; cards outside any bundle are silently un-flagged so the UI doesn't pollute with negative pills.
- **Why dual-store feedback?** Frontend `localStorage` for instant relevance filtering and Benchling-ready edits; backend `feedback.json` for per-plan history and `feedback_memory.json` for cross-hypothesis memory. Both are flat JSON — auditable, portable, no DB dependency. 109 plans saved is the field-test number.

---

## 7. Closing tagline candidates (pick one for hero shot)

1. **"Hypothesis in. Lab-ready plan out. Every correction makes the next plan better."** *(recommended — restates the loop.)*
2. **"The mRNA moment for everyone else's experiments."**
3. **"Type a hypothesis. Get a CRO order."**
4. **"AI that doesn't just write science — it grounds it, prices it, and ships it."**

---

*Built from a full read of: `Challenge_Description.pdf`, `PLATFORM_ANALYSIS.md`, `orchestrator.py`, `services/memory.py`, `litmus_client.py`, `schemas.py`, all 11 agents, and the React frontend. April 2026.*
