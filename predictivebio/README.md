# PredictiveBio

Scientific planning compiler: hypothesis → structured hypothesis → evidence map → risk-aware runnable experiment plan.

See `docs/product_spec.md` and `docs/agent_contracts.md`. Minimal scaffold — agent bodies are stubs.

## Quick start

```bash
make install
make api    # :8000
make web    # :3000  (separate terminal)
```

## Layout

- `services/api/` — FastAPI routes
- `agents/` — pipeline agents (intake → lit_qc → protocol → evidence → plan → risk → budget → timeline → validation → review)
- `core/schemas/` — Pydantic domain models
- `tools/` — external integrations (PubMed, Semantic Scholar, protocols.io, Tavily, suppliers)
- `apps/web/` — Next.js frontend
- `db/` — SQLAlchemy models + migrations
- `prompts/agents/` — per-agent prompt templates
- `evals/` — benchmark inputs, rubrics, regression tests
