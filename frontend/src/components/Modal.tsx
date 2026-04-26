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
          style={{ background: "rgba(10,10,10,0.45)" }}
          onClick={onCancel}
        >
          <motion.div
            initial={{ y: 12, opacity: 0 }}
            animate={{ y: 0, opacity: 1 }}
            exit={{ y: 12, opacity: 0 }}
            transition={{ duration: 0.2 }}
            onClick={(e) => e.stopPropagation()}
            className="w-full max-w-[480px] bg-white"
            style={{ border: "1px solid var(--color-border)", borderRadius: 0 }}
          >
            <div className="px-5 py-4" style={{ borderBottom: "1px solid var(--color-border)" }}>
              <h3 className="text-base font-semibold leading-snug">{title}</h3>
            </div>
            {children && <div className="px-5 py-4 text-sm">{children}</div>}
            <div className="flex items-center justify-end gap-2 px-5 py-4" style={{ borderTop: "1px solid var(--color-border)" }}>
              <button
                type="button"
                onClick={onCancel}
                className="px-4 py-2 text-sm transition hover:opacity-80"
                style={{
                  background: "white",
                  color: "var(--color-text)",
                  border: "1px solid var(--color-border)",
                  borderRadius: 4,
                }}
              >
                {cancelLabel}
              </button>
              {onConfirm && (
                <button
                  type="button"
                  onClick={onConfirm}
                  className="px-4 py-2 text-sm font-semibold transition hover:opacity-90"
                  style={{
                    background: "var(--color-accent)",
                    color: "white",
                    border: "1px solid var(--color-accent)",
                    borderRadius: 4,
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
