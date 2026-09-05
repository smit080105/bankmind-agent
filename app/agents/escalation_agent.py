"""Handles anything outside agent authority.

Phase 1 logs the escalation to the same ledger with outcome='escalated' and
returns a structured handoff packet. A later phase routes this into a real
queue for a human relationship manager / underwriter.
"""
import datetime
import json

from app import database as db


def escalate(customer_id: str, request_type: str, reasons: list[str],
             context: dict) -> dict:
    now = datetime.datetime.now().isoformat()
    details = {"reasons": reasons, "context": context}
    db.record_action(customer_id, f"escalation:{request_type}", json.dumps(details), now, "escalated")
    return {
        "status": "escalated",
        "reasons": reasons,
        "handoff_packet": {
            "customer_id": customer_id,
            "request_type": request_type,
            "context": context,
            "escalated_at": now,
        },
    }
