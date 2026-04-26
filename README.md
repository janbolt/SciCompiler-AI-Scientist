# SciCompiler Vertical Demo

Runnable vertical demo for AI-assisted experiment planning.

## Structure

- `backend`: FastAPI + Pydantic + pytest
- `frontend`: Next.js + TypeScript

You need **Node.js 18+** (includes `npm`) for the frontend.

---

## Run backend

From the **repository root** (recommended, one venv for backend + tests):

```bash
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e "./backend[dev]"
uvicorn app.main:app --reload --port 8000 --app-dir backend
```

Health check: open [http://localhost:8000/health](http://localhost:8000/health).

**Alternative** (venv inside `backend/`):

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
uvicorn app.main:app --reload --port 8000
```

---

## Run frontend

In a **second terminal**, from the repository root:

```bash
cd frontend
npm install
NEXT_PUBLIC_API_BASE_URL=http://localhost:8000 npm run dev
```

Open [http://localhost:3000](http://localhost:3000).

If the UI cannot reach the API, confirm the backend is on port 8000 and that `NEXT_PUBLIC_API_BASE_URL` matches (or omit it; it defaults to `http://localhost:8000`).

---

## Run tests

From the repository root with the same venv activated:

```bash
source .venv/bin/activate
pytest -q backend/tests
```

Or from `backend/` with a venv created there:

```bash
cd backend && source .venv/bin/activate && pytest -q
```
