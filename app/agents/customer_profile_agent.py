"""Fetches and summarizes a customer's full picture for the Supervisor."""
from app import database as db


def get_customer_profile(customer_id: str) -> dict:
    customer = db.get_customer(customer_id)
    if not customer:
        return {"found": False, "customer_id": customer_id}

    accounts = db.get_accounts(customer_id)
    loans = db.get_loans(customer_id)

    return {
        "found": True,
        "customer": customer,
        "accounts": accounts,
        "loans": loans,
        "summary": _summarize(customer, accounts, loans),
    }


def _summarize(customer: dict, accounts: list[dict], loans: list[dict]) -> str:
    parts = [
        f"{customer['full_name']} ({customer['customer_id']}) — {customer['tier'].title()} tier, "
        f"credit score {customer['credit_score']}, account status: {customer['account_status']}.",
    ]
    if customer.get("has_active_delinquency"):
        parts.append("Has an ACTIVE DELINQUENCY on file.")
    if accounts:
        acc_desc = ", ".join(
            f"{a['account_type']} ({a['account_id']}, balance {a['balance']})" for a in accounts
        )
        parts.append(f"Accounts: {acc_desc}.")
    if loans:
        loan_desc = ", ".join(
            f"{l['loan_type']} loan {l['loan_id']} at {l['current_rate']}% on principal {l['principal']}"
            for l in loans
        )
        parts.append(f"Loans: {loan_desc}.")
    return " ".join(parts)
