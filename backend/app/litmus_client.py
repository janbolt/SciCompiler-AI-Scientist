"""
litmus_client.py
----------------
HTTP client for the Litmus Science API (https://api.litmus.science).

Responsibilities:
- Classify each experiment into a Litmus experiment_type
- Derive a null hypothesis from the plan hypothesis
- Validate an experiment spec (POST /validate) before submission
- Submit an experiment (POST /experiments) and return the live response
"""
from __future__ import annotations

import os
import re

import httpx

LITMUS_BASE_URL = "https://api.litmus.science"
LITMUS_TIMEOUT = 20  # seconds


# ── Experiment type classifier ─────────────────────────────────────────────────

_TYPE_KEYWORDS: list[tuple[list[str], str]] = [
    (["mic ", "mbc ", "antimicrobial", "minimum inhibitory", "minimum bactericidal"], "MIC_MBC_ASSAY"),
    (["qpcr", "q-pcr", "gene expression", "rna expression", "mrna"], "QPCR_EXPRESSION"),
    (["ic50", "cell viability", "cytotoxicity", "mtt", "resazurin"], "CELL_VIABILITY_IC50"),
    (["enzyme inhibit", "ki ", "kinetics", "michaelis", "kcat"], "ENZYME_INHIBITION_IC50"),
    (["microbial growth", "growth curve", "od600", "colony count"], "MICROBIAL_GROWTH_MATRIX"),
    (["zone of inhibition", "disk diffusion", "agar diffusion"], "ZONE_OF_INHIBITION"),
    (["sanger", "sequenc", "plasmid verif", "construct verif"], "SANGER_PLASMID_VERIFICATION"),
]


def classify_experiment_type(name: str, goal: str) -> str:
    """Return the most appropriate Litmus experiment type based on name and goal."""
    haystack = (name + " " + goal).lower()
    for keywords, exp_type in _TYPE_KEYWORDS:
        if any(kw in haystack for kw in keywords):
            return exp_type
    return "CUSTOM"


# ── Null hypothesis deriver ────────────────────────────────────────────────────

def derive_null_hypothesis(hypothesis: str) -> str:
    """
    Produce a plausible null hypothesis from the plan hypothesis.
    Strategy: strip specific quantitative claims and negate the relationship.
    """
    # Remove parenthetical measurement details to keep it readable
    cleaned = re.sub(r"\([^)]*\)", "", hypothesis).strip()
    # Simple negation prefix
    return f"{cleaned.rstrip('.')} will show no statistically significant effect compared to controls."


# ── API helpers ────────────────────────────────────────────────────────────────

def _api_key() -> str:
    key = os.getenv("LITMUS_API_KEY", "")
    if not key:
        raise RuntimeError("LITMUS_API_KEY environment variable is not set.")
    return key


def _headers() -> dict[str, str]:
    return {
        "X-API-Key": _api_key(),
        "Content-Type": "application/json",
    }


def _build_intake(
    hypothesis: str,
    experiment_name: str,
    experiment_goal: str,
) -> dict:
    """Construct a Litmus experiment intake payload from plan data."""
    return {
        "experiment_type": classify_experiment_type(experiment_name, experiment_goal),
        "title": experiment_name,
        "hypothesis": {
            "statement": hypothesis,
            "null_hypothesis": derive_null_hypothesis(hypothesis),
        },
        "compliance": {"bsl": "BSL1"},
        "privacy": "open",
        "metadata": {
            "submitter_type": "ai_agent",
            "agent_identifier": "predictivebio",
        },
    }


# ── Public API ─────────────────────────────────────────────────────────────────

def validate_experiment(hypothesis: str, experiment_name: str, experiment_goal: str) -> dict:
    """
    Call POST /validate and return the raw Litmus validation result.
    Raises httpx.HTTPStatusError on non-2xx.
    """
    payload = _build_intake(hypothesis, experiment_name, experiment_goal)
    with httpx.Client(timeout=LITMUS_TIMEOUT) as client:
        resp = client.post(
            f"{LITMUS_BASE_URL}/validate",
            json=payload,
            headers=_headers(),
        )
        resp.raise_for_status()
        return resp.json()


def submit_experiment(hypothesis: str, experiment_name: str, experiment_goal: str) -> dict:
    """
    Validate and then submit one experiment to Litmus.
    Returns the Litmus response with experiment_id, status, estimated_cost_usd,
    estimated_turnaround_days.
    Raises RuntimeError on validation failure or httpx errors.
    """
    payload = _build_intake(hypothesis, experiment_name, experiment_goal)

    with httpx.Client(timeout=LITMUS_TIMEOUT) as client:
        # Step 1 — validate first
        val_resp = client.post(
            f"{LITMUS_BASE_URL}/validate",
            json=payload,
            headers=_headers(),
        )
        val_resp.raise_for_status()
        val = val_resp.json()
        if not val.get("valid", True):
            errors = "; ".join(e.get("message", str(e)) for e in val.get("errors", []))
            raise RuntimeError(f"Litmus validation failed: {errors}")

        # Step 2 — submit
        sub_resp = client.post(
            f"{LITMUS_BASE_URL}/experiments",
            json=payload,
            headers=_headers(),
        )
        sub_resp.raise_for_status()
        return sub_resp.json()
