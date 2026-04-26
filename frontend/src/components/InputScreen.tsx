import { useEffect, useRef, useState } from "react";
import { motion } from "framer-motion";
import { ArrowRight } from "lucide-react";
import { PREFILL_HYPOTHESIS } from "../mockData";

type Props = {
  onSubmit: (hypothesis: string) => void;
};

export function InputScreen({ onSubmit }: Props) {
  const [value, setValue] = useState("");
  const ref = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    autoSize();
  }, [value]);

  function autoSize() {
    const el = ref.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = `${Math.max(el.scrollHeight, 144)}px`;
  }

  function handleGenerate() {
    const trimmed = value.trim() || PREFILL_HYPOTHESIS;
    onSubmit(trimmed);
  }

  return (
    <motion.div
      initial={{ opacity: 0, y: 14 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.35 }}
      className="mx-auto flex min-h-[calc(100vh-3rem)] w-full max-w-[720px] flex-col justify-center px-5 py-14 sm:px-6"
    >
      <div className="space-y-6">
        <div>
          <div className="eyebrow mb-4">AI Scientist</div>
          <h1
            className="text-4xl sm:text-5xl font-bold leading-[1.1] tracking-tight mb-3"
            style={{ fontFamily: "var(--font-serif)", color: "var(--color-text)" }}
          >
            From hypothesis to<br />runnable plan.
          </h1>
          <p className="text-base" style={{ color: "var(--color-text-muted)" }}>
            State your scientific hypothesis and get a complete, operationally
            realistic experiment plan in seconds.
          </p>
        </div>

        <textarea
          ref={ref}
          value={value}
          onChange={(e) => setValue(e.target.value)}
          placeholder="Propose a clear, testable hypothesis that links a specific intervention to a measurable, quantitative outcome (including a defined threshold), grounded in a plausible mechanism, and framed such that an appropriate control condition is evident."
          rows={4}
          className="w-full resize-none p-4 text-[0.95rem] leading-relaxed outline-none transition focus:shadow-[0_0_0_2px_var(--color-accent)]"
          style={{
            background: "var(--color-card)",
            border: "1px solid var(--color-border)",
            borderRadius: 12,
            minHeight: 148,
            color: "var(--color-text)",
            boxShadow: "0 1px 4px rgba(0,0,0,0.05)",
          }}
        />

        <button
          type="button"
          onClick={() => setValue(PREFILL_HYPOTHESIS)}
          className="w-full text-left text-[0.8rem] leading-snug px-4 py-3 transition hover:opacity-80"
          style={{
            background: "var(--color-card)",
            color: "var(--color-text-muted)",
            border: "1px solid var(--color-border)",
            borderRadius: 10,
            boxShadow: "0 1px 3px rgba(0,0,0,0.04)",
          }}
        >
          <span className="eyebrow mr-2" style={{ color: "var(--color-accent-label)" }}>
            Example
          </span>
          {PREFILL_HYPOTHESIS}
        </button>

        <button
          type="button"
          onClick={handleGenerate}
          className="flex w-full items-center justify-center gap-2 px-5 py-3.5 text-[0.95rem] font-semibold transition hover:opacity-90 active:scale-[0.98]"
          style={{
            background: "var(--color-accent)",
            color: "#fff",
            borderRadius: "var(--radius-btn)",
            border: "none",
          }}
        >
          Generate Plan
          <ArrowRight size={16} strokeWidth={2.5} />
        </button>
      </div>
    </motion.div>
  );
}
