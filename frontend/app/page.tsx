"use client";

import { FormEvent, useMemo, useState } from "react";
import type { DemoResponse } from "../lib/types";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";
const DEFAULT_HYPOTHESIS =
  "Replacing sucrose with trehalose as a cryoprotectant in the freezing medium will increase post-thaw viability of HeLa cells by at least 15 percentage points compared to the standard DMSO protocol, due to trehalose’s superior membrane stabilization at low temperatures.";

type FeedbackForm = {
  section: string;
  original_text: string;
  correction: string;
  reason: string;
};

export default function HomePage() {
  const [question, setQuestion] = useState(DEFAULT_HYPOTHESIS);
  const [budget, setBudget] = useState("5000 USD");
  const [timeline, setTimeline] = useState("4 weeks");
  const [executionMode, setExecutionMode] = useState("hybrid");
  const [result, setResult] = useState<DemoResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [feedback, setFeedback] = useState<FeedbackForm>({
    section: "protocol",
    original_text: "",
    correction: "",
    reason: ""
  });
  const [feedbackMessage, setFeedbackMessage] = useState<string | null>(null);

  const planId = result?.plan.id ?? null;
  const noveltyClass = `badge ${result?.literature_qc?.novelty_signal ?? "not_found"}`;

  async function runDemo(e?: FormEvent) {
    e?.preventDefault();
    setLoading(true);
    setError(null);
    setFeedbackMessage(null);
    try {
      const response = await fetch(`${API_BASE}/demo/run`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          question,
          constraints: {
            budget,
            timeline,
            execution_mode: executionMode
          }
        })
      });
      if (!response.ok) {
        throw new Error(`Request failed with status ${response.status}`);
      }
      const payload = (await response.json()) as DemoResponse;
      setResult(payload);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unexpected error");
    } finally {
      setLoading(false);
    }
  }

  async function submitFeedback() {
    if (!planId) return;
    setFeedbackMessage(null);
    const response = await fetch(`${API_BASE}/plans/${planId}/feedback`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(feedback)
    });
    if (!response.ok) {
      setFeedbackMessage("Failed to store feedback.");
      return;
    }
    setFeedbackMessage("Feedback stored.");
  }

  async function regeneratePlan() {
    if (!planId) return;
    setLoading(true);
    setFeedbackMessage(null);
    try {
      const response = await fetch(`${API_BASE}/plans/${planId}/regenerate`, { method: "POST" });
      if (!response.ok) throw new Error("Regeneration failed.");
      const payload = (await response.json()) as DemoResponse;
      setResult(payload);
      setFeedbackMessage("Plan regenerated with stored feedback.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unexpected regenerate error");
    } finally {
      setLoading(false);
    }
  }

  const hypothesisEntries = useMemo(() => {
    if (!result) return [];
    return Object.entries(result.hypothesis).filter(([k]) => k !== "raw_input");
  }, [result]);

  return (
    <main className="container">
      <h1 className="title">PredictiveBio Vertical Demo</h1>
      <p className="subtitle">
        Input hypothesis → literature QC → protocol/evidence/risk-aware plan → budget/timeline/validation → feedback-driven regeneration.
      </p>

      <form className="card" onSubmit={runDemo}>
        <h3>Hypothesis Input</h3>
        <textarea className="textarea" value={question} onChange={(e) => setQuestion(e.target.value)} />
        <div className="row" style={{ marginTop: "0.75rem" }}>
          <input className="input" value={budget} onChange={(e) => setBudget(e.target.value)} placeholder="Budget" />
          <input className="input" value={timeline} onChange={(e) => setTimeline(e.target.value)} placeholder="Timeline" />
          <select className="select" value={executionMode} onChange={(e) => setExecutionMode(e.target.value)}>
            <option value="in_house">in_house</option>
            <option value="cro_ready">cro_ready</option>
            <option value="hybrid">hybrid</option>
          </select>
          <button className="button" type="submit" disabled={loading}>
            {loading ? "Running..." : "Run Demo"}
          </button>
        </div>
        {error && <p style={{ color: "#991b1b" }}>{error}</p>}
      </form>

      {result && (
        <>
          <section className="card">
            <h3>Literature QC</h3>
            <p>
              Novelty: <span className={noveltyClass}>{result.literature_qc.novelty_signal}</span>
            </p>
            <p>Confidence: {result.literature_qc.confidence}</p>
            <p>{result.literature_qc.explanation}</p>
            <ul>
              {result.literature_qc.relevant_references.map((ref) => (
                <li key={ref.title}>
                  {ref.title} ({ref.source})
                </li>
              ))}
            </ul>
          </section>

          <section className="card">
            <h3>Structured Hypothesis</h3>
            <ul>
              {hypothesisEntries.map(([key, value]) => (
                <li key={key}>
                  <strong>{key}:</strong> {String(value)}
                </li>
              ))}
            </ul>
          </section>

          <section className="card">
            <h3>Experiment Plan</h3>
            <p>
              <strong>Objective:</strong> {result.plan.objective}
            </p>
            <p>
              <strong>Design:</strong> {result.plan.experimental_design}
            </p>
            <p>
              <strong>Controls:</strong> {result.plan.controls.join(", ")}
            </p>
            <ol>
              {result.plan.step_by_step_protocol.map((step) => (
                <li key={step.step_number}>
                  {step.description} <em>({step.linked_to})</em>
                </li>
              ))}
            </ol>
            <p>
              <strong>Decision Criteria:</strong> {result.plan.decision_criteria.join(" | ")}
            </p>
            <p>
              <strong>Feedback Incorporated:</strong>{" "}
              {result.plan.feedback_incorporated.length ? result.plan.feedback_incorporated.join(" ; ") : "None yet"}
            </p>
          </section>

          <section className="card">
            <h3>Materials</h3>
            <table>
              <thead>
                <tr>
                  <th>Item</th>
                  <th>Supplier</th>
                  <th>Catalog</th>
                  <th>Qty</th>
                  <th>Unit Cost</th>
                  <th>Confidence</th>
                </tr>
              </thead>
              <tbody>
                {result.materials.map((item) => (
                  <tr key={item.name}>
                    <td>{item.name}</td>
                    <td>{item.supplier}</td>
                    <td>{item.catalog_reference ?? "null"}</td>
                    <td>{item.quantity}</td>
                    <td>{item.estimated_unit_cost ?? "n/a"}</td>
                    <td>{item.confidence}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </section>

          <section className="card">
            <h3>Budget Summary</h3>
            <p>
              Estimated Total: {result.budget.estimated_total_cost} {result.budget.currency}
            </p>
            <ul>
              {result.budget.line_items.map((item) => (
                <li key={item.item_name}>
                  {item.item_name}: {item.total_cost_estimate} ({item.confidence})
                </li>
              ))}
            </ul>
          </section>

          <section className="card">
            <h3>Timeline</h3>
            <p>Total Duration: {result.timeline.estimated_total_days} days (incl. buffers)</p>
            <ul>
              {result.timeline.phases.map((phase) => (
                <li key={phase.phase_name}>
                  {phase.phase_name}: {phase.estimated_duration_days}d + {phase.risk_buffer_days}d buffer; deps:{" "}
                  {phase.dependencies.join(", ") || "none"}
                </li>
              ))}
            </ul>
          </section>

          <section className="card">
            <h3>Risk Matrix</h3>
            <table>
              <thead>
                <tr>
                  <th>Risk ID</th>
                  <th>Category</th>
                  <th>Severity</th>
                  <th>Plan Action</th>
                  <th>Mitigation</th>
                </tr>
              </thead>
              <tbody>
                {result.risks.map((risk) => (
                  <tr key={risk.risk_id}>
                    <td>{risk.risk_id}</td>
                    <td>{risk.category}</td>
                    <td>{risk.severity}</td>
                    <td>{risk.plan_action}</td>
                    <td>{risk.required_mitigation}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </section>

          <section className="card">
            <h3>Validation</h3>
            <p>
              <strong>Primary:</strong> {result.validation.primary_endpoint}
            </p>
            <p>
              <strong>Secondary:</strong> {result.validation.secondary_endpoints.join(", ")}
            </p>
            <p>
              <strong>Success Threshold:</strong> {result.validation.success_threshold}
            </p>
            <p>
              <strong>Failure Conditions:</strong> {result.validation.failure_conditions.join(" | ")}
            </p>
            <p>
              <strong>Stats:</strong> {result.validation.suggested_statistical_comparison}
            </p>
          </section>

          <section className="card">
            <h3>Scientist Feedback & Regeneration</h3>
            <div className="row">
              <input
                className="input"
                placeholder="Section"
                value={feedback.section}
                onChange={(e) => setFeedback({ ...feedback, section: e.target.value })}
              />
              <input
                className="input"
                placeholder="Original text"
                value={feedback.original_text}
                onChange={(e) => setFeedback({ ...feedback, original_text: e.target.value })}
              />
            </div>
            <div className="row" style={{ marginTop: "0.75rem" }}>
              <input
                className="input"
                placeholder="Correction"
                value={feedback.correction}
                onChange={(e) => setFeedback({ ...feedback, correction: e.target.value })}
              />
              <input
                className="input"
                placeholder="Reason"
                value={feedback.reason}
                onChange={(e) => setFeedback({ ...feedback, reason: e.target.value })}
              />
            </div>
            <div className="row" style={{ marginTop: "0.75rem" }}>
              <button className="button secondary" type="button" onClick={submitFeedback}>
                Save Feedback
              </button>
              <button className="button" type="button" onClick={regeneratePlan} disabled={loading}>
                Regenerate Plan
              </button>
            </div>
            {feedbackMessage && <p>{feedbackMessage}</p>}
          </section>
        </>
      )}
    </main>
  );
}
