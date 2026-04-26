import { useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { AlertCircle, RefreshCw } from "lucide-react";
import { Navbar } from "./components/Navbar";
import { InputScreen } from "./components/InputScreen";
import { LoadingState } from "./components/LoadingState";
import { TabBar, TabId } from "./components/TabBar";
import { OverviewTab } from "./components/OverviewTab";
import { ExperimentsTab } from "./components/ExperimentsTab";
import { BudgetTab } from "./components/BudgetTab";
import { SubmitTab } from "./components/SubmitTab";
import { FeedbackAppliedBanner } from "./components/FeedbackAppliedBanner";
import { buildPriorFeedback, loadApplicableReviews } from "./lib/feedbackStore";
import { usePlan, useSetPlan } from "./context/PlanContext";
import { PlanData } from "./mockData";

type Stage = "input" | "loading" | "results" | "error";

type ApiError = {
  reason: string;
  message: string;
  status: number;
};

/**
 * Build a single string out of everything the backend has identified as
 * "this run's topic" so the relevance filter can match scientist reviews
 * tagged with experiment-type keywords against it.
 */
function buildHypothesisContext(hypothesis: string, plan: PlanData): string {
  const expBlobs = plan.experiments.map((e) => `${e.name} ${e.goal}`).join(" ");
  return [hypothesis, plan.hypothesis, plan.objective, expBlobs].join(" ");
}

export default function App() {
  const [stage, setStage] = useState<Stage>("input");
  const [tab, setTab] = useState<TabId>("overview");
  const [currentHypothesis, setCurrentHypothesis] = useState("");
  const [fetchReady, setFetchReady] = useState(false);
  const [apiError, setApiError] = useState<ApiError | null>(null);

  const plan = usePlan();
  const setPlan = useSetPlan();

  function reset() {
    setStage("input");
    setTab("overview");
    setApiError(null);
  }

  async function handleSubmit(hypothesis: string, regenerate: boolean = false) {
    setCurrentHypothesis(hypothesis);
    setStage("loading");
    setFetchReady(false);
    setApiError(null);

    const relevanceContext = regenerate
      ? buildHypothesisContext(hypothesis, plan)
      : hypothesis;
    const priorFeedback = buildPriorFeedback(relevanceContext);
    const useFixture = new URLSearchParams(window.location.search).get("fixture") === "crp";
    const endpoint = useFixture ? "/fixtures/crp_biosensor_plan_data.json" : "/api/demo/plan";
    const init: RequestInit | undefined = useFixture
      ? undefined
      : {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ question: hypothesis, prior_feedback: priorFeedback }),
        };

    if (typeof window !== "undefined" && /^(localhost|127\.|0\.0\.0\.0)/.test(window.location.hostname)) {
      // eslint-disable-next-line no-console
      console.log("[plan] POST", endpoint, {
        regenerate,
        priorFeedbackCount: priorFeedback.length,
        priorFeedback,
      });
    }

    try {
      const res = await fetch(endpoint, init);
      if (!res.ok) {
        // FastAPI returns {"detail": {...}} on HTTPException — surface that.
        let reason = "http_error";
        let message = `Backend returned ${res.status} ${res.statusText}`;
        try {
          const errBody = await res.json();
          if (errBody && typeof errBody === "object" && errBody.detail) {
            const d = errBody.detail;
            if (typeof d === "string") {
              message = d;
            } else if (typeof d === "object") {
              if (d.reason) reason = String(d.reason);
              if (d.message) message = String(d.message);
            }
          }
        } catch {
          /* response body wasn't JSON — keep default message */
        }
        // eslint-disable-next-line no-console
        console.error("[plan] backend error", { status: res.status, reason, message });
        setApiError({ reason, message, status: res.status });
        setStage("error");
        return;
      }
      const data = (await res.json()) as PlanData;
      setPlan(data);
      setFetchReady(true);
    } catch (err) {
      const message = err instanceof Error ? err.message : String(err);
      // eslint-disable-next-line no-console
      console.error("[plan] network/parse failure", err);
      setApiError({
        reason: "network_error",
        message: `Could not reach backend: ${message}. Is uvicorn running on :8000?`,
        status: 0,
      });
      setStage("error");
    }
  }

  function handleRegenerate() {
    if (!currentHypothesis) return;
    handleSubmit(currentHypothesis, true);
  }

  // Filter stored reviews to only those topically relevant to the current run.
  // Scope: the user's input hypothesis plus the plan-derived experiment text.
  const hypothesisContext = buildHypothesisContext(currentHypothesis, plan);
  const activeReviews = loadApplicableReviews(hypothesisContext);

  return (
    <div className="min-h-screen text-[var(--color-text)]">
      <Navbar onReset={stage !== "input" ? reset : undefined} />

      <AnimatePresence mode="wait">
        {stage === "input" && (
          <motion.div key="input" exit={{ opacity: 0 }} transition={{ duration: 0.2 }}>
            <InputScreen onSubmit={handleSubmit} />
          </motion.div>
        )}

        {stage === "loading" && (
          <motion.div
            key="loading"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.2 }}
          >
            <LoadingState onDone={() => setStage("results")} ready={fetchReady} />
          </motion.div>
        )}

        {stage === "error" && (
          <motion.div
            key="error"
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.3 }}
          >
            <main className="mx-auto w-full max-w-[680px] px-4 py-12 sm:px-6">
              <section
                className="card px-6 py-8 space-y-5"
                style={{ borderLeft: "4px solid var(--color-badge-red)" }}
              >
                <div className="flex items-start gap-3">
                  <AlertCircle
                    size={22}
                    className="flex-shrink-0 mt-0.5"
                    style={{ color: "var(--color-badge-red)" }}
                  />
                  <div className="space-y-1">
                    <div className="eyebrow" style={{ color: "var(--color-badge-red)" }}>
                      Plan generation failed
                    </div>
                    <h2
                      className="text-2xl font-bold tracking-tight"
                      style={{ fontFamily: "var(--font-serif)", color: "var(--color-text)" }}
                    >
                      The backend couldn't generate this plan.
                    </h2>
                  </div>
                </div>
                <div className="divider" />
                <div className="space-y-2 text-sm">
                  <p style={{ color: "var(--color-text)" }}>{apiError?.message}</p>
                  <p
                    className="text-[0.78rem]"
                    style={{ fontFamily: "var(--font-mono)", color: "var(--color-text-muted)" }}
                  >
                    reason: <span style={{ color: "var(--color-text)" }}>{apiError?.reason}</span>
                    {apiError && apiError.status > 0 ? `  ·  http: ${apiError.status}` : ""}
                  </p>
                </div>
                {apiError?.reason === "llm_unreachable" && (
                  <div
                    className="rounded-md px-4 py-3 text-[0.82rem] leading-relaxed"
                    style={{ background: "var(--color-bg)", color: "var(--color-text-muted)" }}
                  >
                    Quick fixes:
                    <ul className="mt-1 list-disc pl-5 space-y-0.5">
                      <li>Check your internet connection.</li>
                      <li>
                        Verify <code className="font-mono">OPENAI_API_KEY</code> in{" "}
                        <code className="font-mono">backend/.env</code>.
                      </li>
                      <li>
                        For offline / demo mode set{" "}
                        <code className="font-mono">USE_STUB_AGENTS=true</code> and restart uvicorn.
                      </li>
                    </ul>
                  </div>
                )}
                <div className="flex gap-3 pt-1">
                  <button
                    type="button"
                    onClick={() => handleSubmit(currentHypothesis, false)}
                    className="inline-flex items-center gap-2 px-4 py-2 text-[0.84rem] font-semibold transition hover:opacity-80"
                    style={{
                      background: "var(--color-accent-light)",
                      color: "var(--color-accent-deep)",
                      border: "1.5px solid var(--color-accent)",
                      borderRadius: 999,
                    }}
                  >
                    <RefreshCw size={13} strokeWidth={2.5} />
                    Try again
                  </button>
                  <button
                    type="button"
                    onClick={reset}
                    className="inline-flex items-center gap-2 px-4 py-2 text-[0.84rem] font-medium transition hover:opacity-70"
                    style={{
                      background: "transparent",
                      color: "var(--color-text-muted)",
                      border: "1.5px solid var(--color-border)",
                      borderRadius: 999,
                    }}
                  >
                    Start over
                  </button>
                </div>
              </section>
            </main>
          </motion.div>
        )}

        {stage === "results" && (
          <motion.div
            key="results"
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.3 }}
          >
            <FeedbackAppliedBanner reviews={activeReviews} />
            <TabBar active={tab} onChange={setTab} />
            <main className="mx-auto w-full max-w-[860px] px-4 py-6 sm:px-6 sm:py-8">
              <AnimatePresence mode="wait">
                <motion.div
                  key={tab}
                  initial={{ opacity: 0, y: 8 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, y: -8 }}
                  transition={{ duration: 0.2 }}
                >
                  {tab === "overview" && <OverviewTab onRegenerate={handleRegenerate} />}
                  {tab === "experiments" && <ExperimentsTab />}
                  {tab === "budget" && <BudgetTab />}
                  {tab === "submit" && <SubmitTab />}
                </motion.div>
              </AnimatePresence>
            </main>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
