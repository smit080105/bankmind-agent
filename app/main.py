"""FastAPI surface for the Supervisor agent, plus the static dashboard.

API routes live under /api/* so the dashboard can be mounted at the root
path without any route-collision ambiguity.
"""
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.database import init_schema, get_conn
from app.models import Decision, DecisionRequest
from app.agents import supervisor

app = FastAPI(
    title="bankmind-agent",
    description="Agentic AI banking supervisor — Phase 1",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def _startup():
    init_schema()


@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.get("/api/customers")
def list_customers():
    """Lightweight customer list for the dashboard's picker — not a full
    profile fetch, just enough to populate a dropdown."""
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT customer_id, full_name, tier FROM customers ORDER BY full_name"
        ).fetchall()
        return [dict(r) for r in rows]


@app.post("/api/decide", response_model=Decision)
def decide(req: DecisionRequest):
    try:
        return supervisor.handle_request(req)
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))


_FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend"
if _FRONTEND_DIR.exists():
    app.mount("/", StaticFiles(directory=str(_FRONTEND_DIR), html=True), name="dashboard")
