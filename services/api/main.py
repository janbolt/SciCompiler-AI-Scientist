from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from services.api.routes import demo, projects, plans

app = FastAPI(title="PredictiveBio API")
app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"],
)

app.include_router(demo.router)
app.include_router(projects.router)
app.include_router(plans.router)


@app.get("/health")
async def health():
    return {"ok": True}
