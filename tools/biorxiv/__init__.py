"""Preprint search via Europe PMC SRC:PPR filter."""
from tools import pubmed


async def search(query: str, limit: int = 3) -> list[dict]:
    hits = await pubmed.search(query, limit=limit, sources="PPR")
    for h in hits:
        h["source"] = "bioRxiv/preprint"
    return hits
