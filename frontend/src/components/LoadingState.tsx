import { useEffect, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";

const STATUSES = [
  "Scanning literature...",
  "Assessing novelty...",
  "Drafting experiments...",
  "Estimating budget...",
  "Assessing risks...",
  "Building timeline...",
  "Finalizing plan...",
];

type Props = {
  onDone: () => void;
  ready: boolean;
};

export function LoadingState({ onDone, ready }: Props) {
  const [idx, setIdx] = useState(0);
  const [animDone, setAnimDone] = useState(false);

  // Advance through statuses; stop at last step and wait for `ready`
  useEffect(() => {
    if (idx >= STATUSES.length - 1) {
      setAnimDone(true);
      return;
    }
    const id = window.setTimeout(() => setIdx((i) => i + 1), 1500);
    return () => window.clearTimeout(id);
  }, [idx]);

  // Only transition to results once animation reached end AND data is ready
  useEffect(() => {
    if (!animDone || !ready) return;
    const id = window.setTimeout(onDone, 600);
    return () => window.clearTimeout(id);
  }, [animDone, ready, onDone]);

  // Hold progress at 95% while waiting for backend after animation ends
  const baseProgress = ((idx + 1) / STATUSES.length) * 100;
  const progress = animDone && !ready ? 95 : baseProgress;

  return (
    <div className="mx-auto flex min-h-[calc(100vh-3rem)] w-full max-w-[720px] flex-col justify-center px-5 sm:px-6">
      <div className="space-y-8">
        <div
          style={{
            height: 3,
            background: "var(--color-border)",
            borderRadius: 999,
            overflow: "hidden",
          }}
        >
          <motion.div
            initial={{ width: 0 }}
            animate={{
              width: `${progress}%`,
              opacity: animDone && !ready ? [1, 0.5, 1] : 1,
            }}
            transition={
              animDone && !ready
                ? { width: { duration: 0.8, ease: "easeOut" }, opacity: { duration: 1.4, repeat: Infinity, ease: "easeInOut" } }
                : { duration: 0.8, ease: "easeOut" }
            }
            style={{
              height: "100%",
              background: "var(--color-accent)",
              borderRadius: 999,
            }}
          />
        </div>

        <div className="min-h-[2rem]">
          <AnimatePresence mode="wait">
            <motion.div
              key={STATUSES[idx]}
              initial={{ opacity: 0, y: 6 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -6 }}
              transition={{ duration: 0.3 }}
              className="text-sm"
              style={{ fontFamily: "var(--font-mono)", color: "var(--color-accent-label)" }}
            >
              {STATUSES[idx]}
            </motion.div>
          </AnimatePresence>
        </div>
      </div>
    </div>
  );
}
