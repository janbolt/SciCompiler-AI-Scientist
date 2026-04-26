import { useState } from "react";
import { ArrowRight, Download } from "lucide-react";
import { MOCK_PLAN } from "../mockData";
import { Modal } from "./Modal";

export function SubmitTab() {
  const [open, setOpen] = useState(false);
  const cro = MOCK_PLAN.experiments.filter((e) => e.cro_compatible);

  return (
    <div className="space-y-5">
      <div
        className="text-center bg-white px-5 py-10"
        style={{ border: "1px solid var(--color-border)", borderRadius: 0 }}
      >
        <h2 className="text-2xl sm:text-3xl font-bold tracking-tight mb-3">
          Ready to Run This Experiment?
        </h2>
        <p className="mx-auto max-w-[520px] text-sm text-[var(--color-muted)] leading-relaxed">
          Submit your full experiment plan to Litmus. Their network of vetted CROs will quote and
          execute the CRO-compatible experiments so you can focus on the science.
        </p>
      </div>

      <button
        type="button"
        onClick={() => setOpen(true)}
        className="flex w-full items-center justify-center gap-2 px-5 py-3.5 text-[0.95rem] font-semibold text-white transition hover:opacity-90"
        style={{
          background: "var(--color-accent)",
          borderRadius: 4,
        }}
      >
        Submit Full Plan to Litmus
        <ArrowRight size={16} strokeWidth={2.5} />
      </button>

      <button
        type="button"
        title="Coming soon"
        className="flex w-full items-center justify-center gap-2 px-5 py-3.5 text-[0.95rem] font-semibold transition hover:bg-[var(--color-accent-light)]"
        style={{
          background: "transparent",
          color: "var(--color-text)",
          border: "1px solid var(--color-border)",
          borderRadius: 4,
        }}
      >
        <Download size={16} strokeWidth={2.5} />
        Download Full Plan (PDF)
      </button>

      <Modal
        open={open}
        title="Confirm submission to Litmus?"
        onCancel={() => setOpen(false)}
        onConfirm={() => setOpen(false)}
        confirmLabel="Submit"
      >
        <div className="space-y-3">
          <div>
            <div className="small-caps mb-1">Hypothesis</div>
            <p className="italic text-sm leading-relaxed">{MOCK_PLAN.hypothesis}</p>
          </div>
          <div>
            <div className="small-caps mb-1">CRO-compatible experiments</div>
            <ul className="space-y-1 text-sm">
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
