"""Europe PMC search (covers PubMed + bioRxiv preprints; no API key)."""
import httpx

ENDPOINT = "https://www.ebi.ac.uk/europepmc/webservices/rest/search"


async def search(query: str, limit: int = 5, sources: str | None = None) -> list[dict]:
    q = query if not sources else f"({query}) AND SRC:{sources}"
    async with httpx.AsyncClient(timeout=20.0) as client:
        r = await client.get(ENDPOINT, params={
            "query": q, "format": "json", "pageSize": limit, "resultType": "core",
        })
        r.raise_for_status()
        items = r.json().get("resultList", {}).get("result", [])
    out = []
    for x in items:
        doi = x.get("doi")
        pmid = x.get("pmid")
        url = f"https://doi.org/{doi}" if doi else (f"https://europepmc.org/article/MED/{pmid}" if pmid else None)
        out.append({
            "id": str(x.get("id") or doi or pmid),
            "title": x.get("title", "").strip("."),
            "authors": [a.get("fullName", "") for a in (x.get("authorList", {}) or {}).get("author", [])][:4],
            "year": int(x["pubYear"]) if x.get("pubYear") else None,
            "doi": doi,
            "url": url,
            "source": x.get("source") or ("bioRxiv" if (x.get("bookOrReportDetails") or "").lower() == "preprint" else "PMC"),
            "abstract": (x.get("abstractText") or "")[:1200],
        })
    return out
