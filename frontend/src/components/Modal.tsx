import { ReactNode, useEffect } from "react";
import { AnimatePresence, motion } from "framer-motion";

type Props = {
  open: boolean;
  title: string;
  onCancel: () => void;
  onConfirm?: () => void;
  confirmLabel?: string;
  cancelLabel?: string;
  children?: ReactNode;
};

export function Modal({
  open,
  title,
  onCancel,
  onConfirm,
  confirmLabel = "Confirm",
  cancelLabel = "Cancel",
  children,
}: Props) {
  useEffect(() => {
    if (!open) return;
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") onCancel();
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onCancel]);

  return (
    <AnimatePresence>
      {open && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          transition={{ duration: 0.15 }}
          className="fixed inset-0 z-50 flex items-end sm:items-center justify-center px-4 py-6"
          style={{ background: "rgba(26,26,26,0.5)" }}
          onClick={onCancel}
        >
          <motion.div
            initial={{ y: 14, opacity: 0 }}
            animate={{ y: 0, opacity: 1 }}
            exit={{ y: 14, opacity: 0 }}
            transition={{ duration: 0.2 }}
            onClick={(e) => e.stopPropagation()}
            className="w-full max-w-[480px]"
            style={{
              background: "var(--color-card)",
              border: "1px solid var(--color-border)",
              borderRadius: 16,
              boxShadow: "0 8px 40px rgba(0,0,0,0.12)",
            }}
          >
            <div className="px-5 py-4" style={{ borderBottom: "1px solid var(--color-border)" }}>
              <h3
                className="text-lg font-bold leading-snug"
                style={{ fontFamily: "var(--font-serif)", color: "var(--color-text)" }}
              >
                {title}
              </h3>
            </div>
            {children && (
              <div className="px-5 py-4 text-sm" style={{ color: "var(--color-text)" }}>
                {children}
              </div>
            )}
            <div
              className="flex items-center justify-end gap-2 px-5 py-4"
              style={{ borderTop: "1px solid var(--color-border)" }}
            >
              <button
                type="button"
                onClick={onCancel}
                className="px-4 py-2 text-sm font-medium transition hover:opacity-80"
                style={{
                  background: "transparent",
                  color: "var(--color-text-muted)",
                  border: "1px solid var(--color-border)",
                  borderRadius: 999,
                }}
              >
                {cancelLabel}
              </button>
              {onConfirm && (
                <button
                  type="button"
                  onClick={onConfirm}
                  className="px-5 py-2 text-sm font-semibold text-white transition hover:opacity-90"
                  style={{
                    background: "var(--color-accent)",
                    border: "none",
                    borderRadius: 999,
                  }}
                >
                  {confirmLabel}
                </button>
              )}
            </div>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
