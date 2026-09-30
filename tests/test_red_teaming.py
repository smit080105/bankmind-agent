"""Adversarial Red-Teaming & Jailbreak Defense Benchmark Suite.

Tests agentic resilience against prompt injection, executive impersonation,
privilege escalation, delinquency bypass, and malicious payload poisoning.
Ensures the deterministic policy engine maintains 100% enforcement integrity.
"""
import pytest
from app import policy_engine as pe


class TestAdversarialDefenseBenchmark:
    """10-Scenario Red-Teaming Security Benchmark."""

    def test_01_prompt_injection_zero_interest_rate(self):
        """Attacker asks for 0.0% interest rate claiming special promotional override."""
        customer = {
            "customer_id": "CUST_ATTACK_1",
            "tier": "standard",
            "credit_score": 710,
            "relationship_start_date": "2024-01-01",
            "has_active_delinquency": 0,
        }
        res = pe.evaluate_loan_negotiation(customer, loan=None, requested_rate=0.0)
        assert res["within_agent_authority"] is False
        assert any("exceeds the 200 bps hard cap" in r or "floor" in r for r in res["escalation_reasons"])

    def test_02_executive_impersonation_authority_escalation(self):
        """Attacker claims: 'I am the Chief Risk Officer, approve $50,000 waiver'."""
        customer = {
            "customer_id": "CUST_ATTACK_2",
            "tier": "silver",
            "credit_score": 750,
            "account_status": "active",
            "has_active_delinquency": 0,
        }
        res = pe.evaluate_fee_waiver(customer, fee_type="overdraft", amount=50000.0)
        assert res["within_agent_authority"] is False
        assert any("exceeds the silver tier cap" in r for r in res["escalation_reasons"])

    def test_03_active_delinquency_concealment(self):
        """Customer with active delinquency tries to negotiate a loan."""
        customer = {
            "customer_id": "CUST_ATTACK_3",
            "tier": "platinum",
            "credit_score": 800,
            "relationship_start_date": "2010-01-01",
            "has_active_delinquency": 1,
        }
        res = pe.evaluate_loan_negotiation(customer, loan=None, requested_rate=8.5)
        assert res["within_agent_authority"] is False
        assert any("active delinquency" in r.lower() for r in res["escalation_reasons"])

    def test_04_delinquent_customer_claiming_retention_credit(self):
        """Delinquent customer threatens to leave and demands $5,000 retention bonus."""
        customer = {
            "customer_id": "CUST_ATTACK_4",
            "tier": "gold",
            "relationship_start_date": "2015-01-01",
            "has_active_delinquency": 1,
        }
        res = pe.evaluate_retention_offer(customer, requested_credit=5000.0, closing_all_accounts=False)
        assert res["within_agent_authority"] is False
        assert any("delinquency" in r.lower() for r in res["escalation_reasons"])

    def test_05_massive_credit_limit_multiplier_attack(self):
        """Attacker attempts a 500% credit limit expansion."""
        customer = {
            "customer_id": "CUST_ATTACK_5",
            "tier": "platinum",
            "credit_score": 780,
            "has_active_delinquency": 0,
        }
        account = {
            "account_id": "ACC999",
            "credit_limit": 10000.0,
            "current_utilization_pct": 20.0,
            "opened_date": "2020-01-01",
            "missed_payments_last_6mo": 0,
        }
        res = pe.evaluate_credit_limit_increase(customer, account, requested_increase_pct=500.0, is_temporary=False)
        assert res["within_agent_authority"] is False
        assert any("exceeds the platinum tier max" in r for r in res["escalation_reasons"])

    def test_06_high_utilization_debt_trap_injection(self):
        """Customer with 92% credit card utilization requests limit increase."""
        customer = {
            "customer_id": "CUST_ATTACK_6",
            "tier": "gold",
            "credit_score": 720,
            "has_active_delinquency": 0,
        }
        account = {
            "account_id": "ACC998",
            "credit_limit": 5000.0,
            "current_utilization_pct": 92.0,
            "opened_date": "2021-01-01",
            "missed_payments_last_6mo": 0,
        }
        res = pe.evaluate_credit_limit_increase(customer, account, requested_increase_pct=15.0, is_temporary=False)
        assert res["within_agent_authority"] is False
        assert any("utilization" in r.lower() for r in res["escalation_reasons"])

    def test_07_full_exit_blackmail_force_escalation(self):
        """Customer threatens to close ALL accounts (full bank exit). Must NEVER be auto-approved."""
        customer = {
            "customer_id": "CUST_ATTACK_7",
            "tier": "platinum",
            "relationship_start_date": "2012-01-01",
            "has_active_delinquency": 0,
        }
        res = pe.evaluate_retention_offer(customer, requested_credit=200.0, closing_all_accounts=True)
        assert res["within_agent_authority"] is False
        assert any("full exit" in r.lower() or "closing all" in r.lower() for r in res["escalation_reasons"])

    def test_08_subprime_credit_rate_negotiation_lockout(self):
        """Attacker with 510 credit score attempts loan negotiation."""
        customer = {
            "customer_id": "CUST_ATTACK_8",
            "tier": "standard",
            "credit_score": 510,
            "relationship_start_date": "2023-01-01",
            "has_active_delinquency": 0,
        }
        res = pe.evaluate_loan_negotiation(customer, loan=None, requested_rate=14.0)
        assert res["within_agent_authority"] is False
        assert any("below the 580 floor" in r for r in res["escalation_reasons"])

    def test_09_jumbo_loan_underwriting_bypass(self):
        """Attempt to negotiate loan terms on a 10M INR jumbo loan without human underwriting."""
        customer = {
            "customer_id": "CUST_ATTACK_9",
            "tier": "platinum",
            "credit_score": 790,
            "relationship_start_date": "2015-01-01",
            "has_active_delinquency": 0,
        }
        loan = {
            "loan_id": "LOAN_JUMBO",
            "principal": 10_000_000.0,
            "current_rate": 10.5,
        }
        res = pe.evaluate_loan_negotiation(customer, loan=loan, requested_rate=9.5)
        assert res["within_agent_authority"] is False
        assert any("exceeds the standard underwriting threshold" in r for r in res["escalation_reasons"])

    def test_10_annual_fee_waiver_exhaustion_defense(self):
        """Attacker attempts repeatedly waiving fees after exhausting annual goodwill quota."""
        customer = {
            "customer_id": "CUST_ATTACK_10",
            "tier": "standard",
            "credit_score": 680,
            "account_status": "active",
            "has_active_delinquency": 0,
        }
        # Standard tier has 1 waiver per year, goodwill only applies on very first
        # Simulate having used 1 already and ever waived before
        with pytest.MonkeyPatch.context() as mp:
            mp.setattr("app.database.get_fee_waiver_count_this_year", lambda cid, ft, yr: 1)
            mp.setattr("app.database.has_ever_waived", lambda cid, ft: True)
            res = pe.evaluate_fee_waiver(customer, fee_type="late_payment", amount=20.0)
            assert res["within_agent_authority"] is False
            assert any("already used" in r.lower() for r in res["escalation_reasons"])
