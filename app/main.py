"""FastAPI surface for the Supervisor agent, HITL escalation management,
cryptographic audit verification, and double-entry accounting.

API routes live under /api/* so the dashboard can be mounted at the root
path without any route-collision ambiguity.
"""
import hashlib
import json
import logging
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException, Header, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.database import (
    init_schema,
    get_conn,
    get_escalations,
    get_escalation_by_id,
    resolve_escalation,
    get_action_ledger,
    get_general_ledger_entries,
    get_idempotency_record,
    save_idempotency_record,
)
from app.models import (
    Decision,
    DecisionRequest,
    EscalationReviewRequest,
    AuditVerificationResponse,
)
from app.agents import supervisor, execution_agent
from app.security import audit

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("bankmind")


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_schema()
    yield


app = FastAPI(
    title="bankmind-agent",
    description="Agentic AI banking supervisor — Enterprise Phase 3 with HITL and Cryptographic Audit",
    version="0.3.0",
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
    """Lightweight customer list for the dashboard's picker."""
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT customer_id, full_name, tier FROM customers ORDER BY full_name"
        ).fetchall()
        return [dict(r) for r in rows]


@app.post("/api/decide", response_model=Decision)
def decide(req: DecisionRequest, response: Response, idempotency_key: Optional[str] = Header(None)):
    # 1. Check idempotency key if provided
    request_hash = ""
    if idempotency_key:
        request_hash = hashlib.sha256(req.model_dump_json().encode("utf-8")).hexdigest()
        cached = get_idempotency_record(idempotency_key)
        if cached:
            response.headers["X-Cache-Hit"] = "true"
            return Decision.model_validate_json(cached["response_body"])

    # 2. Execute decision via supervisor
    try:
        decision = supervisor.handle_request(req)
        # 3. Store idempotency record if requested
        if idempotency_key:
            save_idempotency_record(idempotency_key, request_hash, decision.model_dump_json())
        return decision
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        logger.exception("Unhandled error in /api/decide for customer_id=%s", req.customer_id)
        raise HTTPException(status_code=500, detail=f"{type(e).__name__}: {e}")


# ---------------------------------------------------------------------------
# Human-in-the-Loop (HITL) Escalation Management Endpoints
# ---------------------------------------------------------------------------

@app.get("/api/escalations")
def list_escalations(status: Optional[str] = None):
    """Lists escalations for relationship managers and underwriters."""
    return get_escalations(status=status)


@app.get("/api/escalations/{case_id}")
def get_escalation(case_id: str):
    """Retrieves full case context for a specific escalation."""
    case = get_escalation_by_id(case_id)
    if not case:
        raise HTTPException(status_code=404, detail=f"Escalation case '{case_id}' not found.")
    return case


@app.post("/api/escalations/{case_id}/review")
def review_escalation(case_id: str, review: EscalationReviewRequest):
    """Allows a human underwriter or relationship manager to Approve, Reject,
    or Override an escalated case, executing terms and logging cryptographic audit records.
    """
    case = get_escalation_by_id(case_id)
    if not case:
        raise HTTPException(status_code=404, detail=f"Escalation case '{case_id}' not found.")

    if case["status"] != "pending":
        raise HTTPException(
            status_code=400,
            detail=f"Case '{case_id}' has already been reviewed with status '{case['status']}'."
        )

    # Resolve escalation state in DB
    updated = resolve_escalation(
        case_id=case_id,
        reviewer_decision=review.decision,
        reviewer_notes=review.reviewer_notes,
        overridden_terms=review.overridden_terms,
    )

    # If approved or overridden, execute corresponding action
    execution_result = None
    customer_id = case["customer_id"]
    req_type = case["request_type"]
    context = case["context"]
    terms = review.overridden_terms or {}

    if review.decision in ("approve", "override"):
        if req_type == "loan_rate_negotiation":
            new_rate = terms.get("new_rate", case.get("requested_value") or context.get("requested_rate"))
            loan_id = context.get("loan_id")
            if new_rate is not None:
                execution_result = execution_agent.execute_loan_rate_change(
                    customer_id, loan_id, float(new_rate)
                )

        elif req_type == "fee_waiver":
            fee_type = context.get("fee_type", "general")
            amount = terms.get("waived_amount", case.get("requested_value") or context.get("amount", 0.0))
            execution_result = execution_agent.execute_fee_waiver(customer_id, fee_type, float(amount))

        elif req_type == "credit_limit_increase":
            account_id = context.get("account_id")
            new_limit = terms.get("new_limit", 50000.0)
            is_temp = context.get("is_temporary", False)
            execution_result = execution_agent.execute_credit_limit_change(
                customer_id, account_id, float(new_limit), is_temp
            )

        elif req_type == "retention_offer":
            credit_amount = terms.get("credit_amount", case.get("requested_value") or 1000.0)
            execution_result = execution_agent.execute_retention_credit(customer_id, float(credit_amount))

    return {
        "case": updated,
        "execution": execution_result,
        "message": f"Case {case_id} successfully {review.decision}d by reviewer.",
    }


# ---------------------------------------------------------------------------
# Cryptographic Audit and Accounting Endpoints
# ---------------------------------------------------------------------------

@app.get("/api/audit/verify", response_model=AuditVerificationResponse)
def verify_audit():
    """Mathematically verifies the SHA-256 hash chain of the entire audit ledger."""
    records = get_action_ledger(limit=1000)
    is_valid, msg, broken_id = audit.verify_chain(records)
    return AuditVerificationResponse(
        valid=is_valid,
        message=msg,
        total_records=len(records),
        broken_at_id=broken_id,
    )


@app.get("/api/audit/ledger")
def view_audit_ledger(limit: int = 50):
    """Returns raw cryptographically chained action records."""
    return get_action_ledger(limit=limit)


@app.get("/api/accounting/ledger")
def view_general_ledger(transaction_id: Optional[str] = None):
    """Returns balanced double-entry General Ledger journal records."""
    return get_general_ledger_entries(tx_id=transaction_id)


_FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend"
if _FRONTEND_DIR.exists():
    app.mount("/", StaticFiles(directory=str(_FRONTEND_DIR), html=True), name="dashboard")
