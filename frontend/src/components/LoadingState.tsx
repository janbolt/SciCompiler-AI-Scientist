import { useEffect, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";

const STATUSES = [
  "Scanning literature...",
  "Checking novelty...",
  "Drafting protocol...",
  "Calculating budget...",
];

type Props = {
  onDone: () => void;
};

export function LoadingState({ onDone }: Props) {
  const [idx, setIdx] = useState(0);

  useEffect(() => {
    const id = window.setInterval(() => {
      setIdx((i) => {
        if (i >= STATUSES.length - 1) {
          window.clearInterval(id);
          window.setTimeout(onDone, 900);
          return i;
        }
        return i + 1;
      });
    }, 1500);
    return () => window.clearInterval(id);
  }, [onDone]);

  const progress = ((idx + 1) / STATUSES.length) * 100;

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
            animate={{ width: `${progress}%` }}
            transition={{ duration: 0.8, ease: "easeOut" }}
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
