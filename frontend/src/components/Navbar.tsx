export function Navbar() {
  return (
    <header
      className="sticky top-0 z-20 flex h-12 items-center justify-between bg-[var(--color-bg)] px-4 sm:px-6"
      style={{ borderBottom: "1px solid var(--color-border)" }}
    >
      <span className="font-bold uppercase tracking-wide text-[1rem]">AI Scientist</span>
      <span className="small-caps hidden sm:inline">Powered by Fulcrum Science</span>
      <span className="small-caps sm:hidden">Fulcrum</span>
    </header>
  );
}
