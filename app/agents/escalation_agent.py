"""Handles anything outside agent authority.

Creates a tracked case in the Human-in-the-Loop (HITL) escalation queue
for relationship managers/underwriters, and logs an immutable audit entry.
"""
import datetime
import json

from app import database as db


def escalate(customer_id: str, request_type: str, reasons: list[str],
             context: dict) -> dict:
    now = datetime.datetime.now().isoformat()
    requested_value = context.get("requested_value") or context.get("requested_rate") or context.get("amount")

    # 1. Create a persistent case in the underwriter escalation queue
    case = db.create_escalation_case(
        customer_id=customer_id,
        request_type=request_type,
        reasons=reasons,
        context=context,
        requested_value=float(requested_value) if requested_value is not None else None,
    )

    # 2. Record in cryptographically chained audit ledger
    details = {
        "case_id": case["case_id"],
        "reasons": reasons,
        "context": context,
    }
    record = db.record_action(customer_id, f"escalation:{request_type}", json.dumps(details), now, "escalated")

    return {
        "status": "escalated",
        "case_id": case["case_id"],
        "reasons": reasons,
        "record_id": record["id"],
        "record_hash": record["record_hash"][:16] + "...",
        "handoff_packet": {
            "case_id": case["case_id"],
            "customer_id": customer_id,
            "request_type": request_type,
            "status": "pending_human_review",
            "sla": "Within 2 business hours",
            "context": context,
            "escalated_at": now,
        },
    }
