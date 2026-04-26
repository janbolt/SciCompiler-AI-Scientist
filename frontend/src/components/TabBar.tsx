export type TabId = "overview" | "experiments" | "budget" | "submit";

const TABS: { id: TabId; label: string }[] = [
  { id: "overview", label: "Overview" },
  { id: "experiments", label: "Experiments" },
  { id: "budget", label: "Budget" },
  { id: "submit", label: "Submit" },
];

type Props = {
  active: TabId;
  onChange: (id: TabId) => void;
};

export function TabBar({ active, onChange }: Props) {
  return (
    <nav
      className="sticky z-10"
      style={{
        top: 48,
        background: "var(--color-bg)",
        borderBottom: "1px solid var(--color-border)",
      }}
    >
      <div className="mx-auto flex w-full max-w-[860px] items-stretch overflow-x-auto px-4 sm:px-6">
        {TABS.map((tab) => {
          const isActive = active === tab.id;
          return (
            <button
              key={tab.id}
              type="button"
              onClick={() => onChange(tab.id)}
              className="whitespace-nowrap py-3 px-3 sm:px-4 text-sm transition-all"
              style={{
                color: isActive ? "var(--color-accent-deep)" : "var(--color-text-muted)",
                fontWeight: isActive ? 700 : 500,
                borderBottom: isActive
                  ? "2px solid var(--color-accent)"
                  : "2px solid transparent",
                background: "transparent",
                borderRadius: 0,
                letterSpacing: isActive ? undefined : undefined,
              }}
            >
              {tab.label}
            </button>
          );
        })}
      </div>
    </nav>
  );
}
