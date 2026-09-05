"""Quick interactive CLI to exercise the Supervisor without spinning up FastAPI.

Usage: python scripts/run_cli.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.database import init_schema  # noqa: E402
from app.models import DecisionRequest, RequestType  # noqa: E402
from app.agents import supervisor  # noqa: E402

SAMPLE_REQUESTS = {
    "1": DecisionRequest(
        customer_id="CUST1001",
        request_type=RequestType.LOAN_RATE_NEGOTIATION,
        customer_message="I found a personal loan at 9.8% at another bank, can you match it?",
        requested_value=9.8,
        loan_id="LOAN3001",
    ),
    "2": DecisionRequest(
        customer_id="CUST1004",
        request_type=RequestType.LOAN_RATE_NEGOTIATION,
        customer_message="My credit card rate is too high, I want it dropped to 9%.",
        requested_value=9.0,
    ),
    "3": DecisionRequest(
        customer_id="CUST1005",
        request_type=RequestType.FEE_WAIVER,
        customer_message="I was charged a 500 rupee overdraft fee, can you waive it? First time this happens.",
        requested_value=500,
        fee_type="overdraft",
    ),
    "4": DecisionRequest(
        customer_id="CUST1002",
        request_type=RequestType.CREDIT_LIMIT_INCREASE,
        customer_message="Can I get a temporary credit limit increase of 40% for a large purchase?",
        requested_value=40,
        account_id="ACC2002",
    ),
}


def main():
    init_schema()
    print("bankmind-agent CLI — Phase 1\n")
    print("Sample requests:")
    for key, req in SAMPLE_REQUESTS.items():
        print(f"  {key}. [{req.customer_id}] {req.customer_message}")
    print()

    choice = input("Pick a sample (1-4), or press Enter to build a custom request: ").strip()

    if choice in SAMPLE_REQUESTS:
        req = SAMPLE_REQUESTS[choice]
    else:
        customer_id = input("Customer ID: ").strip()
        print("Request type: 1) loan_rate_negotiation 2) fee_waiver 3) credit_limit_increase")
        rt_choice = input("Choice: ").strip()
        rt_map = {
            "1": RequestType.LOAN_RATE_NEGOTIATION,
            "2": RequestType.FEE_WAIVER,
            "3": RequestType.CREDIT_LIMIT_INCREASE,
        }
        message = input("Customer message: ").strip()
        req = DecisionRequest(
            customer_id=customer_id,
            request_type=rt_map.get(rt_choice, RequestType.LOAN_RATE_NEGOTIATION),
            customer_message=message,
        )

    print("\nRunning Supervisor...\n")
    decision = supervisor.handle_request(req)

    print("=" * 70)
    print(f"OUTCOME: {decision.outcome.upper()}")
    print("=" * 70)
    print(f"\nReasoning:\n{decision.reasoning}\n")
    if decision.terms:
        print(f"Terms: {decision.terms}\n")
    if decision.policy_citations:
        print(f"Policy citations: {', '.join(decision.policy_citations)}\n")
    print("Reasoning trace:")
    for step in decision.trace:
        print(f"  [{step.agent}] {step.action}: {step.detail}")


if __name__ == "__main__":
    main()
