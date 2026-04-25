export type DemoResponse = {
  hypothesis: Record<string, unknown>;
  literature_qc: {
    novelty_signal: "not_found" | "similar_work_exists" | "exact_match_found";
    confidence: number;
    explanation: string;
    relevant_references: Array<{ title: string; source: string; url?: string | null }>;
  };
  protocol_candidates: Array<Record<string, unknown>>;
  evidence_claims: Array<Record<string, unknown>>;
  risks: Array<{
    risk_id: string;
    category: string;
    severity: string;
    description: string;
    plan_action: string;
    required_mitigation: string;
  }>;
  plan: {
    id: string;
    objective: string;
    experimental_design: string;
    controls: string[];
    assumptions: string[];
    decision_criteria: string[];
    step_by_step_protocol: Array<{ step_number: number; description: string; linked_to: string }>;
    risk_mitigations_applied: string[];
    feedback_incorporated: string[];
  };
  materials: Array<{
    name: string;
    supplier: string;
    catalog_reference?: string | null;
    quantity: string;
    estimated_unit_cost?: number | null;
    confidence: string;
  }>;
  budget: {
    estimated_total_cost: number;
    currency: string;
    notes: string;
    line_items: Array<{
      item_name: string;
      quantity: string;
      total_cost_estimate: number;
      confidence: string;
      catalog_reference?: string | null;
    }>;
  };
  timeline: {
    estimated_total_days: number;
    phases: Array<{
      phase_name: string;
      estimated_duration_days: number;
      dependencies: string[];
      risk_buffer_days: number;
    }>;
  };
  validation: {
    primary_endpoint: string;
    secondary_endpoints: string[];
    success_threshold: string;
    failure_conditions: string[];
    suggested_statistical_comparison: string;
  };
  cro_ready_brief: Record<string, unknown>;
  confidence_score: number;
};
