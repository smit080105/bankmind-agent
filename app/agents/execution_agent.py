"""Executes an approved action.

Performs:
1. Immutable cryptographic audit ledger append (with SHA-256 hash chaining).
2. Double-entry General Ledger balancing (debits == credits).
3. Updates customer records (fee waiver history).
"""
import datetime
import json
import uuid

from app import database as db
from app.accounting import ledger


def execute_loan_rate_change(customer_id: str, loan_id: str | None, new_rate: float) -> dict:
    now = datetime.datetime.now().isoformat()
    details = {"loan_id": loan_id, "new_rate": new_rate}
    record = db.record_action(customer_id, "loan_rate_change", json.dumps(details), now, "executed")
    return {
        "status": "executed",
        "action": "loan_rate_change",
        "record_id": record["id"],
        "record_hash": record["record_hash"][:16] + "...",
        **details,
    }


def execute_fee_waiver(customer_id: str, fee_type: str, amount: float) -> dict:
    now = datetime.datetime.now().isoformat()
    today = datetime.date.today().isoformat()
    tx_id = f"TX-WAIVER-{uuid.uuid4().hex[:8].upper()}"

    # 1. Update customer fee waiver tracking
    db.record_fee_waiver(customer_id, fee_type, amount, today)

    # 2. Post balanced double-entry accounting journal
    journal_entry = ledger.create_fee_waiver_entry(tx_id, customer_id, fee_type, amount)
    db.record_general_ledger_entry(tx_id, journal_entry.lines, journal_entry.description, now)

    # 3. Log to cryptographically chained audit ledger
    details = {
        "fee_type": fee_type,
        "amount": amount,
        "transaction_id": tx_id,
        "accounting": [
            {"account": l.account, "debit": l.debit, "credit": l.credit} for l in journal_entry.lines
        ],
    }
    record = db.record_action(customer_id, "fee_waiver", json.dumps(details), now, "executed")

    return {
        "status": "executed",
        "action": "fee_waiver",
        "transaction_id": tx_id,
        "record_id": record["id"],
        "record_hash": record["record_hash"][:16] + "...",
        "fee_type": fee_type,
        "amount": amount,
    }


def execute_credit_limit_change(customer_id: str, account_id: str | None,
                                 new_limit: float, is_temporary: bool) -> dict:
    now = datetime.datetime.now().isoformat()
    details = {"account_id": account_id, "new_limit": new_limit, "is_temporary": is_temporary}
    record = db.record_action(customer_id, "credit_limit_change", json.dumps(details), now, "executed")
    return {
        "status": "executed",
        "action": "credit_limit_change",
        "record_id": record["id"],
        "record_hash": record["record_hash"][:16] + "...",
        **details,
    }


def execute_retention_credit(customer_id: str, credit_amount: float) -> dict:
    now = datetime.datetime.now().isoformat()
    tx_id = f"TX-RETENTION-{uuid.uuid4().hex[:8].upper()}"

    # 1. Post balanced double-entry accounting journal
    journal_entry = ledger.create_retention_credit_entry(tx_id, customer_id, credit_amount)
    db.record_general_ledger_entry(tx_id, journal_entry.lines, journal_entry.description, now)

    # 2. Log to cryptographically chained audit ledger
    details = {
        "credit_amount": credit_amount,
        "transaction_id": tx_id,
        "accounting": [
            {"account": l.account, "debit": l.debit, "credit": l.credit} for l in journal_entry.lines
        ],
    }
    record = db.record_action(customer_id, "retention_credit", json.dumps(details), now, "executed")

    return {
        "status": "executed",
        "action": "retention_credit",
        "transaction_id": tx_id,
        "record_id": record["id"],
        "record_hash": record["record_hash"][:16] + "...",
        "credit_amount": credit_amount,
    }
