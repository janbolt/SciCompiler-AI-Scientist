# Changelog — PredictiveBio

All notable changes to this project are documented here in reverse chronological order.

---

## [Unreleased] — 2026-04-26

### Added — Backend → Frontend JSON Contract (live data replaces MOCK_PLAN)
- **`FrontendPlanData` Pydantic schema** (`backend/app/schemas.py`)
  - Models: `FrontendMaterial`, `FrontendExperiment`, `FrontendReference`, `FrontendBudgetLine`, `FrontendBudget`, `FrontendPhase`, `FrontendPlanData`
  - Matches the TypeScript `PlanData` type in `mockData.ts` exactly — no client-side adapter needed
- **`backend/app/adapters.py`** (new file)
  - `to_frontend_plan(hypothesis, lit_qc, timeline, experiments) → FrontendPlanData`
  - Handles all field remapping: novelty enum values, reference formatting, phase key renaming, budget derivation from experiment materials
- **`experiments_agent`** (`backend/app/agents.py`)
  - Produces a `list[FrontendExperiment]` with steps and materials grouped per experiment (3 experiments for the cryopreservation stub)
  - Incorporates prior scientist feedback notes as correction steps
- **`run_frontend_pipeline`** (`backend/app/orchestrator.py`)
  - Lightweight pipeline: intake → lit QC → risks → timeline → experiments → adapter → `FrontendPlanData`
  - Accepts and applies `prior_feedback` from the request
- **`POST /demo/plan`** (`backend/app/main.py`)
  - New endpoint returning `FrontendPlanData` JSON directly consumable by the frontend
- **`PlanContext`** (`frontend/src/context/PlanContext.tsx`)
  - React context providing `{ plan, setPlan }`, defaulting to `MOCK_PLAN`
  - `usePlan()` hook for reading, `useSetPlan()` hook for writing
  - Wrapped around the app in `main.tsx`
- **`App.tsx` API integration**
  - `handleSubmit` calls `POST /api/demo/plan` with the hypothesis and prior feedback
  - On success, calls `setPlan(data)` to replace the mock plan with live backend data
  - Falls back to `MOCK_PLAN` silently if the backend is unreachable
- **`vite.config.ts` proxy**
  - `/api/*` forwarded to `http://localhost:8000` with prefix stripped, so frontend calls `/api/demo/plan` and backend receives `/demo/plan`
- **Component updates** — all tabs now read from `usePlan()` instead of importing `MOCK_PLAN`
  - `OverviewTab.tsx`, `ExperimentsTab.tsx`, `BudgetTab.tsx`
  - `BenchlingExportModal` hypothesis prop sourced from context

---


### Added — Feedback Loop & Scientist Review System
- **`ReviewPanel` component** (`frontend/src/components/ReviewPanel.tsx`)
  - Collapsible "Rate & Review" panel at the bottom of every experiment card
  - Star ratings (1–5) for three sections: Protocol Steps, Materials & Reagents, Timeline
  - Overall plan quality rating (required to submit)
  - Free-text correction note appears automatically for ratings ≤ 3
  - Experiment-type tag input (e.g. "cryopreservation", "western blot") used to match corrections to future similar experiments
  - Submitted reviews show a persistent confirmation state
- **`FeedbackAppliedBanner` component** (`frontend/src/components/FeedbackAppliedBanner.tsx`)
  - Dark teal banner rendered at the top of every results view
  - Shows how many prior reviews were active and how many corrections were applied
  - Previews up to 2 correction notes with experiment type context
- **Structured review storage** in `feedbackStore.ts`
  - `ExperimentReview` / `SectionRating` / `PriorFeedbackItem` types
  - `saveReview()` / `loadAllReviews()` / `reviewCount()` / `buildPriorFeedback()` functions
  - Reviews stored under `localStorage["predictivebio_reviews"]`, separate from material corrections
- **Backend `PriorFeedbackItem` schema** (`backend/app/schemas.py`)
  - New Pydantic model for structured scientist correction items
  - `DemoRunRequest` extended with `prior_feedback: list[PriorFeedbackItem]`
- **Backend feedback incorporation** (`backend/app/orchestrator.py`, `backend/app/agents.py`)
  - `run_demo_pipeline` merges plan-level stored feedback with incoming `prior_feedback` from the UI
  - Only corrections with rating ≤ 3 and a non-empty note are used as generation signals
  - Corrections are passed as silent context to `plan_agent` — no visible flags or labels in the output
  - Correction summaries stored in `ExperimentPlan.feedback_incorporated` for audit purposes only
- **`App.tsx` wiring**
  - `handleSubmit(hypothesis)` fires `POST /api/demo/run` with `prior_feedback` payload built from stored reviews
  - Feedback is applied silently — no banner or UI indicator is shown to the scientist; the plan simply improves

