export type Material = {
  name: string;
  catalog: string;
  supplier: string;
  qty: string;
  unit_cost_eur: number;
  total_eur: number;
};

export type Experiment = {
  id: string;
  name: string;
  duration: string;
  cro_compatible: boolean;
  goal: string;
  success_criteria: string;
  steps: string[];
  materials: Material[];
};

export type Reference = {
  citation: string;
  doi: string;
};

export type BudgetLine = { item: string; cost_eur: number };

export type PlanData = {
  hypothesis: string;
  objective: string;
  /** @deprecated derive from phases[].days sum instead */
  total_duration_days?: number;
  /** @deprecated derive from budget.total_eur instead */
  total_budget_eur?: number;
  novelty_signal: "not found" | "similar work exists" | "exact match found";
  /** 0.0–1.0 AI confidence in the generated plan (literature × protocol × readiness) */
  confidence_score: number;
  references: Reference[];
  experiments: Experiment[];
  budget: {
    fixed: BudgetLine[];
    staff: BudgetLine[];
    recurring: BudgetLine[];
    total_eur: number;
  };
  phases: { name: string; days: number }[];
};

export const PREFILL_HYPOTHESIS =
  "Supplementing C57BL/6 mice with Lactobacillus rhamnosus GG for 4 weeks will reduce intestinal permeability by 30% vs controls, measured by FITC-dextran assay, due to upregulation of claudin-1 and occludin.";

