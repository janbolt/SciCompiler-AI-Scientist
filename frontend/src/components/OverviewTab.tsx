import { RefreshCw } from "lucide-react";
import { usePlan } from "../context/PlanContext";

type Props = {
  onRegenerate?: () => void;
};

const NOVELTY_STYLES: Record<
  string,
  { label: string; bg: string; bar: string; text: string }
> = {
  "not found": {
    label: "NOT FOUND",
    bg: "var(--color-badge-green)",
    bar: "var(--color-badge-green)",
    text: "#fff",
  },
  "similar work exists": {
    label: "SIMILAR WORK EXISTS",
    bg: "var(--color-coral-light)",
    bar: "var(--color-coral)",
    text: "var(--color-coral)",
  },
  "exact match found": {
    label: "EXACT MATCH FOUND",
    bg: "#fde8e8",
    bar: "var(--color-badge-red)",
    text: "var(--color-badge-red)",
  },
};

type ConfidenceLevel = { label: string; color: string; bg: string; text: string };

function getConfidenceLevel(score: number): ConfidenceLevel {
  if (score >= 0.7) {
    return {
      label: "HIGH CONFIDENCE",
      color: "var(--color-badge-green)",
      bg: "rgba(22,163,74,0.08)",
      text: "#166534",
    };
  }
  if (score >= 0.4) {
    return {
      label: "MEDIUM CONFIDENCE",
      color: "#d97706",
      bg: "rgba(217,119,6,0.08)",
      text: "#92400e",
    };
  }
  return {
    label: "LOW CONFIDENCE",
    color: "var(--color-badge-red)",
    bg: "rgba(220,38,38,0.08)",
    text: "#991b1b",
  };
}

