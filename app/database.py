"""SQLite data layer for customer data, cryptographic audit ledger, and general ledger.

Supports:
- Mock customer data (customers, accounts, loans, fee_waivers).
- Cryptographically chained audit ledger (SHA-256 hash chain preventing tampering).
- Double-entry General Ledger journal entries.
- Human-in-the-Loop (HITL) escalation queue for underwriters.
- Idempotency records.
"""
import datetime
import json
import sqlite3
import uuid
from contextlib import contextmanager
from pathlib import Path

from app.config import DATABASE_PATH
from app.security import audit

SCHEMA = """
CREATE TABLE IF NOT EXISTS customers (
    customer_id TEXT PRIMARY KEY,
    full_name TEXT NOT NULL,
    tier TEXT NOT NULL CHECK(tier IN ('platinum','gold','silver','standard')),
    credit_score INTEGER NOT NULL,
    account_status TEXT NOT NULL DEFAULT 'active',
    relationship_start_date TEXT NOT NULL,   -- ISO date
    has_active_delinquency INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS accounts (
    account_id TEXT PRIMARY KEY,
    customer_id TEXT NOT NULL REFERENCES customers(customer_id),
    account_type TEXT NOT NULL,      -- checking, savings, credit_card
    balance REAL NOT NULL DEFAULT 0,
    credit_limit REAL,
    current_utilization_pct REAL,
    opened_date TEXT NOT NULL,
    missed_payments_last_6mo INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS loans (
    loan_id TEXT PRIMARY KEY,
    customer_id TEXT NOT NULL REFERENCES customers(customer_id),
    loan_type TEXT NOT NULL,         -- personal, auto, mortgage
    principal REAL NOT NULL,
    current_rate REAL NOT NULL,
    origination_date TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'active'
);

CREATE TABLE IF NOT EXISTS fee_waiver_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    customer_id TEXT NOT NULL REFERENCES customers(customer_id),
    fee_type TEXT NOT NULL,
    amount REAL NOT NULL,
    waived_on TEXT NOT NULL          -- ISO date
);

CREATE TABLE IF NOT EXISTS action_ledger (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    customer_id TEXT NOT NULL,
    action_type TEXT NOT NULL,
    details TEXT NOT NULL,           -- JSON blob
    executed_on TEXT NOT NULL,       -- ISO timestamp
    outcome TEXT NOT NULL,           -- executed | escalated | denied
    prev_hash TEXT NOT NULL DEFAULT '0000000000000000000000000000000000000000000000000000000000000000',
    record_hash TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS general_ledger_entries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    transaction_id TEXT NOT NULL,
    account_name TEXT NOT NULL,
    debit REAL NOT NULL DEFAULT 0.0,
    credit REAL NOT NULL DEFAULT 0.0,
    timestamp TEXT NOT NULL,
    description TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS escalation_queue (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    case_id TEXT UNIQUE NOT NULL,
    customer_id TEXT NOT NULL,
    request_type TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending', -- pending | approved | rejected | overridden
    reasons TEXT NOT NULL,                 -- JSON array
    context TEXT NOT NULL,                 -- JSON object
    requested_value REAL,
    created_at TEXT NOT NULL,
    reviewed_at TEXT,
    reviewer_decision TEXT,
    reviewer_notes TEXT,
    overridden_terms TEXT                  -- JSON object
);

CREATE TABLE IF NOT EXISTS idempotency_keys (
    idempotency_key TEXT PRIMARY KEY,
    request_hash TEXT NOT NULL,
    response_body TEXT NOT NULL,
    created_at TEXT NOT NULL
);
"""


@contextmanager
def get_conn():
    Path(DATABASE_PATH).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_schema():
    with get_conn() as conn:
        conn.executescript(SCHEMA)
        # Handle migration if action_ledger exists without hash columns
        cols = [col["name"] for col in conn.execute("PRAGMA table_info(action_ledger)").fetchall()]
        if "prev_hash" not in cols:
            conn.execute("ALTER TABLE action_ledger ADD COLUMN prev_hash TEXT NOT NULL DEFAULT '0000000000000000000000000000000000000000000000000000000000000000'")
        if "record_hash" not in cols:
            conn.execute("ALTER TABLE action_ledger ADD COLUMN record_hash TEXT NOT NULL DEFAULT ''")


