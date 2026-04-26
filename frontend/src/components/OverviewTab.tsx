import { MOCK_PLAN } from "../mockData";

const NOVELTY_STYLES: Record<
  string,
  { label: string; bg: string; bar: string }
> = {
  "not found": {
    label: "NOT FOUND",
    bg: "var(--color-badge-green)",
    bar: "var(--color-badge-green)",
  },
  "similar work exists": {
    label: "SIMILAR WORK EXISTS",
    bg: "var(--color-badge-amber)",
    bar: "var(--color-badge-amber)",
  },
  "exact match found": {
    label: "EXACT MATCH FOUND",
    bg: "var(--color-badge-red)",
    bar: "var(--color-badge-red)",
  },
};

export function OverviewTab() {
  const { references, novelty_signal, hypothesis, objective, total_duration_days, total_budget_eur, phases } =
    MOCK_PLAN;
  const novelty = NOVELTY_STYLES[novelty_signal];
  const totalPhaseDays = phases.reduce((sum, p) => sum + p.days, 0);

  return (
    <div className="space-y-6">
      {/* Literature QC Card */}
      <section
        className="bg-white"
        style={{
          border: "1px solid var(--color-border)",
          borderLeft: `3px solid ${novelty.bar}`,
          borderRadius: 0,
        }}
      >
        <div className="flex items-center justify-between px-5 py-4 gap-3">
          <span className="small-caps">Literature QC</span>
          <span
            className="px-2.5 py-1 text-[0.7rem] font-bold uppercase tracking-wider text-white"
            style={{ background: novelty.bg, borderRadius: 0 }}
          >
            {novelty.label}
          </span>
        </div>
        <div className="divider" />
        <div className="px-5 py-4 space-y-3">
          <p className="text-sm text-[var(--color-muted)]">{references.length} relevant references found</p>
          <ol className="space-y-2.5 text-sm">
            {references.map((ref, i) => (
              <li key={ref.doi} className="leading-snug">
                <span className="font-mono text-xs text-[var(--color-muted)] mr-2">{i + 1}.</span>
                {ref.citation}
                <div className="mt-0.5 ml-6 font-mono text-xs text-[var(--color-muted)]">
                  doi:{" "}
                  <a
                    href={`https://doi.org/${ref.doi}`}
                    target="_blank"
                    rel="noreferrer"
                    className="underline hover:text-[var(--color-accent)]"
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
      <section
        className="bg-white"
        style={{ border: "1px solid var(--color-border)", borderRadius: 0 }}
      >
        <div className="px-5 py-4 space-y-4">
          <div>
            <div className="small-caps mb-1.5">Hypothesis</div>
            <p className="italic text-sm leading-relaxed">{hypothesis}</p>
          </div>
          <div className="divider" />
          <div>
            <div className="small-caps mb-1.5">Objective</div>
            <p className="text-sm leading-relaxed">{objective}</p>
          </div>
          <div className="divider" />
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 pt-1">
            <div>
              <div className="small-caps mb-1">Total Duration</div>
              <div className="flex items-baseline gap-1.5">
                <span className="text-3xl font-bold tracking-tight">{total_duration_days}</span>
                <span className="text-sm text-[var(--color-muted)]">days</span>
              </div>
            </div>
            <div>
              <div className="small-caps mb-1">Estimated Budget</div>
              <div className="flex items-baseline gap-1.5">
                <span className="text-3xl font-bold tracking-tight">
                  €{total_budget_eur.toLocaleString("en-US")}
                </span>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* Phase Timeline Bar */}
      <section className="space-y-2">
        <div className="small-caps">Phase Timeline</div>
        <div className="flex w-full overflow-hidden" style={{ height: 32, gap: 2 }}>
          {phases.map((phase) => {
            const widthPct = (phase.days / totalPhaseDays) * 100;
            return (
              <div
                key={phase.name}
                className="flex items-center justify-center text-[0.7rem] font-semibold text-white px-1.5"
                style={{
                  background: "var(--color-accent)",
                  width: `${widthPct}%`,
                  minWidth: 0,
                  whiteSpace: "nowrap",
                  overflow: "hidden",
                  textOverflow: "ellipsis",
                }}
                title={`${phase.name} (${phase.days}d)`}
              >
                {phase.name} ({phase.days}d)
              </div>
            );
          })}
        </div>
      </section>
    </div>
  );
}
