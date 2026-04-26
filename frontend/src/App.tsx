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

type Stage = "input" | "loading" | "results";

export default function App() {
  const [stage, setStage] = useState<Stage>("input");
  const [tab, setTab] = useState<TabId>("overview");

  return (
    <div className="min-h-screen text-[var(--color-text)]">
      <Navbar />

      <AnimatePresence mode="wait">
        {stage === "input" && (
          <motion.div key="input" exit={{ opacity: 0 }} transition={{ duration: 0.2 }}>
            <InputScreen onSubmit={() => setStage("loading")} />
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
            <LoadingState onDone={() => setStage("results")} />
          </motion.div>
        )}

        {stage === "results" && (
          <motion.div
            key="results"
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.3 }}
          >
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
                  {tab === "overview" && <OverviewTab />}
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
