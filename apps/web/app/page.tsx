"use client";
import { useState } from "react";

const SAMPLES = [
  { id: "diag", label: "Diagnostics", text: "A paper-based electrochemical biosensor functionalized with anti-CRP antibodies will detect C-reactive protein in whole blood at concentrations below 0.5 mg/L within 10 minutes, matching laboratory ELISA sensitivity without requiring sample preprocessing." },
  { id: "gut", label: "Gut Health", text: "Supplementing C57BL/6 mice with Lactobacillus rhamnosus GG for 4 weeks will reduce intestinal permeability by at least 30% compared to controls, measured by FITC-dextran assay, due to upregulation of tight junction proteins claudin-1 and occludin." },
  { id: "cell", label: "Cell Biology", text: "Replacing sucrose with trehalose as a cryoprotectant in the freezing medium will increase post-thaw viability of HeLa cells by at least 15 percentage points compared to the standard DMSO protocol, due to trehalose's superior membrane stabilization at low temperatures." },
  { id: "climate", label: "Climate", text: "Introducing Sporomusa ovata into a bioelectrochemical system at a cathode potential of -400mV vs SHE will fix CO2 into acetate at a rate of at least 150 mmol/L/day, outperforming current biocatalytic carbon capture benchmarks by at least 20%." },
];

const NOVELTY_STYLES: Record<string, string> = {
  not_found: "bg-emerald-100 text-emerald-800 border-emerald-300",
  similar_work_exists: "bg-amber-100 text-amber-800 border-amber-300",
  exact_match_found: "bg-rose-100 text-rose-800 border-rose-300",
};

const SEVERITY_STYLES: Record<string, string> = {
  low: "bg-slate-100 text-slate-700",
  moderate: "bg-amber-100 text-amber-800",
  high: "bg-orange-200 text-orange-900",
  critical: "bg-rose-200 text-rose-900",
};

export default function Home() {
  const [q, setQ] = useState(SAMPLES[0].text);
  const [out, setOut] = useState<any>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function run() {
    setLoading(true); setError(null); setOut(null);
    try {
      const r = await fetch("/api/demo/run", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ scientific_question: q, constraints: {} }),
      });
      if (!r.ok) throw new Error(await r.text());
      setOut(await r.json());
    } catch (e: any) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="mx-auto max-w-5xl p-6 md:p-10 space-y-8">
      <header className="space-y-1">
        <h1 className="text-3xl font-bold tracking-tight">PredictiveBio</h1>
        <p className="text-slate-600">Hypothesis → runnable experiment plan, with literature QC and risk-aware revision.</p>
      </header>

      <section className="space-y-3">
        <div className="flex flex-wrap gap-2">
          {SAMPLES.map((s) => (
            <button key={s.id} onClick={() => setQ(s.text)}
              className="text-xs border border-slate-300 hover:border-slate-500 rounded-full px-3 py-1">
              {s.label}
            </button>
          ))}
        </div>
        <textarea value={q} onChange={(e) => setQ(e.target.value)} rows={5}
          className="w-full border border-slate-300 rounded-lg p-3 font-mono text-sm focus:outline-none focus:ring-2 focus:ring-slate-400"
          placeholder="Enter a scientific hypothesis..." />
        <button onClick={run} disabled={loading || !q.trim()}
          className="bg-slate-900 text-white px-5 py-2 rounded-lg font-medium disabled:opacity-50 hover:bg-slate-700">
          {loading ? "Generating plan (30-60s)..." : "Generate experiment plan"}
        </button>
        {error && <div className="text-sm text-rose-700 bg-rose-50 border border-rose-200 rounded p-3">{error}</div>}
      </section>

      {out && <Output data={out} />}
    </main>
  );
}