### Added — Benchling Export
- **`BenchlingExportModal` component** (`frontend/src/components/BenchlingExportModal.tsx`)
  - "Protocol Preview" tab: full plan rendered as Markdown (uses scientist-edited data when available)
  - "Direct API Push" tab: fields for Benchling API key, workspace subdomain, folder ID
  - Copy Markdown to clipboard and Download .md buttons always available
  - Push to Benchling button POSTs to `/api/benchling/export` (backend endpoint TBD)
  - Scientist-edited materials from the feedback store are automatically included in the export
- **"Export to Benchling" button** in Experiments tab toolbar (dark teal, always visible)

### Added — Protocol Step Editing
- Scientists can **add steps** ("+  Add step" button) and **remove steps** (trash icon per row) in edit mode
- Each step uses a self-resizing `<textarea>` instead of contentEditable
- **Warning banner** ("⚠ Check materials") appears on the collapsed card header and inline above the steps list immediately when steps are structurally changed (added or removed)
- Warning persists through save — only clears on page reload (which resets to a fresh plan)
- Steps saved to `localStorage["predictivebio_feedback"]` under the experiment id via `saveExpFeedback`

### Added — Full Material Inline Editing
- All six material table columns are now editable in edit mode: Reagent, Catalog #, Supplier, Qty Amount, Qty Unit, Unit Cost
- Qty split into separate **numeric amount** field (number input) + **free-text unit** field (text input)
  - Subtotal = `qty_amount × unit_cost_eur`, recalculates immediately on change
  - Unit string is unrestricted: accepts "mL", "vials", "10⁶ cells", "μg/mL", "as needed", etc.
- "Save Changes" persists material + step corrections to localStorage
- "✓ Saved" flash appears on card header after saving
- CSV download in Budget tab reads scientist-edited data from the store when available

### Changed — Architecture: Plan Display vs. Feedback Store
- Experiment cards always initialise from the plan data (mock or backend response)
- `localStorage` is **write-only** from the UI's perspective — corrections are stored for backend use but never pre-populate the visible plan on reload
- Each new hypothesis always starts from a fresh backend-generated (or mock) plan

### Added — Navbar & Navigation
- **"← New hypothesis" button** in navbar, visible only when in results view
- Prevents accidental resets by keeping the logo non-interactive
- Brand label changed from "AI Scientist" to **"PredictiveBio"**

### Changed — Hypothesis Input
- Placeholder text updated to guide scientists on forming valid hypotheses (intervention + measurable outcome + mechanism + control condition)

### Fixed — Phase Timeline
- Refactored from a two-row proportional layout to a **Gantt-style list** (one row per phase)
- Each row shows: step index, phase name, proportional bar (min 2% width), duration in days
- All phase labels are now always readable regardless of duration

---

## [0.1.0] — Initial frontend rebuild

### Added
- Complete frontend rewrite: **Vite + React + TypeScript + Tailwind CSS**
- Design system based on litmus.science aesthetic:
  - Color palette: warm cream (`#f5f3ef`), deep teal (`#1e3a3a`), teal accent (`#2ec4b0`), coral (`#e07060`)
  - Typography: Playfair Display (headings), DM Sans (body), Space Mono (mono/code)
  - CSS variables in `index.css` for all design tokens
- **InputScreen**: hypothesis textarea, example pre-fill chip, "Generate Plan" CTA
- **LoadingState**: animated progress bar with cycling agent status messages
- **OverviewTab**: literature QC badge, plan summary cards, phase timeline
- **ExperimentsTab**: collapsible experiment cards, CRO-compatible checkbox selection, batch submit to Litmus
- **BudgetTab**: three-section budget table (fixed / staff / recurring), CSV download
- **SubmitTab**: CRO submission CTA, PDF download placeholder
- **Navbar**: sticky header with brand logo and "Powered by Fulcrum Science" label
- **TabBar**: sticky tab navigation for Overview / Experiments / Budget / Submit
- **Modal**: reusable confirmation dialog (Framer Motion animated)
- `mockData.ts`: TypeScript types and `MOCK_PLAN` sample data matching backend schema shape
- `feedbackStore.ts`: localStorage-backed store for material corrections and protocol step edits

### Backend (existing `jan` branch, no changes)
- FastAPI with agents: Intake, Literature QC, Protocol Retrieval, Evidence, Risk, Plan, Materials, Budget, Timeline, Validation, CRO Brief
- `/demo/run`, `/plans/{id}/feedback`, `/plans/{id}/regenerate` endpoints
- File-based store (`backend/data/`) for plan runs and feedback
