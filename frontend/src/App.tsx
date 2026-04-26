import { useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { Navbar } from "./components/Navbar";
import { InputScreen } from "./components/InputScreen";
import { LoadingState } from "./components/LoadingState";
import { TabBar, TabId } from "./components/TabBar";
import { OverviewTab } from "./components/OverviewTab";
import { ExperimentsTab } from "./components/ExperimentsTab";
import { BudgetTab } from "./components/BudgetTab";
import { SubmitTab } from "./components/SubmitTab";
import { FeedbackAppliedBanner } from "./components/FeedbackAppliedBanner";
import { buildPriorFeedback, loadAllReviews } from "./lib/feedbackStore";
import { useSetPlan } from "./context/PlanContext";
import { PlanData } from "./mockData";

type Stage = "input" | "loading" | "results";

export default function App() {
  const [stage, setStage] = useState<Stage>("input");
  const [tab, setTab] = useState<TabId>("overview");
  const [currentHypothesis, setCurrentHypothesis] = useState("");
  const [fetchReady, setFetchReady] = useState(false);

  const setPlan = useSetPlan();

  function reset() {
    setStage("input");
    setTab("overview");
  }

  function handleSubmit(hypothesis: string) {
    setCurrentHypothesis(hypothesis);
    setStage("loading");
    setFetchReady(false);

    const priorFeedback = buildPriorFeedback();
    const useFixture = new URLSearchParams(window.location.search).get("fixture") === "crp";
    const endpoint = useFixture ? "/fixtures/crp_biosensor_plan_data.json" : "/api/demo/plan";
    const init = useFixture
      ? undefined
      : {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ question: hypothesis, prior_feedback: priorFeedback }),
        };

    // Call the frontend-shaped endpoint; update plan context if successful.
    // Falls back to MOCK_PLAN (already in context) if backend is unreachable.
    fetch(endpoint, init)
      .then((res) => {
        // #region agent log
        fetch('http://127.0.0.1:7293/ingest/3a3fd8fd-a1e7-459c-8132-bb16645c37e2',{method:'POST',headers:{'Content-Type':'application/json','X-Debug-Session-Id':'323526'},body:JSON.stringify({sessionId:'323526',runId:'run1',hypothesisId:'H8',location:'App.tsx:50',message:'fetch_response',data:{endpoint,status:res.status,ok:res.ok},timestamp:Date.now()})}).catch(()=>{});
        // #endregion
        if (!res.ok) throw new Error(res.statusText);
        return res.json() as Promise<PlanData>;
      })
      .then((data) => {
        // #region agent log
        fetch('http://127.0.0.1:7293/ingest/3a3fd8fd-a1e7-459c-8132-bb16645c37e2',{method:'POST',headers:{'Content-Type':'application/json','X-Debug-Session-Id':'323526'},body:JSON.stringify({sessionId:'323526',runId:'run1',hypothesisId:'H9',location:'App.tsx:55',message:'set_plan_from_api',data:{confidence_score:data?.confidence_score,experiments_count:Array.isArray(data?.experiments)?data.experiments.length:-1},timestamp:Date.now()})}).catch(()=>{});
        // #endregion
        setPlan(data);
        setFetchReady(true);
      })
      .catch((err: unknown) => {
        const errorMessage = err instanceof Error ? err.message : String(err);
        // #region agent log
        fetch('http://127.0.0.1:7293/ingest/3a3fd8fd-a1e7-459c-8132-bb16645c37e2',{method:'POST',headers:{'Content-Type':'application/json','X-Debug-Session-Id':'323526'},body:JSON.stringify({sessionId:'323526',runId:'run1',hypothesisId:'H10',location:'App.tsx:59',message:'fetch_fallback_to_mock',data:{endpoint,errorMessage},timestamp:Date.now()})}).catch(()=>{});
        // #endregion
        // Backend not reachable — MOCK_PLAN remains in context; still unblock loading
        setFetchReady(true);
      });
  }

  function handleRegenerate() {
    if (!currentHypothesis) return;
    handleSubmit(currentHypothesis);
  }

  const activeReviews = loadAllReviews();

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
