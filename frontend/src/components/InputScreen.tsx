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
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3 }}
      className="mx-auto flex min-h-[calc(100vh-3rem)] w-full max-w-[860px] flex-col justify-center px-4 py-12 sm:px-6"
    >
      <div className="space-y-5">
        <div className="small-caps">AI Scientist</div>

        <textarea
          ref={ref}
          value={value}
          onChange={(e) => setValue(e.target.value)}
          placeholder="State your scientific hypothesis. Name the intervention, expected outcome, and mechanism."
          rows={4}
          className="w-full resize-none border bg-white p-4 text-[1.05rem] leading-relaxed outline-none focus:border-[var(--color-accent)]"
          style={{
            borderColor: "var(--color-border)",
            borderRadius: 0,
            minHeight: 144,
          }}
        />

        <div className="flex flex-wrap gap-2">
          <button
            type="button"
            onClick={() => setValue(PREFILL_HYPOTHESIS)}
            className="text-left text-[0.8rem] leading-snug text-[var(--color-muted)] transition hover:text-[var(--color-text)]"
            style={{
              background: "#F0F0F0",
              padding: "10px 14px",
              borderRadius: 999,
              border: "1px solid var(--color-border)",
            }}
          >
            {PREFILL_HYPOTHESIS}
          </button>
        </div>

        <button
          type="button"
          onClick={handleGenerate}
          className="flex w-full items-center justify-center gap-2 px-5 py-3.5 text-[0.95rem] font-semibold transition hover:opacity-90"
          style={{
            background: "var(--color-text)",
            color: "var(--color-bg)",
            borderRadius: 4,
          }}
        >
          Generate Plan
          <ArrowRight size={16} strokeWidth={2.5} />
        </button>
      </div>
    </motion.div>
  );
}
