RESTRICTED_DOMAINS = [
    "pathogen_work", "human_subjects", "animal_experiments",
    "ecological_gene_release", "toxin_production", "clinical_claims",
    "hazardous_synthesis", "unverified_regulatory_claims",
]


def classify(text: str) -> list[str]:
    """Stub. Return list of triggered restricted domains."""
    return []


def should_block_execution(triggered: list[str]) -> bool:
    return bool(triggered)
