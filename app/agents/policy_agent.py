"""Validates a proposed action against the deterministic policy engine and
attaches the relevant policy text (via RAG) so the final decision can cite
*why*, not just *what*."""
from app import policy_engine as pe
from app import rag


def check_loan_negotiation(customer: dict, loan: dict | None, requested_rate: float | None) -> dict:
    evaluation = pe.evaluate_loan_negotiation(customer, loan, requested_rate)
    context = rag.retrieve_policy_context(
        "loan rate negotiation discount escalation competitor match",
        source_filter="loan_negotiation",
    )
    evaluation["policy_context"] = rag.format_context_for_prompt(context)
    evaluation["citations"] = [f"{c.source}.md — {c.heading}" for c in context]
    return evaluation


def check_fee_waiver(customer: dict, fee_type: str, amount: float) -> dict:
    evaluation = pe.evaluate_fee_waiver(customer, fee_type, amount)
    context = rag.retrieve_policy_context(
        f"fee waiver {fee_type} annual limit goodwill",
        source_filter="fee_waiver",
    )
    evaluation["policy_context"] = rag.format_context_for_prompt(context)
    evaluation["citations"] = [f"{c.source}.md — {c.heading}" for c in context]
    return evaluation


def check_credit_limit_increase(customer: dict, account: dict,
                                 requested_increase_pct: float, is_temporary: bool) -> dict:
    evaluation = pe.evaluate_credit_limit_increase(
        customer, account, requested_increase_pct, is_temporary
    )
    context = rag.retrieve_policy_context(
        "credit limit increase eligibility utilization escalation",
        source_filter="credit_limit",
    )
    evaluation["policy_context"] = rag.format_context_for_prompt(context)
    evaluation["citations"] = [f"{c.source}.md — {c.heading}" for c in context]
    return evaluation
