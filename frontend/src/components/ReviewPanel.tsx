import { useState } from "react";
import { Check, ChevronDown, Star } from "lucide-react";
import { AnimatePresence, motion } from "framer-motion";
import { Experiment } from "../mockData";
import { ExperimentReview, SectionRating, saveReview } from "../lib/feedbackStore";

type Section = "steps" | "materials" | "timeline";

const SECTION_LABELS: Record<Section, string> = {
  steps: "Protocol Steps",
  materials: "Materials & Reagents",
  timeline: "Timeline",
};

const SECTION_DESCRIPTIONS: Record<Section, string> = {
  steps: "Were all necessary steps present and correctly ordered?",
  materials: "Were reagent choices, catalog numbers, and suppliers accurate?",
  timeline: "Were phase durations realistic for this experiment type?",
};

const RATING_LABELS = ["", "Poor", "Below expectations", "Adequate", "Good", "Excellent"];

// ─── StarRating ───────────────────────────────────────────────────────────────

function StarRating({
  value,
  onChange,
}: {
  value: number;
  onChange: (v: 1 | 2 | 3 | 4 | 5) => void;
}) {
  const [hovered, setHovered] = useState(0);

  return (
    <div className="flex items-center gap-1">
      {([1, 2, 3, 4, 5] as const).map((n) => {
        const active = n <= (hovered || value);
        return (
          <button
            key={n}
            type="button"
            onMouseEnter={() => setHovered(n)}
            onMouseLeave={() => setHovered(0)}
            onClick={() => onChange(n)}
            aria-label={`Rate ${n} out of 5`}
            style={{
              background: "none",
              border: "none",
              padding: 1,
              cursor: "pointer",
              color: active ? "#f0a500" : "var(--color-border)",
              transition: "color 0.1s",
            }}
          >
            <Star
              size={20}
              strokeWidth={1.5}
              fill={active ? "#f0a500" : "none"}
            />
          </button>
        );
      })}
      {(hovered || value) > 0 && (
        <span className="ml-1.5 text-[0.75rem]" style={{ color: "var(--color-text-muted)" }}>
          {RATING_LABELS[hovered || value]}
        </span>
      )}
    </div>
  );
}

// ─── SectionBlock ─────────────────────────────────────────────────────────────

function SectionBlock({
  section,
  value,
  onChange,
}: {
  section: Section;
  value: SectionRating;
  onChange: (v: SectionRating) => void;
}) {
  return (
    <div className="space-y-2">
      <div>
        <p className="text-[0.88rem] font-semibold" style={{ color: "var(--color-text)" }}>
          {SECTION_LABELS[section]}
        </p>
        <p className="text-[0.75rem]" style={{ color: "var(--color-text-muted)" }}>
          {SECTION_DESCRIPTIONS[section]}
        </p>
      </div>
      <StarRating
        value={value.rating}
        onChange={(r) => onChange({ ...value, rating: r })}
      />
      {value.rating > 0 && value.rating <= 3 && (
        <textarea
          rows={2}
          value={value.note}
          onChange={(e) => onChange({ ...value, note: e.target.value })}
          placeholder={`What should change? (this will inform future plan generation for ${SECTION_LABELS[section].toLowerCase()})`}
          className="w-full resize-none rounded px-3 py-2 text-[0.84rem] leading-relaxed outline-none"
          style={{
            background: "var(--color-edit)",
            border: "1px solid var(--color-accent)",
            borderRadius: 8,
            color: "var(--color-text)",
            fontFamily: "var(--font-sans)",
          }}
        />
      )}
      {value.rating >= 4 && (
        <textarea
          rows={1}
          value={value.note}
          onChange={(e) => onChange({ ...value, note: e.target.value })}
          placeholder="Optional: any details worth noting for future experiments?"
          className="w-full resize-none rounded px-3 py-2 text-[0.84rem] leading-relaxed outline-none"
          style={{
            background: "var(--color-bg)",
            border: "1px solid var(--color-border)",
            borderRadius: 8,
            color: "var(--color-text)",
            fontFamily: "var(--font-sans)",
          }}
        />
      )}
    </div>
  );
}

// ─── ReviewPanel ──────────────────────────────────────────────────────────────

type Props = {
  exp: Experiment;
  defaultExpType?: string;
};

const EMPTY_SECTION: SectionRating = { rating: 0 as 1, note: "" };