def get_customer(customer_id: str) -> dict | None:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM customers WHERE customer_id = ?", (customer_id,)
        ).fetchone()
        return dict(row) if row else None


def get_accounts(customer_id: str) -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM accounts WHERE customer_id = ?", (customer_id,)
        ).fetchall()
        return [dict(r) for r in rows]


def get_loans(customer_id: str) -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM loans WHERE customer_id = ?", (customer_id,)
        ).fetchall()
        return [dict(r) for r in rows]


def get_fee_waiver_count_this_year(customer_id: str, fee_type: str, year: str) -> int:
    with get_conn() as conn:
        row = conn.execute(
            """SELECT COUNT(*) as cnt FROM fee_waiver_history
               WHERE customer_id = ? AND fee_type = ? AND waived_on LIKE ?""",
            (customer_id, fee_type, f"{year}%"),
        ).fetchone()
        return row["cnt"] if row else 0


def has_ever_waived(customer_id: str, fee_type: str) -> bool:
    with get_conn() as conn:
        row = conn.execute(
            """SELECT COUNT(*) as cnt FROM fee_waiver_history
               WHERE customer_id = ? AND fee_type = ?""",
            (customer_id, fee_type),
        ).fetchone()
        return (row["cnt"] if row else 0) > 0


def record_fee_waiver(customer_id: str, fee_type: str, amount: float, waived_on: str):
    with get_conn() as conn:
        conn.execute(
            """INSERT INTO fee_waiver_history (customer_id, fee_type, amount, waived_on)
               VALUES (?, ?, ?, ?)""",
            (customer_id, fee_type, amount, waived_on),
        )


def record_action(customer_id: str, action_type: str, details_json: str,
                   executed_on: str, outcome: str) -> dict:
    """Records an action in the cryptographic tamper-evident audit ledger."""
    with get_conn() as conn:
        # Fetch the hash of the latest block to chain onto
        row = conn.execute("SELECT record_hash FROM action_ledger ORDER BY id DESC LIMIT 1").fetchone()
        prev_hash = row["record_hash"] if (row and row["record_hash"]) else audit.GENESIS_HASH

        record_hash = audit.compute_record_hash(
            prev_hash=prev_hash,
            customer_id=customer_id,
            action_type=action_type,
            details_json=details_json,
            executed_on=executed_on,
            outcome=outcome,
        )

        cur = conn.execute(
            """INSERT INTO action_ledger
               (customer_id, action_type, details, executed_on, outcome, prev_hash, record_hash)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (customer_id, action_type, details_json, executed_on, outcome, prev_hash, record_hash),
        )
        return {
            "id": cur.lastrowid,
            "customer_id": customer_id,
            "action_type": action_type,
            "details": details_json,
            "executed_on": executed_on,
            "outcome": outcome,
            "prev_hash": prev_hash,
            "record_hash": record_hash,
        }


def get_action_ledger(limit: int = 50) -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute("SELECT * FROM action_ledger ORDER BY id ASC LIMIT ?", (limit,)).fetchall()
        return [dict(r) for r in rows]


# ---------------------------------------------------------------------------
# Double-Entry General Ledger
# ---------------------------------------------------------------------------

def record_general_ledger_entry(tx_id: str, lines: list, description: str, timestamp: str):
    with get_conn() as conn:
        for line in lines:
            account = line.account if hasattr(line, "account") else line["account"]
            debit = line.debit if hasattr(line, "debit") else line.get("debit", 0.0)
            credit = line.credit if hasattr(line, "credit") else line.get("credit", 0.0)
            conn.execute(
                """INSERT INTO general_ledger_entries (transaction_id, account_name, debit, credit, timestamp, description)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (tx_id, account, debit, credit, timestamp, description)
            )


