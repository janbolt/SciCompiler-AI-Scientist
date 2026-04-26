import { useMemo, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { ChevronDown, Pencil, ArrowRight } from "lucide-react";
import { Experiment, MOCK_PLAN } from "../mockData";
import { Modal } from "./Modal";

export function ExperimentsTab() {
  const experiments = MOCK_PLAN.experiments;

  const [expandedId, setExpandedId] = useState<string | null>(experiments[0]?.id ?? null);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [singleSubmitId, setSingleSubmitId] = useState<string | null>(null);
  const [batchModalOpen, setBatchModalOpen] = useState(false);

  const croCompatible = useMemo(
    () => experiments.filter((e) => e.cro_compatible),
    [experiments]
  );

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
      {croCompatible.length > 0 && (
        <section
          className="bg-white p-4 space-y-3 sm:flex sm:items-center sm:justify-between sm:space-y-0 sm:gap-4"
          style={{ border: "1px solid var(--color-border)", borderRadius: 0 }}
        >
          <p className="text-sm">
            Select CRO-compatible experiments to outsource:
          </p>
          <button
            type="button"
            disabled={selected.size === 0}
            onClick={() => setBatchModalOpen(true)}
            className="inline-flex items-center justify-center gap-2 px-4 py-2 text-sm font-semibold transition disabled:cursor-not-allowed disabled:opacity-40"
            style={{
              background: "transparent",
              color: "var(--color-accent)",
              border: "1px solid var(--color-accent)",
              borderRadius: 4,
            }}
          >
            Submit selected to Litmus
            <ArrowRight size={14} strokeWidth={2.5} />
          </button>
        </section>
      )}

      <ul className="space-y-3">
        {experiments.map((exp) => (
          <ExperimentCard
            key={exp.id}
            exp={exp}
            expanded={expandedId === exp.id}
            onToggleExpand={() =>
              setExpandedId((cur) => (cur === exp.id ? null : exp.id))
            }
            editing={editingId === exp.id}
            onToggleEdit={() =>
              setEditingId((cur) => (cur === exp.id ? null : exp.id))
            }
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
        onConfirm={() => {
          setBatchModalOpen(false);
          setSelected(new Set());
        }}
        confirmLabel="Submit"
      >
        <p className="text-sm text-[var(--color-muted)] mb-2">
          The following experiments will be sent to Litmus for CRO quotation:
        </p>
        <ul className="space-y-1 text-sm">
          {selectedExperiments.map((e) => (
            <li key={e.id}>• {e.name}</li>
          ))}
        </ul>
      </Modal>

      <Modal
        open={singleSubmitId !== null}
        title={
          singleSubmitId
            ? `Submit ${experiments.find((e) => e.id === singleSubmitId)?.name} to Litmus for CRO outsourcing?`
            : ""
        }
        onCancel={() => setSingleSubmitId(null)}
        onConfirm={() => setSingleSubmitId(null)}
        confirmLabel="Submit"
      />
    </div>
  );
}

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
  exp,
  expanded,
  onToggleExpand,
  editing,
  onToggleEdit,
  onStopEdit,
  selected,
  onToggleSelect,
  onSubmit,
}: CardProps) {
  return (
    <li
      className="bg-white"
      style={{ border: "1px solid var(--color-border)", borderRadius: 0 }}
    >
      <div
        className="flex items-center gap-3 px-4 py-3 cursor-pointer"
        onClick={onToggleExpand}
      >
        {exp.cro_compatible && (
          <input
            type="checkbox"
            checked={selected}
            onChange={onToggleSelect}
            onClick={(e) => e.stopPropagation()}
            aria-label={`Select ${exp.name}`}
            className="h-4 w-4 accent-[var(--color-accent)]"
          />
        )}
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <span className="font-semibold text-[0.95rem]">{exp.name}</span>
          </div>
          <div className="mt-1 flex flex-wrap items-center gap-2">
            <span
              className="text-[0.7rem] px-2 py-0.5"
              style={{
                color: "var(--color-muted)",
                border: "1px solid var(--color-border)",
                borderRadius: 999,
              }}
            >
              {exp.duration}
            </span>
            {exp.cro_compatible && (
              <span
                className="text-[0.65rem] font-bold uppercase tracking-wider px-2 py-0.5 text-white"
                style={{ background: "var(--color-accent)", borderRadius: 0 }}
              >
                CRO Compatible
              </span>
            )}
          </div>
        </div>
        <motion.span
          animate={{ rotate: expanded ? 180 : 0 }}
          transition={{ duration: 0.2 }}
          className="text-[var(--color-muted)]"
        >
          <ChevronDown size={18} />
        </motion.span>
      </div>

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
            <div className="px-4 pb-4 pt-1 space-y-5" style={{ borderTop: "1px solid var(--color-border)" }}>
              <div className="pt-4">
                <div className="small-caps mb-1.5">Goal</div>
                <p className="italic text-sm text-[var(--color-muted)] leading-relaxed">{exp.goal}</p>
              </div>

              <div>
                <div className="small-caps mb-2">Protocol Steps</div>
                <ol className="space-y-2 text-sm">
                  {exp.steps.map((step, i) => (
                    <li key={i} className="flex gap-3">
                      <span className="font-mono text-xs text-[var(--color-muted)] mt-0.5 w-5 flex-shrink-0">
                        {i + 1}.
                      </span>
                      <div
                        className="flex-1 leading-relaxed px-2 py-1"
                        contentEditable={editing}
                        suppressContentEditableWarning
                      >
                        {step}
                      </div>
                    </li>
                  ))}
                </ol>
              </div>

              <div>
                <div className="small-caps mb-2">Materials</div>
                <div
                  className="overflow-x-auto"
                  style={{ border: "1px solid var(--color-border)" }}
                >
                  <table className="w-full text-[0.85rem]">
                    <thead>
                      <tr style={{ background: "#F5F5F5" }}>
                        <Th>Reagent</Th>
                        <Th>Catalog #</Th>
                        <Th>Supplier</Th>
                        <Th align="right">Qty</Th>
                        <Th align="right">Unit Cost</Th>
                        <Th align="right">Subtotal</Th>
                      </tr>
                    </thead>
                    <tbody>
                      {exp.materials.map((m, i) => (
                        <tr
                          key={i}
                          style={{ borderTop: "1px solid var(--color-border)" }}
                        >
                          <Td>{m.name}</Td>
                          <Td mono>{m.catalog}</Td>
                          <Td>{m.supplier}</Td>
                          <Td align="right" editable={editing}>
                            {m.qty}
                          </Td>
                          <Td align="right" editable={editing} mono>
                            €{m.unit_cost_eur}
                          </Td>
                          <Td align="right" mono>
                            €{m.total_eur}
                          </Td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>

              <div>
                <div className="small-caps mb-1.5">Success Criteria</div>
                <p className="text-sm leading-relaxed">{exp.success_criteria}</p>
              </div>

              <div className="flex flex-wrap items-center justify-end gap-2 pt-1">
                <button
                  type="button"
                  onClick={onToggleEdit}
                  aria-label={editing ? "Exit edit mode" : "Edit"}
                  className="inline-flex items-center justify-center p-2 transition hover:bg-[var(--color-accent-light)]"
                  style={{
                    border: "1px solid var(--color-border)",
                    borderRadius: 4,
                    color: editing ? "var(--color-accent)" : "var(--color-muted)",
                  }}
                >
                  <Pencil size={14} />
                </button>
                {editing && (
                  <button
                    type="button"
                    onClick={onStopEdit}
                    className="px-3 py-2 text-sm font-semibold text-white transition hover:opacity-90"
                    style={{
                      background: "var(--color-accent)",
                      borderRadius: 4,
                    }}
                  >
                    Save Changes
                  </button>
                )}
                {exp.cro_compatible && (
                  <button
                    type="button"
                    onClick={onSubmit}
                    className="inline-flex items-center gap-2 px-3 py-2 text-sm font-semibold transition hover:bg-[var(--color-accent-light)]"
                    style={{
                      background: "transparent",
                      color: "var(--color-accent)",
                      border: "1px solid var(--color-accent)",
                      borderRadius: 4,
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

function Th({
  children,
  align = "left",
}: {
  children: React.ReactNode;
  align?: "left" | "right";
}) {
  return (
    <th
      className="px-3 py-2 text-[0.7rem] font-bold uppercase tracking-wider text-[var(--color-muted)]"
      style={{ textAlign: align }}
    >
      {children}
    </th>
  );
}

function Td({
  children,
  align = "left",
  mono = false,
  editable = false,
}: {
  children: React.ReactNode;
  align?: "left" | "right";
  mono?: boolean;
  editable?: boolean;
}) {
  return (
    <td
      className="px-3 py-2 align-top"
      style={{
        textAlign: align,
        fontFamily: mono ? "var(--font-mono)" : "inherit",
        fontSize: mono ? "0.78rem" : undefined,
      }}
    >
      <span contentEditable={editable} suppressContentEditableWarning>
        {children}
      </span>
    </td>
  );
}