export function ReviewPanel({ exp, defaultExpType = "" }: Props) {
  const [open, setOpen] = useState(false);
  const [submitted, setSubmitted] = useState(false);

  const [expType, setExpType] = useState(defaultExpType);
  const [overall, setOverall] = useState<1 | 2 | 3 | 4 | 5 | 0>(0);
  const [sections, setSections] = useState<Record<Section, SectionRating>>({
    steps: { ...EMPTY_SECTION },
    materials: { ...EMPTY_SECTION },
    timeline: { ...EMPTY_SECTION },
  });

  function updateSection(section: Section, value: SectionRating) {
    setSections((prev) => ({ ...prev, [section]: value }));
  }

  const canSubmit = overall > 0;

  function handleSubmit() {
    if (!canSubmit) return;

    const review: ExperimentReview = {
      experiment_id: exp.id,
      experiment_name: exp.name,
      experiment_type: expType.trim() || exp.name,
      timestamp: new Date().toISOString(),
      overall_rating: overall as 1 | 2 | 3 | 4 | 5,
      sections: {
        steps: sections.steps.rating > 0 ? sections.steps : undefined,
        materials: sections.materials.rating > 0 ? sections.materials : undefined,
        timeline: sections.timeline.rating > 0 ? sections.timeline : undefined,
      },
    };

    saveReview(review);
    setSubmitted(true);
  }

  if (submitted) {
    return (
      <div
        className="flex items-center gap-2 rounded-xl px-4 py-3 text-sm font-medium"
        style={{ background: "var(--color-accent-light)", border: "1px solid var(--color-accent)", color: "var(--color-accent-deep)" }}
      >
        <Check size={15} />
        Review saved — corrections will inform the next plan generated for similar experiments.
      </div>
    );
  }

  return (
    <div
      className="rounded-xl overflow-hidden"
      style={{ border: "1px solid var(--color-border)" }}
    >
      {/* Collapsed header */}
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        className="w-full flex items-center justify-between px-4 py-3 text-left transition hover:bg-[#faf9f7]"
        style={{ background: "var(--color-bg)", border: "none" }}
      >
        <span className="text-[0.84rem] font-semibold" style={{ color: "var(--color-text)" }}>
          Rate &amp; Review
          <span className="ml-2 text-[0.72rem] font-normal" style={{ color: "var(--color-text-muted)" }}>
            — corrections train future plans
          </span>
        </span>
        <motion.span
          animate={{ rotate: open ? 180 : 0 }}
          transition={{ duration: 0.2 }}
          style={{ color: "var(--color-text-muted)" }}
        >
          <ChevronDown size={16} />
        </motion.span>
      </button>

      <AnimatePresence initial={false}>
        {open && (
          <motion.div
            key="review-body"
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.22 }}
            style={{ overflow: "hidden" }}
          >
            <div
              className="px-4 pb-4 pt-3 space-y-5"
              style={{ borderTop: "1px solid var(--color-border)", background: "var(--color-card)" }}
            >
              {/* Experiment type tag */}
              <div>
                <label className="eyebrow mb-1.5 block">Experiment type tag</label>
                <input
                  type="text"
                  value={expType}
                  onChange={(e) => setExpType(e.target.value)}
                  placeholder="e.g. cryopreservation, western blot, PCR…"
                  className="w-full rounded-lg px-3 py-2 text-sm outline-none"
                  style={{
                    border: "1.5px solid var(--color-border)",
                    background: "var(--color-bg)",
                    color: "var(--color-text)",
                    borderRadius: 8,
                  }}
                  onFocus={(e) => (e.target.style.borderColor = "var(--color-accent)")}
                  onBlur={(e) => (e.target.style.borderColor = "var(--color-border)")}
                />
                <p className="mt-1 text-[0.72rem]" style={{ color: "var(--color-text-muted)" }}>
                  Used to match corrections to similar experiments in future generations.
                </p>
              </div>

              {/* Overall */}
              <div className="space-y-1.5">
                <p className="text-[0.88rem] font-semibold" style={{ color: "var(--color-text)" }}>
                  Overall plan quality
                </p>
                <StarRating
                  value={overall}
                  onChange={(r) => setOverall(r)}
                />
              </div>

              <hr style={{ borderColor: "var(--color-border)" }} />

              {/* Per-section ratings */}
              {(["steps", "materials", "timeline"] as Section[]).map((s) => (
                <SectionBlock
                  key={s}
                  section={s}
                  value={sections[s]}
                  onChange={(v) => updateSection(s, v)}
                />
              ))}

              <div className="pt-1">
                <button
                  type="button"
                  onClick={handleSubmit}
                  disabled={!canSubmit}
                  className="px-5 py-2.5 text-sm font-semibold text-white transition hover:opacity-90 disabled:opacity-40 disabled:cursor-not-allowed"
                  style={{ background: "var(--color-bg-dark)", border: "none", borderRadius: 999 }}
                >
                  Submit Review
                </button>
                {!canSubmit && (
                  <p className="mt-1.5 text-[0.72rem]" style={{ color: "var(--color-text-muted)" }}>
                    Set at least an overall rating to submit.
                  </p>
                )}
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
