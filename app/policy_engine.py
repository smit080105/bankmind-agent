"""Deterministic policy engine.

This module is the one place in the whole system that computes numeric
bounds and hard yes/no eligibility. The LLM-driven agents are only ever
allowed to choose *within* what this module returns — they never invent a
rate, waiver amount, or limit increase themselves. This is what makes the
system audit-safe for a banking context: every number in a final decision
traces back to a YAML rule and a database fact, not a model guess.
"""
import datetime
import functools
from pathlib import Path
from typing import Any

import yaml

from app.config import POLICY_DIR
from app import database as db


@functools.lru_cache(maxsize=None)
def _load_policy(name: str) -> dict:
    path = Path(POLICY_DIR) / f"{name}.yaml"
    with open(path, "r") as f:
        return yaml.safe_load(f)


def _credit_band(credit_score: int) -> str:
    if credit_score >= 750:
        return "excellent"
    if credit_score >= 700:
        return "good"
    if credit_score >= 650:
        return "fair"
    return "poor"


def _years_with_bank(relationship_start_date: str) -> float:
    start = datetime.date.fromisoformat(relationship_start_date)
    return (datetime.date.today() - start).days / 365.25


# ---------------------------------------------------------------------------
# Loan rate negotiation
# ---------------------------------------------------------------------------

def evaluate_loan_negotiation(customer: dict, loan: dict | None,
                               requested_rate: float | None) -> dict[str, Any]:
    """Returns a dict describing the allowed rate range, or an escalation reason."""
    policy = _load_policy("loan_negotiation")

    band = _credit_band(customer["credit_score"])
    base_rate = policy["base_rate_by_credit_band"][band]
    tier_bps = policy["max_discount_bps_by_tier"][customer["tier"]]

    years = _years_with_bank(customer["relationship_start_date"])
    loyalty_bps = 0
    if years >= 10:
        loyalty_bps = policy["loyalty_bonus_bps"]["years_10_plus"]
    elif years >= 5:
        loyalty_bps = policy["loyalty_bonus_bps"]["years_5_plus"]

    max_discount_bps = min(
        tier_bps + loyalty_bps,
        policy["max_discount_bps_absolute_floor"],
    )
    floor_rate = round(base_rate - (max_discount_bps / 100), 3)

    escalation_reasons = []
    if customer["credit_score"] < policy["escalation_required_if"][1]["customer_credit_score_below"]:
        escalation_reasons.append(
            f"Credit score {customer['credit_score']} is below the {policy['escalation_required_if'][1]['customer_credit_score_below']} floor for agent-level negotiation."
        )
    if customer.get("has_active_delinquency"):
        escalation_reasons.append("Customer has an active delinquency on file.")
    if loan and loan["principal"] > policy["escalation_required_if"][3]["loan_amount_exceeds"]:
        escalation_reasons.append(
            f"Loan principal {loan['principal']} exceeds the standard underwriting threshold."
        )

    requested_discount_bps = None
    if requested_rate is not None:
        requested_discount_bps = round((base_rate - requested_rate) * 100)
        if requested_discount_bps > policy["escalation_required_if"][0]["requested_discount_bps_exceeds"]:
            escalation_reasons.append(
                f"Requested discount of {requested_discount_bps} bps exceeds the "
                f"{policy['escalation_required_if'][0]['requested_discount_bps_exceeds']} bps hard cap."
            )

    return {
        "credit_band": band,
        "base_rate": base_rate,
        "max_discount_bps": max_discount_bps,
        "floor_rate": floor_rate,
        "years_with_bank": round(years, 1),
        "loyalty_bps_applied": loyalty_bps,
        "requested_rate": requested_rate,
        "requested_discount_bps": requested_discount_bps,
        "within_agent_authority": len(escalation_reasons) == 0,
        "escalation_reasons": escalation_reasons,
    }


# ---------------------------------------------------------------------------
# Fee waiver
# ---------------------------------------------------------------------------

