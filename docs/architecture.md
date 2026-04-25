# Architecture

- FastAPI backend (`services/api`)
- Next.js frontend (`apps/web`)
- Pipeline: intake → lit_qc → protocol_retrieval → evidence → plan(draft) → risk → plan(revise) → budget → timeline → validation
- Risk runs **before** final assembly and must mutate the plan, not annotate it.
