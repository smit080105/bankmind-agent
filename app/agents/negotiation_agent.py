"""Computes a concrete, policy-compliant offer.

Deliberately dumb and deterministic: given the policy engine's bounds, pick
the best offer that still satisfies the customer's ask where possible. The
Supervisor's LLM call is responsible for *phrasing* this to the customer and
deciding whether to present it — it does not compute the number itself.
"""


def negotiate_loan_rate(evaluation: dict) -> dict:
    """evaluation comes from policy_agent.check_loan_negotiation."""
    if not evaluation["within_agent_authority"]:
        return {"offer_possible": False, "reason": "; ".join(evaluation["escalation_reasons"])}

    floor_rate = evaluation["floor_rate"]
    requested_rate = evaluation.get("requested_rate")

    if requested_rate is not None and requested_rate >= floor_rate:
        # Customer's ask is within what we're allowed to give — give it to them.
        offered_rate = requested_rate
    else:
        # Either no explicit ask, or ask is outside bounds (already caught above
        # if it required escalation) — offer the best rate we can.
        offered_rate = floor_rate

    return {
        "offer_possible": True,
        "offered_rate": round(offered_rate, 3),
        "base_rate": evaluation["base_rate"],
        "discount_bps_used": round((evaluation["base_rate"] - offered_rate) * 100),
        "max_discount_bps_available": evaluation["max_discount_bps"],
    }


def negotiate_fee_waiver(evaluation: dict, requested_amount: float) -> dict:
    if not evaluation["within_agent_authority"]:
        return {"offer_possible": False, "reason": "; ".join(evaluation["escalation_reasons"])}

    cap = evaluation["max_single_amount"]
    waived_amount = min(requested_amount, cap)
    return {
        "offer_possible": True,
        "waived_amount": waived_amount,
        "is_goodwill": evaluation["goodwill_eligible"] and evaluation["used_this_year"] >= evaluation["annual_limit"],
        "remaining_annual_waivers": max(evaluation["annual_limit"] - evaluation["used_this_year"] - 1, 0),
    }


def negotiate_credit_limit(evaluation: dict, current_limit: float) -> dict:
    if not evaluation["within_agent_authority"]:
        return {"offer_possible": False, "reason": "; ".join(evaluation["escalation_reasons"])}

    requested_pct = evaluation["requested_increase_pct"]
    max_pct = evaluation["max_allowed_pct"]
    granted_pct = min(requested_pct, max_pct)
    new_limit = round(current_limit * (1 + granted_pct / 100), 2)

    return {
        "offer_possible": True,
        "granted_increase_pct": granted_pct,
        "new_limit": new_limit,
        "is_temporary": evaluation["is_temporary"],
    }


def negotiate_retention_offer(evaluation: dict) -> dict:
    if not evaluation["within_agent_authority"]:
        return {"offer_possible": False, "reason": "; ".join(evaluation["escalation_reasons"])}

    max_credit = evaluation["max_credit"]
    requested = evaluation.get("requested_credit")
    granted_credit = min(requested, max_credit) if requested is not None else max_credit

    return {
        "offer_possible": True,
        "granted_credit": round(granted_credit, 2),
        "max_credit_available": max_credit,
    }
