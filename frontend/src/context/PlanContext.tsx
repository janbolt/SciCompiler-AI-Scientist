import { createContext, useContext, useState, ReactNode } from "react";
import { PlanData, MOCK_PLAN } from "../mockData";

type PlanContextType = {
  plan: PlanData;
  setPlan: (plan: PlanData) => void;
};

const PlanContext = createContext<PlanContextType>({
  plan: MOCK_PLAN,
  setPlan: () => {},
});

export function PlanProvider({ children }: { children: ReactNode }) {
  const [plan, setPlan] = useState<PlanData>(MOCK_PLAN);
  return (
    <PlanContext.Provider value={{ plan, setPlan }}>
      {children}
    </PlanContext.Provider>
  );
}

/** Read the current plan — use this in tab components. */
export function usePlan(): PlanData {
  return useContext(PlanContext).plan;
}

/** Update the plan — use this in App.tsx after a successful API response. */
export function useSetPlan(): (plan: PlanData) => void {
  return useContext(PlanContext).setPlan;
}
