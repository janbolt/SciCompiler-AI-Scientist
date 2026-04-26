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

// ─── Hypothesis-relevance filter ──────────────────────────────────────────────

/**
 * Generic experimental words that don't carry topical meaning. Excluded
 * before matching so a review tagged "western blot experiment" doesn't
 * match every hypothesis just because both contain the word "experiment".
 */
const STOPWORDS = new Set([
  "a", "an", "and", "or", "the", "of", "to", "in", "for", "with", "by",
  "on", "at", "as", "is", "are", "be", "this", "that", "these", "those",
  "experiment", "experiments", "study", "studies", "test", "tests",
  "assay", "assays", "protocol", "protocols", "method", "methods",
  "analysis", "based", "using", "use", "vs", "versus",
]);

/** Minimum shared-prefix length for stem matching between two tokens. */
const STEM_PREFIX_LEN = 4;

function tokens(text: string): string[] {
  return text
    .toLowerCase()
    .split(/[^a-z0-9-]+/)
    .filter((t) => t.length > 2 && !STOPWORDS.has(t));
}

/**
 * Returns true when two tokens are likely about the same topic. Catches
 * morphological variants and common scientific stems that simple substring
 * matching misses, e.g.:
 *   - "cryopreservation" ↔ "cryoprotectant"  (stem "cryo*")
 *   - "cryopreservation" ↔ "cryopreserve"
 *   - "western"          ↔ "westerns"
 *   - "qpcr"             ↔ "pcr"
 */
function tokensRelated(a: string, b: string): boolean {
  if (!a || !b) return false;
  if (a === b) return true;
  if (a.includes(b) || b.includes(a)) return true;
  if (a.length >= STEM_PREFIX_LEN && b.length >= STEM_PREFIX_LEN) {
    return a.slice(0, STEM_PREFIX_LEN) === b.slice(0, STEM_PREFIX_LEN);
  }
  return false;
}

/**
 * A review is applicable to the current context if any meaningful token from
 * its experiment_type tag (or its experiment_name as a fallback) is related
 * to any token in the current hypothesis / plan / experiment text. Matching
 * is case-insensitive and uses both substring and shared-stem heuristics.
 */
export function isReviewApplicable(review: ExperimentReview, contextText: string): boolean {
  const haystackTokens = tokens(contextText);
  const reviewTokens = [
    ...tokens(review.experiment_type || ""),
    ...tokens(review.experiment_name || ""),
  ];
  if (reviewTokens.length === 0 || haystackTokens.length === 0) return false;
  return reviewTokens.some((rt) => haystackTokens.some((ht) => tokensRelated(rt, ht)));
}

export function loadApplicableReviews(contextText: string): ExperimentReview[] {
  if (!contextText || !contextText.trim()) return [];
  return readReviews().filter((r) => isReviewApplicable(r, contextText));
}

/**
 * Flatten all stored reviews into the flat `PriorFeedbackItem[]` format
 * the backend expects. Only sections with a note are included.
 *
 * Pass a non-empty `contextText` (e.g. the current hypothesis) to limit
 * the output to reviews relevant to that context. With no contextText
 * the function returns every stored note (legacy behavior).
 */
export function buildPriorFeedback(contextText: string = ""): PriorFeedbackItem[] {
  const reviews = contextText.trim()
    ? readReviews().filter((r) => isReviewApplicable(r, contextText))
    : readReviews();

  const items: PriorFeedbackItem[] = [];
  for (const review of reviews) {
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