export function OverviewTab({ onRegenerate }: Props) {
  const { references, novelty_signal, hypothesis, objective, budget, phases, confidence_score } = usePlan();
  const novelty = NOVELTY_STYLES[novelty_signal];
  const totalPhaseDays = phases.reduce((sum, p) => sum + p.days, 0);
  const totalBudgetEur = budget.total_eur;

  const pct = Math.round((confidence_score ?? 0) * 100);
  const conf = getConfidenceLevel(confidence_score ?? 0);

  return (
    <div className="space-y-6">
      {/* Plan Confidence Card */}
      <section
        className="card overflow-hidden"
        style={{ borderLeft: `4px solid ${conf.color}` }}
      >
        <div className="flex items-center justify-between px-5 py-4 gap-3">
          <span className="eyebrow">Plan Confidence</span>
          <span
            className="px-3 py-1 text-[0.65rem] font-bold uppercase tracking-wider"
            style={{
              background: conf.bg,
              color: conf.text,
              borderRadius: 999,
            }}
          >
            {conf.label}
          </span>
        </div>
        <div className="divider" />
        <div className="px-5 py-5 space-y-4">
          {/* Score + bar */}
          <div className="flex items-center gap-4">
            <span
              className="text-5xl font-bold tracking-tight flex-shrink-0"
              style={{ fontFamily: "var(--font-serif)", color: conf.color }}
            >
              {pct}%
            </span>
            <div className="flex-1 space-y-1.5 min-w-0">
              <div
                className="w-full overflow-hidden"
                style={{ height: 10, background: "var(--color-border)", borderRadius: 999 }}
              >
                <div
                  style={{
                    height: "100%",
                    width: `${pct}%`,
                    background: conf.color,
                    borderRadius: 999,
                    transition: "width 0.6s ease",
                  }}
                />
              </div>
              <p className="text-[0.75rem]" style={{ color: "var(--color-text-muted)" }}>
                Based on protocol fit and execution readiness
              </p>
            </div>
          </div>

          {/* Regenerate button */}
          {onRegenerate && (
            <div className="pt-1">
              <button
                type="button"
                onClick={onRegenerate}
                className="inline-flex items-center gap-2 px-4 py-2 text-[0.84rem] font-semibold transition hover:opacity-80"
                style={{
                  background: "var(--color-accent-light)",
                  color: "var(--color-accent-deep)",
                  border: "1.5px solid var(--color-accent)",
                  borderRadius: 999,
                }}
              >
                <RefreshCw size={13} strokeWidth={2.5} />
                Regenerate Plan
              </button>
              <p className="mt-1.5 text-[0.72rem]" style={{ color: "var(--color-text-muted)" }}>
                Uses your saved reviews and corrections to improve the plan.
              </p>
            </div>
          )}
        </div>
      </section>

      {/* Literature QC Card */}
      <section
        className="card overflow-hidden"
        style={{ borderLeft: `4px solid ${novelty.bar}` }}
      >
        <div className="flex items-center justify-between px-5 py-4 gap-3">
          <span className="eyebrow">Literature QC</span>
          <span
            className="px-3 py-1 text-[0.65rem] font-bold uppercase tracking-wider"
            style={{
              background: novelty.bg,
              color: novelty.text,
              borderRadius: 999,
            }}
          >
            {novelty.label}
          </span>
        </div>
        <div className="divider" />
        <div className="px-5 py-5 space-y-4">
          <p className="text-sm" style={{ color: "var(--color-text-muted)" }}>
            {references.length} relevant references found
          </p>
          <ol className="space-y-4 text-sm">
            {references.map((ref, i) => (
              <li key={ref.doi} className="leading-snug">
                <span
                  className="mr-2"
                  style={{ fontFamily: "var(--font-mono)", fontSize: "0.72rem", color: "var(--color-text-muted)" }}
                >
                  {i + 1}.
                </span>
                <span style={{ color: "var(--color-text)" }}>{ref.citation}</span>
                <div
                  className="mt-1 ml-5"
                  style={{ fontFamily: "var(--font-mono)", fontSize: "0.72rem", color: "var(--color-text-muted)" }}
                >
                  doi:{" "}
                  <a
                    href={`https://doi.org/${ref.doi}`}
                    target="_blank"
                    rel="noreferrer"
                    className="underline transition hover:text-[var(--color-accent)]"
                  >
                    {ref.doi}
                  </a>
                </div>
              </li>
            ))}
          </ol>
        </div>
      </section>

      {/* Plan Summary Card */}
      <section className="card px-5 py-5 space-y-5">
        <div>
          <div className="eyebrow mb-2">Hypothesis</div>
          <p className="italic text-sm leading-relaxed" style={{ color: "var(--color-text)" }}>
            {hypothesis}
          </p>
        </div>
        <div className="divider" />
        <div>
          <div className="eyebrow mb-2">Objective</div>
          <p className="text-sm leading-relaxed" style={{ color: "var(--color-text)" }}>
            {objective}
          </p>
        </div>
        <div className="divider" />
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-5 pt-1">
          <div>
            <div className="eyebrow mb-2">Total Duration</div>
            <div className="flex items-baseline gap-1.5">
              <span
                className="text-4xl font-bold tracking-tight"
                style={{ fontFamily: "var(--font-serif)" }}
              >
                {totalPhaseDays}
              </span>
              <span className="text-sm" style={{ color: "var(--color-text-muted)" }}>
                days
              </span>
            </div>
          </div>
          <div>
            <div className="eyebrow mb-2">Estimated Budget</div>
            <div className="flex items-baseline gap-1">
              <span
                className="text-4xl font-bold tracking-tight"
                style={{ fontFamily: "var(--font-serif)" }}
              >
                €{totalBudgetEur.toLocaleString("en-US")}
              </span>
            </div>
          </div>
        </div>
      </section>

      {/* Phase Timeline */}
      <section className="card px-5 py-4 space-y-2.5">
        <div className="eyebrow mb-3">Phase Timeline</div>
        {phases.map((phase, i) => {
          const widthPct = Math.max((phase.days / totalPhaseDays) * 100, 2);
          return (
            <div key={phase.name} className="flex items-center gap-3">
              <span
                className="w-5 flex-shrink-0 text-right text-[0.65rem]"
                style={{ fontFamily: "var(--font-mono)", color: "var(--color-accent-label)" }}
              >
                {String(i + 1).padStart(2, "0")}
              </span>
              <span
                className="w-36 sm:w-48 flex-shrink-0 text-[0.82rem] font-medium truncate"
                style={{ color: "var(--color-text)" }}
                title={phase.name}
              >
                {phase.name}
              </span>
              <div className="flex-1 min-w-0" style={{ height: 8, background: "var(--color-border)", borderRadius: 999 }}>
                <div
                  style={{
                    height: "100%",
                    width: `${widthPct}%`,
                    background: "var(--color-bg-dark)",
                    borderRadius: 999,
                  }}
                />
              </div>
              <span
                className="w-8 flex-shrink-0 text-right text-[0.72rem]"
                style={{ fontFamily: "var(--font-mono)", color: "var(--color-accent-label)" }}
              >
                {phase.days}d
              </span>
            </div>
          );
        })}
      </section>
    </div>
  );
}
