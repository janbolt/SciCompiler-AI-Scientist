import { Download } from "lucide-react";
import { BudgetLine } from "../mockData";
import { loadMaterials, splitQty } from "../lib/feedbackStore";
import { usePlan } from "../context/PlanContext";

const SECTIONS: { key: "fixed" | "staff" | "recurring"; label: string }[] = [
  { key: "fixed", label: "Fixed Costs" },
  { key: "staff", label: "Staff Costs" },
  { key: "recurring", label: "Recurring Costs" },
];

export function BudgetTab() {
  const { budget, experiments } = usePlan();

  function downloadCsv() {
    const rows: string[][] = [
      ["Experiment", "Reagent", "Catalog #", "Supplier", "Qty", "Unit Cost (EUR)", "Subtotal (EUR)"],
    ];
    for (const exp of experiments) {
      // Prefer scientist-edited materials from the feedback store
      const saved = loadMaterials(exp.id);
      if (saved) {
        for (const m of saved) {
          const qty = m.qty_unit ? `${m.qty_amount} ${m.qty_unit}` : String(m.qty_amount);
          rows.push([exp.name, m.name, m.catalog, m.supplier, qty,
            String(m.unit_cost_eur), String(m.total_eur)]);
        }
      } else {
        for (const m of exp.materials) {
          const { qty_amount, qty_unit } = splitQty(m.qty);
          const subtotal = parseFloat((qty_amount * m.unit_cost_eur).toFixed(2));
          rows.push([exp.name, m.name, m.catalog, m.supplier, m.qty,
            String(m.unit_cost_eur), String(subtotal)]);
        }
      }
    }
    const csv = rows
      .map((r) => r.map((c) => `"${c.replace(/"/g, '""')}"`).join(","))
      .join("\n");
    const blob = new Blob([csv], { type: "text/csv;charset=utf-8;" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "materials_list.csv";
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  }

  return (
    <div className="space-y-5">
      <div className="card overflow-hidden">
        <table className="w-full">
          <tbody>
            {SECTIONS.map((section) => {
              const lines = budget[section.key] as BudgetLine[];
              return (
                <SectionBlock key={section.key} label={section.label} lines={lines} />
              );
            })}
            <tr>
              <td
                className="px-5 py-4 text-base font-bold"
                style={{
                  borderTop: "2px solid var(--color-text)",
                  fontFamily: "var(--font-serif)",
                  color: "var(--color-text)",
                }}
              >
                Total
              </td>
              <td
                className="px-5 py-4 text-right text-base font-bold"
                style={{
                  borderTop: "2px solid var(--color-text)",
                  fontFamily: "var(--font-mono)",
                  color: "var(--color-text)",
                }}
              >
                €{budget.total_eur.toLocaleString("en-US")}
              </td>
            </tr>
          </tbody>
        </table>
      </div>

      <button
        type="button"
        onClick={downloadCsv}
        className="inline-flex items-center gap-2 px-5 py-2.5 text-sm font-semibold transition hover:opacity-80"
        style={{
          background: "transparent",
          color: "var(--color-text)",
          border: "1.5px solid var(--color-border)",
          borderRadius: 999,
        }}
      >
        <Download size={14} strokeWidth={2.5} />
        Download Materials List (CSV)
      </button>
    </div>
  );
}

function SectionBlock({ label, lines }: { label: string; lines: BudgetLine[] }) {
  return (
    <>
      <tr style={{ background: "var(--color-bg)" }}>
        <td
          colSpan={2}
          className="px-5 py-2.5 eyebrow"
        >
          {label}
        </td>
      </tr>
      {lines.map((line, i) => (
        <tr key={i} style={{ borderTop: "1px solid var(--color-border)" }}>
          <td className="px-5 py-3 text-sm" style={{ color: "var(--color-text)" }}>
            {line.item}
          </td>
          <td
            className="px-5 py-3 text-right text-sm"
            style={{ fontFamily: "var(--font-mono)", color: "var(--color-text)" }}
          >
            €{line.cost_eur.toLocaleString("en-US")}
          </td>
        </tr>
      ))}
    </>
  );
}
