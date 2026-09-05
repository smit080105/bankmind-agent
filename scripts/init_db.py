"""Initializes the SQLite schema and seeds a handful of realistic mock
customers covering the different policy paths (clean approval, goodwill
waiver, and hard escalation) so Phase 1 can be tested end-to-end.

Usage: python scripts/init_db.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.database import init_schema, get_conn  # noqa: E402


CUSTOMERS = [
    # customer_id, full_name, tier, credit_score, account_status,
    # relationship_start_date, has_active_delinquency
    ("CUST1001", "Ananya Rao", "gold", 742, "active", "2018-03-12", 0),
    ("CUST1002", "Devansh Mehta", "platinum", 781, "active", "2011-07-01", 0),
    ("CUST1003", "Priya Nair", "standard", 601, "active", "2023-01-20", 0),
    ("CUST1004", "Rohan Kulkarni", "silver", 655, "active", "delinquent-flag", 1),
    ("CUST1005", "Kabir Shah", "gold", 710, "good_standing", "2016-09-05", 0),
]

# Fix Rohan's relationship_start_date typo above (placeholder replaced below)
CUSTOMERS[3] = ("CUST1004", "Rohan Kulkarni", "silver", 655, "active", "2015-05-10", 1)

ACCOUNTS = [
    # account_id, customer_id, account_type, balance, credit_limit,
    # current_utilization_pct, opened_date, missed_payments_last_6mo
    ("ACC2001", "CUST1001", "credit_card", 12500.0, 150000.0, 42.0, "2018-04-01", 0),
    ("ACC2002", "CUST1002", "credit_card", 5400.0, 500000.0, 15.0, "2011-08-01", 0),
    ("ACC2003", "CUST1003", "checking", 8200.0, None, None, "2023-01-25", 0),
    ("ACC2004", "CUST1004", "credit_card", 42000.0, 100000.0, 88.0, "2015-06-01", 2),
    ("ACC2005", "CUST1005", "credit_card", 9000.0, 200000.0, 30.0, "2016-10-01", 0),
]

LOANS = [
    # loan_id, customer_id, loan_type, principal, current_rate, origination_date, status
    ("LOAN3001", "CUST1001", "personal", 500000.0, 11.0, "2022-02-15", "active"),
    ("LOAN3002", "CUST1002", "auto", 1200000.0, 9.5, "2023-06-01", "active"),
    ("LOAN3003", "CUST1005", "personal", 300000.0, 11.0, "2021-11-10", "active"),
]


def main():
    init_schema()
    with get_conn() as conn:
        conn.executemany(
            """INSERT OR REPLACE INTO customers
               (customer_id, full_name, tier, credit_score, account_status,
                relationship_start_date, has_active_delinquency)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            CUSTOMERS,
        )
        conn.executemany(
            """INSERT OR REPLACE INTO accounts
               (account_id, customer_id, account_type, balance, credit_limit,
                current_utilization_pct, opened_date, missed_payments_last_6mo)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            ACCOUNTS,
        )
        conn.executemany(
            """INSERT OR REPLACE INTO loans
               (loan_id, customer_id, loan_type, principal, current_rate,
                origination_date, status)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            LOANS,
        )
    print(f"Seeded {len(CUSTOMERS)} customers, {len(ACCOUNTS)} accounts, {len(LOANS)} loans.")
    print("Try customer IDs: " + ", ".join(c[0] for c in CUSTOMERS))


if __name__ == "__main__":
    main()
