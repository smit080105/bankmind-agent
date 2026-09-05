"""SQLite data layer for mock customer data.

Phase 1 uses SQLite so the whole project runs with zero external infra.
The query functions below are the only surface the agents touch — swapping
SQLite for Postgres later (as in the IoT dashboard project) means rewriting
this file only, not the agent code.
"""
import sqlite3
from contextlib import contextmanager
from pathlib import Path

from app.config import DATABASE_PATH

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
    outcome TEXT NOT NULL            -- executed | escalated | denied
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
                   executed_on: str, outcome: str):
    with get_conn() as conn:
        conn.execute(
            """INSERT INTO action_ledger
               (customer_id, action_type, details, executed_on, outcome)
               VALUES (?, ?, ?, ?, ?)""",
            (customer_id, action_type, details_json, executed_on, outcome),
        )
