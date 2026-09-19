"""FastAPI surface for the Supervisor agent, plus the static dashboard.

API routes live under /api/* so the dashboard can be mounted at the root
path without any route-collision ambiguity.
"""
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.database import init_schema, get_conn
from app.models import Decision, DecisionRequest
from app.agents import supervisor

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("bankmind")


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_schema()
    yield


app = FastAPI(
    title="bankmind-agent",
    description="Agentic AI banking supervisor — Phase 1",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


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
        # Expected, actionable errors (missing API key, unknown provider) —
        # the message itself is the fix instruction, safe to show as-is.
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        # Anything else (a provider SDK error, a malformed response, etc.)
        # — log the full traceback server-side for debugging, but still
        # hand the client a real message instead of a blank 500. Previously
        # this surfaced as an opaque "Request failed (500)" with nothing to
        # go on.
        logger.exception("Unhandled error in /api/decide for customer_id=%s", req.customer_id)
        raise HTTPException(status_code=500, detail=f"{type(e).__name__}: {e}")


_FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend"
if _FRONTEND_DIR.exists():
    app.mount("/", StaticFiles(directory=str(_FRONTEND_DIR), html=True), name="dashboard")
