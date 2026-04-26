/**
 * Lightweight localStorage-backed feedback store.
 *
 * Two concern separated under two storage keys:
 *
 * 1. "predictivebio_feedback"  — per-experiment material + step corrections.
 *    Written on "Save Changes"; never pre-loaded back into the displayed plan.
 *    Used by the Benchling export and passed as context to the backend.
 *
 * 2. "predictivebio_reviews"   — structured scientist reviews (star ratings +
 *    section annotations). Written via the ReviewPanel. Passed as
 *    `prior_feedback` in the next POST /demo/run so the backend can incorporate
 *    corrections into the new plan generation.
 */

// ─── Corrections (per-experiment material / step edits) ───────────────────────

const CORRECTIONS_KEY = "predictivebio_feedback";

export type EditedMaterial = {
  name: string;
  catalog: string;
  supplier: string;
  qty_amount: number;
  qty_unit: string;
  unit_cost_eur: number;
  total_eur: number;
};

export type ExpFeedback = {
  materials?: EditedMaterial[];
  steps?: string[];
};

type CorrectionsShape = Record<string, ExpFeedback>;

function readCorrections(): CorrectionsShape {
  try {
    const raw = localStorage.getItem(CORRECTIONS_KEY);
    return raw ? (JSON.parse(raw) as CorrectionsShape) : {};
  } catch { return {}; }
}

function writeCorrections(data: CorrectionsShape): void {
  try { localStorage.setItem(CORRECTIONS_KEY, JSON.stringify(data)); }
  catch { /* quota exceeded */ }
}

export function loadMaterials(expId: string): EditedMaterial[] | null {
  return readCorrections()[expId]?.materials ?? null;
}

export function loadSteps(expId: string): string[] | null {
  return readCorrections()[expId]?.steps ?? null;
}

export function saveExpFeedback(expId: string, patch: Partial<ExpFeedback>): void {
  const store = readCorrections();
  store[expId] = { ...store[expId], ...patch };
  writeCorrections(store);
}

// ─── Reviews (structured scientist ratings) ───────────────────────────────────

const REVIEWS_KEY = "predictivebio_reviews";

export type SectionRating = {
  /** 1 (poor) to 5 (excellent) */
  rating: 1 | 2 | 3 | 4 | 5;
  note: string;
};

export type ExperimentReview = {
  experiment_id: string;
  experiment_name: string;
  /** Free-text tag the scientist applies: "cryopreservation", "western blot", etc. */
  experiment_type: string;
  timestamp: string;
  overall_rating: 1 | 2 | 3 | 4 | 5;
  sections: {
    steps?: SectionRating;
    materials?: SectionRating;
    timeline?: SectionRating;
  };
};

/** Shape the backend expects inside DemoRunRequest.prior_feedback */
export type PriorFeedbackItem = {
  experiment_type: string;
  section: string;
  rating: number;
  note: string;
  timestamp: string;
};

type ReviewsShape = ExperimentReview[];

function readReviews(): ReviewsShape {
  try {
    const raw = localStorage.getItem(REVIEWS_KEY);
    return raw ? (JSON.parse(raw) as ReviewsShape) : [];
  } catch { return []; }
}

function writeReviews(data: ReviewsShape): void {
  try { localStorage.setItem(REVIEWS_KEY, JSON.stringify(data)); }
  catch { /* quota exceeded */ }
}

export function saveReview(review: ExperimentReview): void {
  const existing = readReviews().filter((r) => r.experiment_id !== review.experiment_id);
  writeReviews([...existing, review]);
}

export function loadAllReviews(): ExperimentReview[] {
  return readReviews();
}

export function reviewCount(): number {
  return readReviews().length;
}

/**
 * Flatten all stored reviews into the flat `PriorFeedbackItem[]` format
 * the backend expects. Only sections with a note are included.
 */
export function buildPriorFeedback(): PriorFeedbackItem[] {
  const items: PriorFeedbackItem[] = [];
  for (const review of readReviews()) {
    for (const [section, sr] of Object.entries(review.sections) as [string, SectionRating][]) {
      if (sr.note.trim()) {
        items.push({
          experiment_type: review.experiment_type,
          section,
          rating: sr.rating,
          note: sr.note,
          timestamp: review.timestamp,
        });
      }
    }
    // Overall note is not a section so we skip it here; overall_rating is meta-only
  }
  return items;
}

export function getAllFeedback(): CorrectionsShape {
  return readCorrections();
}

// ─── Utilities ────────────────────────────────────────────────────────────────

export function splitQty(qty: string): { qty_amount: number; qty_unit: string } {
  const spaceIdx = qty.indexOf(" ");
  if (spaceIdx === -1) {
    const n = parseFloat(qty);
    return { qty_amount: isNaN(n) || n <= 0 ? 1 : n, qty_unit: "" };
  }
  const n = parseFloat(qty.slice(0, spaceIdx));
  return { qty_amount: isNaN(n) || n <= 0 ? 1 : n, qty_unit: qty.slice(spaceIdx + 1) };
}
