import { Zap } from "lucide-react";
import { ExperimentReview } from "../lib/feedbackStore";

type Props = {
  reviews: ExperimentReview[];
};

/**
 * Shown at the top of the results view when there are stored scientist reviews
 * that were sent as prior_feedback in the generation request. Renders a single
 * summary line — the actual review text is intentionally hidden so the banner
 * stays compact and doesn't leak the scientist's verbatim notes into the UI.
 */
export function FeedbackAppliedBanner({ reviews }: Props) {
  if (reviews.length === 0) return null;

  const correctionCount = reviews.reduce((sum, r) => {
    const lowRated = (Object.values(r.sections) as ({ rating: number; note: string } | undefined)[]).filter(
      (s) => s && s.rating > 0 && s.rating <= 3 && s.note.trim(),
    );
    return sum + lowRated.length;
  }, 0);

  return (
    <div className="mx-auto w-full max-w-[860px] px-4 sm:px-6 pt-4">
      <div
        className="flex items-center gap-3 rounded-xl px-4 py-3 text-[0.84rem] leading-snug"
        style={{
          background: "linear-gradient(135deg, var(--color-bg-dark) 0%, #1a4040 100%)",
          color: "rgba(255,255,255,0.92)",
        }}
      >
        <Zap size={16} className="flex-shrink-0" style={{ color: "var(--color-accent)" }} />
        <p className="font-semibold" style={{ color: "#fff" }}>
          Plan informed by {reviews.length} prior scientist review{reviews.length !== 1 ? "s" : ""}
          {correctionCount > 0 && ` · ${correctionCount} correction${correctionCount !== 1 ? "s" : ""} applied`}
        </p>
      </div>
    </div>
  );
}
