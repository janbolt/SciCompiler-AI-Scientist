import { Download } from "lucide-react";
import { BudgetLine, MOCK_PLAN } from "../mockData";

const SECTIONS: { key: "fixed" | "staff" | "recurring"; label: string }[] = [
  { key: "fixed", label: "Fixed Costs" },
  { key: "staff", label: "Staff Costs" },
  { key: "recurring", label: "Recurring Costs" },
];

export function BudgetTab() {
  const { budget, experiments } = MOCK_PLAN;

  function downloadCsv() {
    const rows: string[][] = [
      ["Experiment", "Reagent", "Catalog #", "Supplier", "Qty", "Unit Cost (EUR)", "Subtotal (EUR)"],
    ];
    for (const exp of experiments) {
      for (const m of exp.materials) {
        rows.push([
          exp.name,
          m.name,
          m.catalog,
          m.supplier,
          m.qty,
          String(m.unit_cost_eur),
          String(m.total_eur),
        ]);
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
      <div
        className="bg-white"
        style={{ border: "1px solid var(--color-border)", borderRadius: 0 }}
      >
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
                className="px-4 py-3 text-base font-bold"
                style={{ borderTop: "2px solid var(--color-text)" }}
              >
                Total
              </td>
              <td
                className="px-4 py-3 text-right font-mono text-base font-bold"
                style={{ borderTop: "2px solid var(--color-text)" }}
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
        className="inline-flex items-center gap-2 px-4 py-2.5 text-sm font-semibold transition hover:bg-[var(--color-text)] hover:text-[var(--color-bg)]"
        style={{
          background: "transparent",
          color: "var(--color-text)",
          border: "1px solid var(--color-text)",
          borderRadius: 4,
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
      <tr style={{ background: "#F5F5F5" }}>
        <td
          colSpan={2}
          className="px-4 py-2 text-[0.72rem] font-bold uppercase tracking-wider text-[var(--color-muted)]"
        >
          {label}
        </td>
      </tr>
      {lines.map((line, i) => (
        <tr key={i} style={{ borderTop: "1px solid var(--color-border)" }}>
          <td className="px-4 py-2.5 text-sm">{line.item}</td>
          <td className="px-4 py-2.5 text-right font-mono text-sm">
            €{line.cost_eur.toLocaleString("en-US")}
          </td>
        </tr>
      ))}
    </>
  );
}
