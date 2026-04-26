import { Zap } from "lucide-react";
import { ExperimentReview } from "../lib/feedbackStore";

type Props = {
  reviews: ExperimentReview[];
};

/**
 * Shown at the top of the results view when there are stored scientist reviews
 * that were sent as prior_feedback in the generation request. Makes the
 * feedback loop visible to a judge / demo audience.
 */
export function FeedbackAppliedBanner({ reviews }: Props) {
  if (reviews.length === 0) return null;

  const lowRatedSections = reviews.flatMap((r) =>
    (Object.entries(r.sections) as [string, { rating: number; note: string }][])
      .filter(([, s]) => s && s.rating > 0 && s.rating <= 3 && s.note.trim())
      .map(([section, s]) => ({ section, note: s.note, expType: r.experiment_type }))
  );

  const correctionCount = lowRatedSections.length;

  return (
    <div
      className="mx-auto w-full max-w-[860px] px-4 sm:px-6 pt-4"
    >
      <div
        className="flex items-start gap-3 rounded-xl px-4 py-3 text-[0.84rem] leading-snug"
        style={{
          background: "linear-gradient(135deg, var(--color-bg-dark) 0%, #1a4040 100%)",
          color: "rgba(255,255,255,0.92)",
        }}
      >
        <Zap size={16} className="mt-0.5 flex-shrink-0" style={{ color: "var(--color-accent)" }} />
        <div className="space-y-1 min-w-0">
          <p className="font-semibold" style={{ color: "#fff" }}>
            Plan informed by {reviews.length} prior scientist review{reviews.length !== 1 ? "s" : ""}
            {correctionCount > 0 && ` · ${correctionCount} correction${correctionCount !== 1 ? "s" : ""} applied`}
          </p>
          {lowRatedSections.slice(0, 2).map((item, i) => (
            <p key={i} className="text-[0.78rem] truncate" style={{ color: "rgba(255,255,255,0.65)" }}>
              {item.expType} › {item.section}: "{item.note}"
            </p>
          ))}
          {lowRatedSections.length > 2 && (
            <p className="text-[0.78rem]" style={{ color: "rgba(255,255,255,0.5)" }}>
              + {lowRatedSections.length - 2} more
            </p>
          )}
        </div>
      </div>
    </div>
  );
}