function Output({ data }: { data: any }) {
  const { hypothesis, literature_qc, protocol_candidates, evidence_claims, risks, plan } = data;
  return (
    <div className="space-y-6">
      <Card title="Structured hypothesis">
        <dl className="grid grid-cols-1 md:grid-cols-2 gap-x-6 gap-y-2 text-sm">
          {Object.entries({
            organism_or_model: hypothesis.organism_or_model,
            intervention: hypothesis.intervention,
            outcome: hypothesis.outcome,
            measurable_endpoint: hypothesis.measurable_endpoint,
            expected_effect_size: hypothesis.expected_effect_size,
            mechanism: hypothesis.mechanism,
            control_condition: hypothesis.control_condition,
            experiment_type: hypothesis.experiment_type,
          }).map(([k, v]) => (
            <div key={k} className="border-b border-slate-100 py-1">
              <dt className="text-slate-500 font-mono text-xs">{k}</dt>
              <dd>{(v as any) || <span className="text-slate-400">—</span>}</dd>
            </div>
          ))}
        </dl>
        {hypothesis.missing_fields?.length > 0 && (
          <div className="mt-3 text-xs text-amber-700">
            Missing: {hypothesis.missing_fields.join(", ")}
          </div>
        )}
      </Card>

      <Card title="Literature QC"
        right={<span className={`px-3 py-1 rounded-full text-xs font-semibold border ${NOVELTY_STYLES[literature_qc.novelty_signal] || ""}`}>
          {literature_qc.novelty_signal} · {(literature_qc.confidence * 100).toFixed(0)}%
        </span>}>
        <p className="text-sm text-slate-700 mb-3">{literature_qc.explanation}</p>
        <p className="text-xs text-slate-500 italic mb-3">→ {literature_qc.recommended_action}</p>
        <ul className="space-y-1 text-sm">
          {literature_qc.relevant_references.map((r: any) => (
            <li key={r.id}>
              <a href={r.url} target="_blank" rel="noreferrer" className="text-blue-700 hover:underline">{r.title}</a>
              <span className="text-slate-500 text-xs"> · {r.source} {r.year ? `(${r.year})` : ""}</span>
            </li>
          ))}
        </ul>
      </Card>

      <Card title={`Protocol candidates (${protocol_candidates.length})`}>
        <ul className="space-y-2 text-sm">
          {protocol_candidates.map((p: any) => (
            <li key={p.id} className="border-l-2 border-slate-300 pl-3">
              <div className="font-medium">{p.title}</div>
              <div className="text-xs text-slate-500">
                {p.source} · match {(p.match_score * 100).toFixed(0)}% · confidence {(p.confidence * 100).toFixed(0)}%
              </div>
              {p.adaptation_need && <div className="text-xs text-slate-600 mt-1">Adapt: {p.adaptation_need}</div>}
            </li>
          ))}
        </ul>
      </Card>

      <Card title={`Evidence claims (${evidence_claims.length})`}>
        <ul className="space-y-1 text-sm">
          {evidence_claims.map((c: any, i: number) => (
            <li key={i} className="flex gap-2">
              <span className={`text-xs px-2 py-0.5 rounded font-mono ${c.evidence_type === "unvalidated_assumption" ? "bg-amber-100 text-amber-800" : "bg-slate-100 text-slate-700"}`}>
                {c.evidence_type} · {c.strength}
              </span>
              <span>{c.claim}</span>
            </li>
          ))}
        </ul>
      </Card>

      <Card title={`Risk matrix (${risks.length})`}>
        <ul className="space-y-2 text-sm">
          {risks.map((r: any) => (
            <li key={r.risk_id} className="border border-slate-200 rounded p-2">
              <div className="flex items-center gap-2 mb-1">
                <span className={`text-xs px-2 py-0.5 rounded font-semibold ${SEVERITY_STYLES[r.severity] || ""}`}>{r.severity}</span>
                <span className="text-xs text-slate-500 font-mono">{r.category}</span>
                <span className="text-xs text-slate-400">→ {r.plan_action}</span>
              </div>
              <div>{r.description}</div>
              <div className="text-xs text-slate-600 mt-1">Mitigation: {r.required_mitigation}</div>
            </li>
          ))}
        </ul>
      </Card>

      <Card title={plan.title} right={<span className="text-xs text-slate-500">confidence {(plan.confidence_score * 100).toFixed(0)}%</span>}>
        <p className="text-sm text-slate-700 mb-4">{plan.objective}</p>

        <h3 className="font-semibold text-sm mt-4 mb-2">Protocol</h3>
        <ol className="space-y-2 text-sm">
          {plan.protocol_steps.map((s: any) => (
            <li key={s.order} className="border-l-2 border-blue-300 pl-3">
              <div className="font-medium">{s.order}. {s.title}{s.duration_min ? ` (${s.duration_min} min)` : ""}</div>
              <div className="text-slate-700">{s.description}</div>
              {s.notes && <div className="text-xs text-slate-500 mt-1 italic">{s.notes}</div>}
            </li>
          ))}
        </ol>

        <h3 className="font-semibold text-sm mt-6 mb-2">Materials</h3>
        <table className="w-full text-xs border border-slate-200">
          <thead className="bg-slate-50">
            <tr>
              <th className="text-left p-2">Item</th>
              <th className="text-left p-2">Supplier</th>
              <th className="text-left p-2">Catalog #</th>
              <th className="text-left p-2">Qty</th>
              <th className="text-left p-2">Verified</th>
            </tr>
          </thead>
          <tbody>
            {plan.materials.map((m: any, i: number) => (
              <tr key={i} className="border-t border-slate-100">
                <td className="p-2">{m.name}</td>
                <td className="p-2">{m.supplier || "—"}</td>
                <td className="p-2 font-mono">{m.catalog_number || <span className="text-slate-400">candidate</span>}</td>
                <td className="p-2">{m.quantity || "—"}</td>
                <td className="p-2">{m.verified ? "✓" : "—"}</td>
              </tr>
            ))}
          </tbody>
        </table>

        <h3 className="font-semibold text-sm mt-6 mb-2">Budget · {plan.budget.currency} {plan.budget.total.toFixed(2)}</h3>
        <table className="w-full text-xs border border-slate-200">
          <thead className="bg-slate-50">
            <tr>
              <th className="text-left p-2">Item</th><th className="text-left p-2">Supplier</th>
              <th className="text-right p-2">Qty</th><th className="text-right p-2">Unit</th>
              <th className="text-right p-2">Total</th><th className="text-left p-2">Conf.</th>
            </tr>
          </thead>
          <tbody>
            {plan.budget.items.map((b: any, i: number) => (
              <tr key={i} className="border-t border-slate-100">
                <td className="p-2">{b.item_name}</td>
                <td className="p-2">{b.supplier || "—"}</td>
                <td className="p-2 text-right">{b.quantity}</td>
                <td className="p-2 text-right">${b.unit_cost.toFixed(2)}</td>
                <td className="p-2 text-right font-medium">${b.total_cost.toFixed(2)}</td>
                <td className="p-2">{b.confidence}</td>
              </tr>
            ))}
          </tbody>
        </table>

        <h3 className="font-semibold text-sm mt-6 mb-2">Timeline</h3>
        <ul className="space-y-1 text-sm">
          {plan.timeline.phases.map((p: any, i: number) => (
            <li key={i} className="flex justify-between border-b border-slate-100 py-1">
              <div>
                <span className="font-medium">{p.name}</span>
                {p.dependencies?.length > 0 && <span className="text-xs text-slate-500"> · after: {p.dependencies.join(", ")}</span>}
              </div>
              <div className="text-xs text-slate-600">{p.duration_days}d {p.risk_buffer_days ? `(+${p.risk_buffer_days} buffer)` : ""}</div>
            </li>
          ))}
        </ul>

        {plan.validation && (
          <>
            <h3 className="font-semibold text-sm mt-6 mb-2">Validation</h3>
            <dl className="text-sm space-y-1">
              <div><dt className="inline text-slate-500">Primary endpoint: </dt><dd className="inline">{plan.validation.primary_endpoint}</dd></div>
              {plan.validation.secondary_endpoints?.length > 0 && (
                <div><dt className="inline text-slate-500">Secondary: </dt><dd className="inline">{plan.validation.secondary_endpoints.join("; ")}</dd></div>
              )}
              {plan.validation.positive_control && <div><dt className="inline text-slate-500">+ control: </dt><dd className="inline">{plan.validation.positive_control}</dd></div>}
              {plan.validation.negative_control && <div><dt className="inline text-slate-500">− control: </dt><dd className="inline">{plan.validation.negative_control}</dd></div>}
              {plan.validation.statistical_test && <div><dt className="inline text-slate-500">Stats: </dt><dd className="inline">{plan.validation.statistical_test}</dd></div>}
              {plan.validation.success_threshold && <div><dt className="inline text-slate-500">Success: </dt><dd className="inline">{plan.validation.success_threshold}</dd></div>}
            </dl>
          </>
        )}
      </Card>
    </div>
  );
}

function Card({ title, right, children }: { title: string; right?: React.ReactNode; children: React.ReactNode }) {
  return (
    <section className="border border-slate-200 rounded-xl bg-white p-5 shadow-sm">
      <div className="flex items-center justify-between mb-3">
        <h2 className="font-semibold text-lg">{title}</h2>
        {right}
      </div>
      {children}
    </section>
  );
}
