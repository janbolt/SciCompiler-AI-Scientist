import { useMemo, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { ChevronDown, Pencil, ArrowRight, Check, Plus, Trash2, AlertTriangle, FlaskConical } from "lucide-react";
import { Experiment, Material } from "../mockData";
import { usePlan } from "../context/PlanContext";
import { EditedMaterial, saveExpFeedback, splitQty } from "../lib/feedbackStore";
import { Modal } from "./Modal";
import { BenchlingExportModal } from "./BenchlingExportModal";
import { ReviewPanel } from "./ReviewPanel";

export function ExperimentsTab() {
  const { experiments, hypothesis } = usePlan();

  const [expandedId, setExpandedId] = useState<string | null>(experiments[0]?.id ?? null);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [singleSubmitId, setSingleSubmitId] = useState<string | null>(null);
  const [batchModalOpen, setBatchModalOpen] = useState(false);
  const [benchlingOpen, setBenchlingOpen] = useState(false);

  const croCompatible = useMemo(() => experiments.filter((e) => e.cro_compatible), [experiments]);

  function toggleSelect(id: string) {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  const selectedExperiments = experiments.filter((e) => selected.has(e.id));

  return (
    <div className="space-y-5">
      {/* Toolbar row */}
      <section className="card p-4 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
        <p className="text-sm" style={{ color: "var(--color-text-muted)" }}>
          {croCompatible.length > 0
            ? "Select CRO-compatible experiments to outsource, or export the full plan to Benchling."
            : "Review protocols and export the full plan to Benchling."}
        </p>
        <div className="flex flex-wrap gap-2">
          {croCompatible.length > 0 && (
            <button
              type="button"
              disabled={selected.size === 0}
              onClick={() => setBatchModalOpen(true)}
              className="inline-flex items-center gap-2 px-4 py-2 text-sm font-semibold transition disabled:cursor-not-allowed disabled:opacity-40 hover:opacity-80"
              style={{
                background: "transparent",
                color: "var(--color-accent-deep)",
                border: "1.5px solid var(--color-accent)",
                borderRadius: 999,
              }}
            >
              Submit selected to Litmus
              <ArrowRight size={14} strokeWidth={2.5} />
            </button>
          )}
          <button
            type="button"
            onClick={() => setBenchlingOpen(true)}
            className="inline-flex items-center gap-2 px-4 py-2 text-sm font-semibold text-white transition hover:opacity-90"
            style={{
              background: "var(--color-bg-dark)",
              border: "none",
              borderRadius: 999,
            }}
          >
            <FlaskConical size={14} />
            Export to Benchling
          </button>
        </div>
      </section>

      <ul className="space-y-3">
        {experiments.map((exp) => (
          <ExperimentCard
            key={exp.id}
            exp={exp}
            expanded={expandedId === exp.id}
            onToggleExpand={() => setExpandedId((cur) => (cur === exp.id ? null : exp.id))}
            editing={editingId === exp.id}
            onToggleEdit={() => setEditingId((cur) => (cur === exp.id ? null : exp.id))}
            onStopEdit={() => setEditingId(null)}
            selected={selected.has(exp.id)}
            onToggleSelect={() => toggleSelect(exp.id)}
            onSubmit={() => setSingleSubmitId(exp.id)}
          />
        ))}
      </ul>

      <Modal
        open={batchModalOpen}
        title="Confirm submission to Litmus?"
        onCancel={() => setBatchModalOpen(false)}
        onConfirm={() => { setBatchModalOpen(false); setSelected(new Set()); }}
        confirmLabel="Submit"
      >
        <p className="text-sm mb-3" style={{ color: "var(--color-text-muted)" }}>
          The following experiments will be sent to Litmus for CRO quotation:
        </p>
        <ul className="space-y-1 text-sm" style={{ color: "var(--color-text)" }}>
          {selectedExperiments.map((e) => <li key={e.id}>• {e.name}</li>)}
        </ul>
      </Modal>

      <Modal
        open={singleSubmitId !== null}
        title={singleSubmitId
          ? `Submit ${experiments.find((e) => e.id === singleSubmitId)?.name} to Litmus for CRO outsourcing?`
          : ""}
        onCancel={() => setSingleSubmitId(null)}
        onConfirm={() => setSingleSubmitId(null)}
        confirmLabel="Submit"
      />

      <BenchlingExportModal
        open={benchlingOpen}
        onClose={() => setBenchlingOpen(false)}
        hypothesis={hypothesis}
        experiments={experiments}
      />
    </div>
  );
}

// ─── helpers ──────────────────────────────────────────────────────────────────

function toEdited(m: Material): EditedMaterial {
  const { qty_amount, qty_unit } = splitQty(m.qty);
  return {
    name: m.name, catalog: m.catalog, supplier: m.supplier,
    qty_amount, qty_unit, unit_cost_eur: m.unit_cost_eur, total_eur: m.total_eur,
  };
}

// ─── ExperimentCard ───────────────────────────────────────────────────────────

type CardProps = {
  exp: Experiment;
  expanded: boolean;
  onToggleExpand: () => void;
  editing: boolean;
  onToggleEdit: () => void;
  onStopEdit: () => void;
  selected: boolean;
  onToggleSelect: () => void;
  onSubmit: () => void;
};

function ExperimentCard({
  exp, expanded, onToggleExpand,
  editing, onToggleEdit, onStopEdit,
  selected, onToggleSelect, onSubmit,
}: CardProps) {
  // Always initialise from the plan data — never from localStorage.
  // localStorage is write-only from the UI's perspective: it stores scientist
  // corrections that the backend will pick up on the next generation run.
  const [steps, setSteps] = useState<string[]>([...exp.steps]);
  const [materials, setMaterials] = useState<EditedMaterial[]>(() => exp.materials.map(toEdited));

  const [savedFlash, setSavedFlash] = useState(false);
  // True once a step has been added or removed in this session
  const [stepsStructureChanged, setStepsStructureChanged] = useState(false);

  // ── step handlers ─────────────────────────────────────────────────────────

  function updateStep(idx: number, value: string) {
    setSteps((prev) => prev.map((s, i) => (i === idx ? value : s)));
  }

  function removeStep(idx: number) {
    setSteps((prev) => prev.filter((_, i) => i !== idx));
    setStepsStructureChanged(true);
  }

  function addStep() {
    setSteps((prev) => [...prev, ""]);
    setStepsStructureChanged(true);
  }

  // ── material handlers ─────────────────────────────────────────────────────

  function updateMaterial<K extends keyof EditedMaterial>(idx: number, field: K, value: EditedMaterial[K]) {
    setMaterials((prev) => {
      const next = prev.map((m, i) => (i === idx ? { ...m, [field]: value } : m));
      if (field === "qty_amount" || field === "unit_cost_eur") {
        const m = next[idx];
        next[idx] = { ...m, total_eur: parseFloat((m.qty_amount * m.unit_cost_eur).toFixed(2)) };
      }
      return next;
    });
  }

  // ── save — persists corrections for the backend; does NOT alter displayed plan ──

  function handleSave() {
    saveExpFeedback(exp.id, { steps, materials });
    // Keep stepsStructureChanged true so the reminder stays until materials are reviewed
    setSavedFlash(true);
    setTimeout(() => setSavedFlash(false), 2500);
    onStopEdit();
  }

  // ─────────────────────────────────────────────────────────────────────────

  return (
    <li className="card overflow-hidden">
      {/* ── Header ── */}
      <div
        className="flex items-center gap-3 px-5 py-4 cursor-pointer hover:bg-[#faf9f7] transition-colors"
        onClick={onToggleExpand}
      >
        {exp.cro_compatible && (
          <input
            type="checkbox"
            checked={selected}
            onChange={onToggleSelect}
            onClick={(e) => e.stopPropagation()}
            aria-label={`Select ${exp.name}`}
            className="h-4 w-4"
            style={{ accentColor: "var(--color-accent)" }}
          />
        )}
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2 mb-1.5">
            <span className="font-semibold text-[0.95rem]" style={{ color: "var(--color-text)" }}>
              {exp.name}
            </span>
            {savedFlash && (
              <span className="tag-cro flex items-center gap-1">
                <Check size={10} /> Saved
              </span>
            )}
            {/* Warning badge on the header — visible even when card is collapsed */}
            {stepsStructureChanged && !editing && (
              <span
                className="flex items-center gap-1 px-2 py-0.5 text-[0.7rem] font-semibold rounded-full"
                style={{ background: "#fffbea", border: "1px solid #f0c030", color: "#7a5000" }}
              >
                <AlertTriangle size={10} style={{ color: "#c09000" }} />
                Check materials
              </span>
            )}
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <span
              className="text-[0.72rem] px-2.5 py-0.5"
              style={{ color: "var(--color-text-muted)", border: "1px solid var(--color-border)", borderRadius: 999 }}
            >
              {exp.duration}
            </span>
            {exp.cro_compatible && <span className="tag-cro">CRO Compatible</span>}
          </div>
        </div>
        <motion.span animate={{ rotate: expanded ? 180 : 0 }} transition={{ duration: 0.2 }} style={{ color: "var(--color-text-muted)" }}>
          <ChevronDown size={18} />
        </motion.span>
      </div>

      {/* ── Expanded body ── */}
      <AnimatePresence initial={false}>
        {expanded && (
          <motion.div
            key="body"
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.25 }}
            style={{ overflow: "hidden" }}
          >
            <div className="px-5 pb-5 pt-4 space-y-6" style={{ borderTop: "1px solid var(--color-border)" }}>

              <div>
                <div className="eyebrow mb-2">Goal</div>
                <p className="italic text-sm leading-relaxed" style={{ color: "var(--color-text-muted)" }}>
                  {exp.goal}
                </p>
              </div>

              {/* Protocol Steps */}
              <div>
                <div className="eyebrow mb-3">Protocol Steps</div>

                {/* Inline warning — shown as soon as structure changes */}
                {stepsStructureChanged && (
                  <div
                    className="mb-3 flex items-start gap-2 rounded-lg px-3 py-2.5 text-[0.8rem] leading-snug"
                    style={{ background: "#fffbea", border: "1px solid #f0c030", color: "#7a5000" }}
                  >
                    <AlertTriangle size={14} className="mt-0.5 flex-shrink-0" style={{ color: "#c09000" }} />
                    <span>
                      Steps were added or removed — review the <strong>Materials</strong> table below to confirm reagents and quantities are still accurate.
                    </span>
                  </div>
                )}

                <ol className="space-y-2">
                  {steps.map((step, i) => (
                    <li key={i} className="flex gap-3 items-start">
                      <span
                        className="mt-2 w-5 flex-shrink-0 text-right select-none"
                        style={{ fontFamily: "var(--font-mono)", fontSize: "0.72rem", color: "var(--color-accent-label)" }}
                      >
                        {i + 1}.
                      </span>
                      {editing ? (
                        <>
                          <AutoTextarea value={step} onChange={(v) => updateStep(i, v)} />
                          <button
                            type="button"
                            onClick={() => removeStep(i)}
                            aria-label="Remove step"
                            className="mt-1.5 flex-shrink-0 p-1 rounded transition hover:opacity-80"
                            style={{ color: "var(--color-coral)", background: "var(--color-coral-light)", border: "none" }}
                          >
                            <Trash2 size={13} />
                          </button>
                        </>
                      ) : (
                        <div className="flex-1 text-sm leading-relaxed py-1" style={{ color: "var(--color-text)" }}>
                          {step}
                        </div>
                      )}
                    </li>
                  ))}
                </ol>

                {editing && (
                  <button
                    type="button"
                    onClick={addStep}
                    className="mt-3 flex items-center gap-1.5 text-[0.82rem] font-medium transition hover:opacity-70"
                    style={{ color: "var(--color-accent-deep)", background: "none", border: "none", padding: 0 }}
                  >
                    <Plus size={14} strokeWidth={2.5} />
                    Add step
                  </button>
                )}
              </div>

              {/* Materials */}
              <div>
                <div className="eyebrow mb-3">Materials</div>
                <div className="overflow-x-auto" style={{ border: "1px solid var(--color-border)", borderRadius: 10 }}>
                  <table className="w-full text-[0.84rem]">
                    <thead>
                      <tr style={{ background: "var(--color-bg)" }}>
                        <Th>Reagent</Th>
                        <Th>Catalog #</Th>
                        <Th>Supplier</Th>
                        <Th align="right">Qty</Th>
                        <Th align="right">Unit Cost</Th>
                        <Th align="right">Subtotal</Th>
                      </tr>
                    </thead>
                    <tbody>
                      {materials.map((m, i) => (
                        <tr key={i} style={{ borderTop: "1px solid var(--color-border)" }}>
                          <MatCell editing={editing} value={m.name}
                            onChange={(v) => updateMaterial(i, "name", v)} />
                          <MatCell
                            editing={editing}
                            value={m.catalog}
                            mono
                            onChange={(v) => updateMaterial(i, "catalog", v)}
                            displayNode={
                              m.catalog === "verify_before_ordering" ? (
                                <span
                                  style={{
                                    fontFamily: "var(--font-mono)",
                                    fontSize: "0.72rem",
                                    color: "var(--color-text-muted)",
                                    fontStyle: "italic",
                                  }}
                                >
                                  Verify before ordering
                                </span>
                              ) : undefined
                            }
                          />
                          <MatCell editing={editing} value={m.supplier}
                            onChange={(v) => updateMaterial(i, "supplier", v)} />

                          {/* Qty: separate number + unit fields */}
                          <td className="px-3 py-2 align-middle text-right">
                            {editing ? (
                              <div className="flex items-center justify-end gap-1">
                                <input
                                  type="number"
                                  min={0}
                                  step="any"
                                  value={m.qty_amount}
                                  onChange={(e) => updateMaterial(i, "qty_amount", parseFloat(e.target.value) || 0)}
                                  className="w-16 outline-none rounded px-1 py-0.5 text-right"
                                  style={{ background: "var(--color-edit)", border: "1px solid var(--color-accent)", borderRadius: 4, fontSize: "0.84rem", color: "var(--color-text)" }}
                                />
                                <input
                                  type="text"
                                  value={m.qty_unit}
                                  onChange={(e) => updateMaterial(i, "qty_unit", e.target.value)}
                                  placeholder="unit"
                                  className="w-20 outline-none rounded px-1 py-0.5"
                                  style={{ background: "var(--color-edit)", border: "1px solid var(--color-accent)", borderRadius: 4, fontSize: "0.84rem", color: "var(--color-text)" }}
                                />
                              </div>
                            ) : (
                              <span style={{ fontSize: "0.84rem", color: "var(--color-text)" }}>
                                {m.qty_amount} {m.qty_unit}
                              </span>
                            )}
                          </td>

                          <MatCell editing={editing} value={String(m.unit_cost_eur)} align="right" mono prefix="€"
                            onChange={(v) => updateMaterial(i, "unit_cost_eur", parseFloat(v) || 0)} />

                          {/* Subtotal — read-only, auto-calculated */}
                          <td className="px-3 py-2.5 align-top text-right"
                            style={{ fontFamily: "var(--font-mono)", fontSize: "0.78rem", color: "var(--color-text)" }}>
                            €{m.total_eur.toLocaleString("en-US", { minimumFractionDigits: 0, maximumFractionDigits: 2 })}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>

              <div>
                <div className="eyebrow mb-2">Success Criteria</div>
                <p className="text-sm leading-relaxed" style={{ color: "var(--color-text)" }}>
                  {exp.success_criteria}
                </p>
              </div>

              {/* Structured review — always accessible */}
              <ReviewPanel exp={exp} defaultExpType={exp.name} />

              {/* Footer actions */}
              <div className="flex flex-wrap items-center justify-end gap-2 pt-1">
                <button
                  type="button"
                  onClick={onToggleEdit}
                  aria-label={editing ? "Exit edit mode" : "Edit protocol"}
                  className="inline-flex items-center justify-center p-2 transition hover:opacity-80"
                  style={{
                    border: "1px solid var(--color-border)",
                    borderRadius: 8,
                    color: editing ? "var(--color-accent)" : "var(--color-text-muted)",
                    background: editing ? "var(--color-accent-light)" : "transparent",
                  }}
                >
                  <Pencil size={14} />
                </button>
                {editing && (
                  <button
                    type="button"
                    onClick={handleSave}
                    className="px-4 py-2 text-sm font-semibold text-white transition hover:opacity-90"
                    style={{ background: "var(--color-accent)", border: "none", borderRadius: 999 }}
                  >
                    Save Changes
                  </button>
                )}
                {exp.cro_compatible && (
                  <button
                    type="button"
                    onClick={onSubmit}
                    className="inline-flex items-center gap-2 px-4 py-2 text-sm font-semibold transition hover:opacity-80"
                    style={{
                      background: "transparent",
                      color: "var(--color-accent-deep)",
                      border: "1.5px solid var(--color-accent)",
                      borderRadius: 999,
                    }}
                  >
                    Submit to Litmus
                    <ArrowRight size={14} strokeWidth={2.5} />
                  </button>
                )}
              </div>

            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </li>
  );
}

// ─── AutoTextarea ─────────────────────────────────────────────────────────────

function AutoTextarea({ value, onChange }: { value: string; onChange: (v: string) => void }) {
  return (
    <textarea
      value={value}
      rows={1}
      onChange={(e) => {
        onChange(e.target.value);
        e.target.style.height = "auto";
        e.target.style.height = e.target.scrollHeight + "px";
      }}
      onFocus={(e) => {
        e.target.style.height = "auto";
        e.target.style.height = e.target.scrollHeight + "px";
      }}
      className="flex-1 text-sm leading-relaxed outline-none resize-none rounded px-2 py-1"
      style={{
        background: "var(--color-edit)",
        border: "1px solid var(--color-accent)",
        borderRadius: 4,
        color: "var(--color-text)",
        fontFamily: "var(--font-sans)",
        overflow: "hidden",
        minHeight: "2rem",
      }}
    />
  );
}

// ─── MatCell ──────────────────────────────────────────────────────────────────

type MatCellProps = {
  editing: boolean;
  value: string;
  onChange: (v: string) => void;
  align?: "left" | "right";
  mono?: boolean;
  prefix?: string;
  displayNode?: React.ReactNode;
};

function MatCell({ editing, value, onChange, align = "left", mono = false, prefix, displayNode }: MatCellProps) {
  const textStyle: React.CSSProperties = {
    fontFamily: mono ? "var(--font-mono)" : "inherit",
    fontSize: mono ? "0.78rem" : undefined,
    color: "var(--color-text)",
    textAlign: align,
  };

  return (
    <td className="px-3 py-2 align-middle" style={{ textAlign: align }}>
      {editing ? (
        <div className="flex items-center gap-0.5">
          {prefix && <span style={{ ...textStyle, opacity: 0.6 }}>{prefix}</span>}
          <input
            type="text"
            value={value}
            onChange={(e) => onChange(e.target.value)}
            className="min-w-0 w-full outline-none rounded px-1 py-0.5"
            style={{ ...textStyle, background: "var(--color-edit)", border: "1px solid var(--color-accent)", borderRadius: 4 }}
          />
        </div>
      ) : displayNode !== undefined ? (
        <span style={{ textAlign: align, display: "block" }}>{displayNode}</span>
      ) : (
        <span style={textStyle}>{prefix}{value}</span>
      )}
    </td>
  );
}

// ─── Th ───────────────────────────────────────────────────────────────────────

function Th({ children, align = "left" }: { children: React.ReactNode; align?: "left" | "right" }) {
  return (
    <th
      className="px-3 py-2.5"
      style={{
        textAlign: align,
        fontFamily: "var(--font-sans)",
        fontSize: "0.67rem",
        fontWeight: 700,
        letterSpacing: "0.1em",
        textTransform: "uppercase",
        color: "var(--color-accent-label)",
      }}
    >
      {children}
    </th>
  );
}