def get_general_ledger_entries(tx_id: str | None = None) -> list[dict]:
    with get_conn() as conn:
        if tx_id:
            rows = conn.execute("SELECT * FROM general_ledger_entries WHERE transaction_id = ? ORDER BY id ASC", (tx_id,)).fetchall()
        else:
            rows = conn.execute("SELECT * FROM general_ledger_entries ORDER BY id DESC LIMIT 100").fetchall()
        return [dict(r) for r in rows]


# ---------------------------------------------------------------------------
# Human-in-the-Loop (HITL) Escalation Queue
# ---------------------------------------------------------------------------

def create_escalation_case(customer_id: str, request_type: str, reasons: list[str],
                           context: dict, requested_value: float | None = None) -> dict:
    case_id = f"ESC-{datetime.date.today().strftime('%Y%m%d')}-{uuid.uuid4().hex[:6].upper()}"
    now = datetime.datetime.now().isoformat()
    reasons_json = json.dumps(reasons)
    context_json = json.dumps(context)
    with get_conn() as conn:
        conn.execute(
            """INSERT INTO escalation_queue
               (case_id, customer_id, request_type, status, reasons, context, requested_value, created_at)
               VALUES (?, ?, ?, 'pending', ?, ?, ?, ?)""",
            (case_id, customer_id, request_type, reasons_json, context_json, requested_value, now)
        )
    return {
        "case_id": case_id,
        "customer_id": customer_id,
        "request_type": request_type,
        "status": "pending",
        "reasons": reasons,
        "context": context,
        "requested_value": requested_value,
        "created_at": now,
    }


def get_escalations(status: str | None = None) -> list[dict]:
    with get_conn() as conn:
        if status:
            rows = conn.execute("SELECT * FROM escalation_queue WHERE status = ? ORDER BY id DESC", (status,)).fetchall()
        else:
            rows = conn.execute("SELECT * FROM escalation_queue ORDER BY id DESC").fetchall()
        result = []
        for r in rows:
            d = dict(r)
            d["reasons"] = json.loads(d["reasons"]) if d["reasons"] else []
            d["context"] = json.loads(d["context"]) if d["context"] else {}
            d["overridden_terms"] = json.loads(d["overridden_terms"]) if d.get("overridden_terms") else None
            result.append(d)
        return result


def get_escalation_by_id(case_id: str) -> dict | None:
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM escalation_queue WHERE case_id = ?", (case_id,)).fetchone()
        if not row:
            return None
        d = dict(row)
        d["reasons"] = json.loads(d["reasons"]) if d["reasons"] else []
        d["context"] = json.loads(d["context"]) if d["context"] else {}
        d["overridden_terms"] = json.loads(d["overridden_terms"]) if d.get("overridden_terms") else None
        return d


def resolve_escalation(case_id: str, reviewer_decision: str, reviewer_notes: str,
                       overridden_terms: dict | None = None) -> dict | None:
    now = datetime.datetime.now().isoformat()
    terms_json = json.dumps(overridden_terms) if overridden_terms else None
    status = "approved" if reviewer_decision == "approve" else ("overridden" if reviewer_decision == "override" else "rejected")
    with get_conn() as conn:
        conn.execute(
            """UPDATE escalation_queue
               SET status = ?, reviewer_decision = ?, reviewer_notes = ?, overridden_terms = ?, reviewed_at = ?
               WHERE case_id = ?""",
            (status, reviewer_decision, reviewer_notes, terms_json, now, case_id)
        )
    return get_escalation_by_id(case_id)


# ---------------------------------------------------------------------------
# Idempotency
# ---------------------------------------------------------------------------

def get_idempotency_record(key: str) -> dict | None:
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM idempotency_keys WHERE idempotency_key = ?", (key,)).fetchone()
        return dict(row) if row else None


def save_idempotency_record(key: str, request_hash: str, response_body: str):
    now = datetime.datetime.now().isoformat()
    with get_conn() as conn:
        conn.execute(
            """INSERT OR REPLACE INTO idempotency_keys (idempotency_key, request_hash, response_body, created_at)
               VALUES (?, ?, ?, ?)""",
            (key, request_hash, response_body, now)
        )