def evaluate_fee_waiver(customer: dict, fee_type: str, amount: float) -> dict[str, Any]:
    policy = _load_policy("fee_waiver")
    tier = customer["tier"]
    year = str(datetime.date.today().year)

    annual_limit = policy["max_waivers_per_year_by_tier"][tier]
    max_amount = policy["max_single_waiver_amount_by_tier"][tier]

    used_this_year = db.get_fee_waiver_count_this_year(customer["customer_id"], fee_type, year)
    is_first_ever = not db.has_ever_waived(customer["customer_id"], fee_type)

    escalation_reasons = []
    within_annual_limit = used_this_year < annual_limit
    goodwill_eligible = is_first_ever and amount <= max_amount

    if amount > max_amount:
        escalation_reasons.append(
            f"Requested waiver amount {amount} exceeds the {tier} tier cap of {max_amount}."
        )
    if not within_annual_limit and not goodwill_eligible:
        escalation_reasons.append(
            f"Customer has already used {used_this_year}/{annual_limit} waivers this year "
            f"for {fee_type} and this is not a first-time goodwill case."
        )
    if customer["account_status"] not in ("active", "good_standing"):
        escalation_reasons.append(f"Account status '{customer['account_status']}' requires review.")

    return {
        "tier": tier,
        "annual_limit": annual_limit,
        "used_this_year": used_this_year,
        "max_single_amount": max_amount,
        "is_first_ever_waiver_of_type": is_first_ever,
        "goodwill_eligible": goodwill_eligible,
        "within_agent_authority": len(escalation_reasons) == 0,
        "escalation_reasons": escalation_reasons,
    }


# ---------------------------------------------------------------------------
# Credit limit / overdraft increase
# ---------------------------------------------------------------------------

def evaluate_credit_limit_increase(customer: dict, account: dict,
                                    requested_increase_pct: float,
                                    is_temporary: bool) -> dict[str, Any]:
    policy = _load_policy("credit_limit")
    tier = customer["tier"]
    elig = policy["eligibility_requirements"]

    account_age_months = _account_age_months(account["opened_date"])
    max_pct = (policy["max_temp_increase_pct_by_tier"][tier] if is_temporary
               else policy["max_permanent_increase_pct_by_tier"][tier])

    escalation_reasons = []
    if account_age_months < elig["min_account_age_months"]:
        escalation_reasons.append(
            f"Account is {account_age_months} months old; minimum is {elig['min_account_age_months']}."
        )
    if customer["credit_score"] < elig["min_credit_score"]:
        escalation_reasons.append(
            f"Credit score {customer['credit_score']} is below minimum {elig['min_credit_score']}."
        )
    if (account.get("current_utilization_pct") or 0) > elig["max_current_utilization_pct"]:
        escalation_reasons.append(
            f"Utilization {account.get('current_utilization_pct')}% exceeds max {elig['max_current_utilization_pct']}%."
        )
    if account.get("missed_payments_last_6mo", 0) > 0:
        escalation_reasons.append("Customer has missed payments in the last 6 months.")
    if customer.get("has_active_delinquency"):
        escalation_reasons.append("Customer has an active delinquency on file.")
    if requested_increase_pct > max_pct:
        escalation_reasons.append(
            f"Requested increase {requested_increase_pct}% exceeds the {tier} tier max of {max_pct}% "
            f"({'temporary' if is_temporary else 'permanent'})."
        )

    return {
        "tier": tier,
        "account_age_months": account_age_months,
        "max_allowed_pct": max_pct,
        "requested_increase_pct": requested_increase_pct,
        "is_temporary": is_temporary,
        "within_agent_authority": len(escalation_reasons) == 0,
        "escalation_reasons": escalation_reasons,
    }


def _account_age_months(opened_date: str) -> int:
    opened = datetime.date.fromisoformat(opened_date)
    today = datetime.date.today()
    return (today.year - opened.year) * 12 + (today.month - opened.month)
