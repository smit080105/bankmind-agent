"""FastAPI surface for the Supervisor agent."""
from fastapi import FastAPI, HTTPException

from app.database import init_schema
from app.models import Decision, DecisionRequest
from app.agents import supervisor

app = FastAPI(
    title="bankmind-agent",
    description="Agentic AI banking supervisor — Phase 1",
    version="0.1.0",
)


@app.on_event("startup")
def _startup():
    init_schema()


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/decide", response_model=Decision)
def decide(req: DecisionRequest):
    try:
        return supervisor.handle_request(req)
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))
