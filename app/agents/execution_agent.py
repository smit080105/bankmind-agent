"""Executes an approved action.

Phase 1 has no real core-banking connector, so "executing" means writing an
immutable ledger entry (and, for fee waivers, updating waiver history so
future policy checks see it). This keeps the interface identical to what a
real core-banking call will look like in a later phase.
"""
import datetime
import json

from app import database as db


def execute_loan_rate_change(customer_id: str, loan_id: str | None, new_rate: float) -> dict:
    now = datetime.datetime.now().isoformat()
    details = {"loan_id": loan_id, "new_rate": new_rate}
    db.record_action(customer_id, "loan_rate_change", json.dumps(details), now, "executed")
    return {"status": "executed", "action": "loan_rate_change", **details}


def execute_fee_waiver(customer_id: str, fee_type: str, amount: float) -> dict:
    now = datetime.datetime.now().isoformat()
    today = datetime.date.today().isoformat()
    db.record_fee_waiver(customer_id, fee_type, amount, today)
    details = {"fee_type": fee_type, "amount": amount}
    db.record_action(customer_id, "fee_waiver", json.dumps(details), now, "executed")
    return {"status": "executed", "action": "fee_waiver", **details}


def execute_credit_limit_change(customer_id: str, account_id: str | None,
                                 new_limit: float, is_temporary: bool) -> dict:
    now = datetime.datetime.now().isoformat()
    details = {"account_id": account_id, "new_limit": new_limit, "is_temporary": is_temporary}
    db.record_action(customer_id, "credit_limit_change", json.dumps(details), now, "executed")
    return {"status": "executed", "action": "credit_limit_change", **details}
