type Props = {
  onReset?: () => void;
};

export function Navbar({ onReset }: Props) {
  return (
    <header
      className="sticky top-0 z-20 flex h-12 items-center justify-between px-4 sm:px-6"
      style={{
        background: "var(--color-bg)",
        borderBottom: "1px solid var(--color-border)",
      }}
    >
      <span
        className="tracking-tight text-[1.05rem] font-bold"
        style={{ fontFamily: "var(--font-serif)", color: "var(--color-text)" }}
      >
        SciCompiler
      </span>

      <div className="flex items-center gap-3">
        {onReset && (
          <button
            type="button"
            onClick={onReset}
            className="flex items-center gap-1.5 px-3 py-1.5 text-[0.78rem] font-medium transition hover:opacity-70"
            style={{
              background: "transparent",
              color: "var(--color-text-muted)",
              border: "1px solid var(--color-border)",
              borderRadius: 999,
            }}
          >
            ← New hypothesis
          </button>
        )}
        <span className="eyebrow hidden sm:inline" style={{ color: "var(--color-accent-label)" }}>
          Powered by Fulcrum Science
        </span>
      </div>
    </header>
  );
}
