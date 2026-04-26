import { useState } from "react";
import { ArrowRight, CheckCircle2, AlertTriangle, Loader2, Download } from "lucide-react";
import { usePlan } from "../context/PlanContext";
import { Modal } from "./Modal";

type LitmusResult = {
  experiment_name: string;
  experiment_type: string;
  litmus_experiment_id: string | null;
  status: string;
  estimated_cost_usd: number | null;
  estimated_turnaround_days: number | null;
  error: string | null;
};

type LitmusResponse = {
  results: LitmusResult[];
  total_submitted: number;
  total_errors: number;
};

export function SubmitTab() {
  const { hypothesis, experiments } = usePlan();
  const cro = experiments.filter((e) => e.cro_compatible);

  const [open, setOpen] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [litmusData, setLitmusData] = useState<LitmusResponse | null>(null);
  const [errorMsg, setErrorMsg] = useState<string>("");

  async function handleSubmit() {
    setSubmitting(true);
    setOpen(false);
    setErrorMsg("");
    setLitmusData(null);

    try {
      const res = await fetch("/api/litmus/submit", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          hypothesis,
          experiment_ids: cro.map((e) => e.id),
          experiments,
        }),
      });

      if (!res.ok) {
        const body = await res.json().catch(() => ({ detail: res.statusText }));
        throw new Error(body.detail ?? res.statusText);
      }

      const data: LitmusResponse = await res.json();
      setLitmusData(data);
    } catch (err) {
      setErrorMsg(err instanceof Error ? err.message : "Unexpected error");
    } finally {
      setSubmitting(false);
    }
  }
  return (
    <div className="space-y-4">
      <div
        className="rounded-2xl px-6 py-10 sm:py-14 text-center space-y-4"
        style={{ background: "var(--color-bg-dark)" }}
      >
        <div className="eyebrow" style={{ color: "var(--color-accent)" }}>
          Ready to Run
        </div>
        <h2
          className="text-3xl sm:text-4xl font-bold leading-[1.1] tracking-tight text-white"
          style={{ fontFamily: "var(--font-serif)" }}
        >
          Submit Your Experiment<br />Plan to Litmus
        </h2>
        <p
          className="mx-auto max-w-[480px] text-[0.9rem] leading-relaxed"
          style={{ color: "rgba(255,255,255,0.65)" }}
        >
          Their network of vetted CROs will quote and execute the CRO-compatible
          experiments so you can focus on the science.
        </p>
      </div>

      <button
        type="button"
        onClick={() => setOpen(true)}
        disabled={cro.length === 0 || submitting}
        className="flex w-full items-center justify-center gap-2 px-5 py-3.5 text-[0.95rem] font-semibold text-white transition hover:opacity-90 active:scale-[0.98] disabled:opacity-40 disabled:cursor-not-allowed"
        style={{
          background: "var(--color-accent)",
          border: "none",
          borderRadius: 999,
        }}
      >
        {submitting ? (
          <>
            <Loader2 size={16} className="animate-spin" />
            Submitting...
          </>
        ) : (
          <>
            Submit Full Plan to Litmus
            <ArrowRight size={16} strokeWidth={2.5} />
          </>
        )}
      </button>

      <button
        type="button"
        title="Coming soon"
        className="flex w-full items-center justify-center gap-2 px-5 py-3.5 text-[0.95rem] font-medium transition hover:opacity-70"
        style={{
          background: "transparent",
          color: "var(--color-text-muted)",
          border: "1.5px solid var(--color-border)",
          borderRadius: 999,
        }}
      >
        <Download size={16} strokeWidth={2.5} />
        Download Full Plan (PDF)
        <span className="tag-coral ml-1">Coming soon</span>
      </button>

      {errorMsg && (
        <section
          className="card px-5 py-4 flex items-start gap-3"
          style={{ borderLeft: "4px solid var(--color-badge-red)" }}
        >
          <AlertTriangle size={18} className="mt-0.5 flex-shrink-0" style={{ color: "var(--color-badge-red)" }} />
          <div className="space-y-1">
            <p className="text-sm" style={{ color: "var(--color-text)" }}>{errorMsg}</p>
            {errorMsg.includes("LITMUS_API_KEY") && (
              <p className="text-xs" style={{ color: "var(--color-text-muted)" }}>
                Set <code className="font-mono">LITMUS_API_KEY=lk_your_key</code> in the backend environment and restart the server.
              </p>
            )}
          </div>
        </section>
      )}

      {litmusData && (
        <section className="card px-5 py-4 space-y-2">
          <div className="flex items-center gap-2">
            <CheckCircle2 size={16} style={{ color: "var(--color-accent)" }} />
            <p className="text-sm font-semibold" style={{ color: "var(--color-text)" }}>
              Submitted {litmusData.total_submitted} of {litmusData.results.length} experiment
              {litmusData.results.length !== 1 ? "s" : ""}.
            </p>
          </div>
          {litmusData.total_errors > 0 && (
            <p className="text-sm" style={{ color: "var(--color-text-muted)" }}>
              {litmusData.total_errors} submission{litmusData.total_errors !== 1 ? "s" : ""} returned errors.
            </p>
          )}
        </section>
      )}

      <Modal
        open={open}
        title="Submit Full Plan to Litmus?"
        onCancel={() => setOpen(false)}
        onConfirm={handleSubmit}
        confirmLabel="Submit"
      >
        <div className="space-y-4">
          <div>
            <div className="eyebrow mb-1.5">Hypothesis</div>
            <p className="italic text-sm leading-relaxed" style={{ color: "var(--color-text)" }}>
              {hypothesis}
            </p>
          </div>
          <div>
            <div className="eyebrow mb-1.5">CRO-compatible experiments</div>
            <ul className="space-y-1 text-sm" style={{ color: "var(--color-text)" }}>
              {cro.map((e) => (
                <li key={e.id}>• {e.name}</li>
              ))}
            </ul>
          </div>
        </div>
      </Modal>
    </div>
  );
}