export const MOCK_PLAN: PlanData = {
  hypothesis:
    "Supplementing C57BL/6 mice with Lactobacillus rhamnosus GG for 4 weeks will reduce intestinal permeability by 30% vs controls, measured by FITC-dextran assay, due to upregulation of tight junction proteins claudin-1 and occludin.",
  objective:
    "Establish whether LGG supplementation measurably strengthens the murine gut barrier within a 4-week supplementation window.",
  total_duration_days: 35,
  total_budget_eur: 8240,
  novelty_signal: "similar work exists",
  confidence_score: 0.72,
  references: [
    {
      citation:
        "Korpela et al. (2016). LGG intake modifies probiotic and non-probiotic core gut microbiota. Nature Communications 7.",
      doi: "10.1038/ncomms10979",
    },
    {
      citation:
        "Cani et al. (2022). Gut microbiota and intestinal permeability: Role of tight junctions. Cell Host & Microbe.",
      doi: "10.1016/j.chom.2022.03.010",
    },
  ],
  phases: [
    { name: "Animal Setup", days: 7 },
    { name: "Supplementation", days: 28 },
    { name: "FITC-Dextran Assay", days: 1 },
    { name: "Western Blot", days: 3 },
    { name: "Analysis", days: 3 },
  ],
  experiments: [
    {
      id: "exp-01",
      name: "Animal Setup & LGG Supplementation",
      duration: "7 days setup + 28 days treatment",
      cro_compatible: false,
      goal: "Acclimatize C57BL/6 mice and administer daily LGG supplementation vs vehicle control for 4 weeks.",
      success_criteria:
        "All animals reach end of 4-week treatment with less than 10% body weight loss; daily gavage confirmed in log.",
      steps: [
        "Source 20 male C57BL/6 mice (8 weeks old, 20-25g) from certified supplier. Acclimatize for 7 days in BSL-1 housing, 12h light/dark cycle, ad libitum water and standard chow.",
        "Randomize into two groups of 10: LGG group and vehicle control group.",
        "Prepare LGG gavage solution: resuspend lyophilized LGG (ATCC 53103) in PBS to 1x10^9 CFU/ml. Prepare fresh daily.",
        "Administer 200 ul of LGG solution (LGG group) or 200 ul PBS (control group) by oral gavage daily at 09:00 for 28 consecutive days.",
        "Weigh animals every 3 days. Record body weights and stool consistency.",
        "On day 28, fast animals for 4 hours prior to FITC-dextran assay.",
      ],
      materials: [
        {
          name: "C57BL/6 mice (male, 8 weeks)",
          catalog: "000664",
          supplier: "Jackson Laboratory",
          qty: "20 animals",
          unit_cost_eur: 45,
          total_eur: 900,
        },
        {
          name: "Lactobacillus rhamnosus GG (ATCC 53103)",
          catalog: "53103",
          supplier: "ATCC",
          qty: "1 vial lyophilized",
          unit_cost_eur: 140,
          total_eur: 140,
        },
        {
          name: "PBS (sterile, pH 7.4)",
          catalog: "10010023",
          supplier: "Thermo Fisher",
          qty: "500 ml",
          unit_cost_eur: 12,
          total_eur: 12,
        },
        {
          name: "Oral gavage needles (20G)",
          catalog: "FN-7902",
          supplier: "Fine Science Tools",
          qty: "10",
          unit_cost_eur: 3,
          total_eur: 30,
        },
      ],
    },
    {
      id: "exp-02",
      name: "FITC-Dextran Intestinal Permeability Assay",
      duration: "6 hours (1 day)",
      cro_compatible: true,
      goal: "Quantify intestinal permeability by measuring serum FITC-dextran concentration following oral gavage.",
      success_criteria:
        "30% reduction in serum FITC-dextran in LGG group vs controls (p<0.05 by unpaired t-test).",
      steps: [
        "After 4-hour fast, administer 150 mg/kg FITC-dextran (MW 4,000 Da, FD4) in PBS by oral gavage. Volume: 200 ul per mouse at 75 mg/ml.",
        "Return mice to cages for 4 hours. No food or water.",
        "Anesthetize with isoflurane (2-3% induction, 1.5% maintenance).",
        "Collect blood by cardiac puncture into EDTA tubes. Centrifuge 2,000xg, 15 min, 4C to obtain plasma.",
        "Dilute plasma 1:2 in PBS. Load 100 ul per well in black 96-well plate (duplicate wells per animal).",
        "Read fluorescence: excitation 485 nm, emission 528 nm.",
        "Calculate concentration from standard curve (0-2,000 ng/ml FD4 in PBS + 50% plasma).",
        "Express as ng FITC-dextran per ml plasma. Compare groups by unpaired t-test.",
      ],
      materials: [
        {
          name: "FITC-Dextran MW 4000 (FD4)",
          catalog: "FD4-1G",
          supplier: "Sigma-Aldrich",
          qty: "1 g",
          unit_cost_eur: 380,
          total_eur: 380,
        },
        {
          name: "Black 96-well flat-bottom plate",
          catalog: "3915",
          supplier: "Corning",
          qty: "2 plates",
          unit_cost_eur: 18,
          total_eur: 36,
        },
        {
          name: "EDTA blood collection tubes",
          catalog: "365974",
          supplier: "BD Vacutainer",
          qty: "25 tubes",
          unit_cost_eur: 0.8,
          total_eur: 20,
        },
        {
          name: "Isoflurane",
          catalog: "NDC 66794-013",
          supplier: "Piramal",
          qty: "100 ml",
          unit_cost_eur: 42,
          total_eur: 42,
        },
      ],
    },
    {
      id: "exp-03",
      name: "Western Blot — Claudin-1 & Occludin Expression",
      duration: "3 days",
      cro_compatible: true,
      goal: "Quantify claudin-1 and occludin protein expression in intestinal tissue from both groups.",
      success_criteria:
        "Statistically significant upregulation of claudin-1 and/or occludin in LGG group (normalized to beta-actin, p<0.05).",
      steps: [
        "Sacrifice animals by cervical dislocation. Excise 5 cm of proximal jejunum per animal. Flash-freeze in liquid nitrogen.",
        "Homogenize tissue in RIPA buffer (150 mM NaCl, 1% NP-40, 0.5% sodium deoxycholate, 0.1% SDS, 50 mM Tris pH 8.0) + protease inhibitor cocktail. 30 mg tissue per 300 ul buffer.",
        "Centrifuge 12,000xg, 15 min, 4C. Collect supernatant (protein lysate).",
        "Quantify protein by BCA assay. Normalize to 30 ug total protein per lane.",
        "Run SDS-PAGE on 12% gel (claudin-1: ~23 kDa, occludin: ~65 kDa, beta-actin: ~42 kDa). 90V for 2h.",
        "Transfer to PVDF membrane at 100V for 1h on ice.",
        "Block in 5% skim milk / TBST for 1h RT.",
        "Primary antibody overnight 4C: anti-claudin-1 (1:1000), anti-occludin (1:1000), anti-beta-actin (1:5000) in 3% BSA/TBST.",
        "Wash 3x TBST 10 min. HRP secondary antibody 1h RT.",
        "Develop with ECL. Image on ChemiDoc. Quantify band density with ImageJ.",
      ],
      materials: [
        {
          name: "Anti-claudin-1 antibody (rabbit)",
          catalog: "AB15098",
          supplier: "Abcam",
          qty: "100 ul",
          unit_cost_eur: 380,
          total_eur: 380,
        },
        {
          name: "Anti-occludin antibody (rabbit)",
          catalog: "AB216327",
          supplier: "Abcam",
          qty: "100 ul",
          unit_cost_eur: 390,
          total_eur: 390,
        },
        {
          name: "Anti-beta-actin antibody (mouse)",
          catalog: "AB8226",
          supplier: "Abcam",
          qty: "100 ul",
          unit_cost_eur: 260,
          total_eur: 260,
        },
        {
          name: "HRP anti-rabbit secondary",
          catalog: "7074S",
          supplier: "Cell Signaling",
          qty: "1 vial",
          unit_cost_eur: 220,
          total_eur: 220,
        },
        {
          name: "RIPA Buffer",
          catalog: "9806S",
          supplier: "Cell Signaling",
          qty: "50 ml",
          unit_cost_eur: 58,
          total_eur: 58,
        },
        {
          name: "BCA Protein Assay Kit",
          catalog: "23225",
          supplier: "Thermo Fisher",
          qty: "1 kit",
          unit_cost_eur: 92,
          total_eur: 92,
        },
        {
          name: "ECL Western Blotting Substrate",
          catalog: "32109",
          supplier: "Thermo Fisher",
          qty: "50 ml",
          unit_cost_eur: 65,
          total_eur: 65,
        },
        {
          name: "PVDF Membrane",
          catalog: "IPVH00010",
          supplier: "Millipore",
          qty: "1 roll",
          unit_cost_eur: 175,
          total_eur: 175,
        },
      ],
    },
    {
      id: "exp-04",
      name: "Statistical Analysis & Reporting",
      duration: "2-3 days",
      cro_compatible: false,
      goal: "Analyze all datasets, generate figures, and determine whether results meet the hypothesis threshold.",
      success_criteria:
        "Primary endpoint: 30% reduction in FITC-dextran (p<0.05). Secondary: significant TJ upregulation in at least 1 target protein.",
      steps: [
        "Import FITC fluorescence readings and western blot densitometry into GraphPad Prism or R.",
        "Test normality with Shapiro-Wilk test (n=10 per group).",
        "Compare FITC-dextran serum levels: unpaired two-tailed t-test if normal; Mann-Whitney U if not.",
        "Compare band densities (claudin-1, occludin normalized to beta-actin): same statistical approach.",
        "Generate bar graphs with individual data points (mean +/- SEM). Mark significance: *p<0.05, **p<0.01.",
        "Write summary: was the primary hypothesis threshold met? State effect size and 95% CI.",
        "Flag for follow-up: if permeability reduced but TJ proteins not upregulated, suggest alternative mechanisms.",
      ],
      materials: [
        {
          name: "GraphPad Prism license",
          catalog: "software",
          supplier: "GraphPad",
          qty: "1 month",
          unit_cost_eur: 38,
          total_eur: 38,
        },
      ],
    },
  ],
  budget: {
    fixed: [
      { item: "Animal housing & husbandry (35 days x 20 mice)", cost_eur: 1200 },
      { item: "Equipment use fees (plate reader, ChemiDoc, centrifuge)", cost_eur: 320 },
    ],
    staff: [{ item: "Researcher time (62h x 45 EUR/h)", cost_eur: 2790 }],
    recurring: [
      { item: "LGG probiotic (ATCC 53103)", cost_eur: 140 },
      { item: "FITC-dextran FD4 + plate consumables", cost_eur: 480 },
      { item: "Western blot antibodies", cost_eur: 1250 },
      { item: "Western blot reagents (ECL, PVDF, BCA, buffers)", cost_eur: 390 },
      { item: "Animal consumables (feed, bedding, gavage needles)", cost_eur: 942 },
      { item: "Analysis software", cost_eur: 38 },
    ],
    total_eur: 8240,
  },
};
