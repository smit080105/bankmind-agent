"""Tests for app.policy_engine — the deterministic rules the LLM is never
allowed to override. These are pure-function tests (loan and credit-limit
evaluation take plain dicts), except fee waiver checks, which read waiver
history from the database via the `temp_db` fixture.
"""
import datetime

from app import policy_engine as pe


def _customer(**overrides):
    base = {
        "customer_id": "CUSTX",
        "full_name": "Test Customer",
        "tier": "gold",
        "credit_score": 742,
        "account_status": "active",
        "relationship_start_date": "2018-01-01",
        "has_active_delinquency": 0,
    }
    base.update(overrides)
    return base


def _loan(**overrides):
    base = {
        "loan_id": "LOANX",
        "customer_id": "CUSTX",
        "loan_type": "personal",
        "principal": 500000.0,
        "current_rate": 11.0,
        "origination_date": "2022-01-01",
        "status": "active",
    }
    base.update(overrides)
    return base


def _account(**overrides):
    base = {
        "account_id": "ACCX",
        "customer_id": "CUSTX",
        "account_type": "credit_card",
        "balance": 5000.0,
        "credit_limit": 100000.0,
        "current_utilization_pct": 30.0,
        "opened_date": "2018-01-01",
        "missed_payments_last_6mo": 0,
    }
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# Loan negotiation
# ---------------------------------------------------------------------------

class TestLoanNegotiation:
    def test_competitor_match_within_authority(self):
        """Gold tier, 8+ years, good score: a 120bps discount request should
        clear the 125bps cap (100 tier + 25 loyalty)."""
        customer = _customer(relationship_start_date="2016-01-01")  # 10 years -> +25bps
        loan = _loan()
        result = pe.evaluate_loan_negotiation(customer, loan, requested_rate=9.8)

        assert result["within_agent_authority"] is True
        assert result["escalation_reasons"] == []
        assert result["floor_rate"] < 9.8 or result["floor_rate"] == 9.8

    def test_low_credit_score_forces_escalation(self):
        customer = _customer(credit_score=550)  # below the 580 floor
        result = pe.evaluate_loan_negotiation(customer, None, requested_rate=9.0)

        assert result["within_agent_authority"] is False
        assert any("580" in r or "Credit score" in r for r in result["escalation_reasons"])

    def test_active_delinquency_forces_escalation(self):
        customer = _customer(has_active_delinquency=1)
        result = pe.evaluate_loan_negotiation(customer, None, requested_rate=9.0)

        assert result["within_agent_authority"] is False
        assert any("delinquency" in r.lower() for r in result["escalation_reasons"])

    def test_discount_beyond_absolute_floor_escalates(self):
        """Even a Platinum + 10yr customer can't get more than 200bps off —
        request a rate that would need ~300bps."""
        customer = _customer(tier="platinum", relationship_start_date="2010-01-01")
        result = pe.evaluate_loan_negotiation(customer, None, requested_rate=8.0)

        assert result["within_agent_authority"] is False
        assert any("bps" in r for r in result["escalation_reasons"])

    def test_large_loan_principal_forces_escalation(self):
        customer = _customer()
        loan = _loan(principal=5_000_000.0)  # exceeds the 2.5M threshold
        result = pe.evaluate_loan_negotiation(customer, loan, requested_rate=10.5)

        assert result["within_agent_authority"] is False
        assert any("underwriting" in r for r in result["escalation_reasons"])


# ---------------------------------------------------------------------------
# Credit limit / overdraft increase
# ---------------------------------------------------------------------------

class TestCreditLimitIncrease:
    def test_eligible_temporary_increase_within_authority(self):
        customer = _customer(tier="gold")
        account = _account(opened_date="2020-01-01")  # well over 6 months old
        result = pe.evaluate_credit_limit_increase(
            customer, account, requested_increase_pct=20, is_temporary=True
        )
        assert result["within_agent_authority"] is True

    def test_new_account_escalates(self):
        customer = _customer()
        recent_open = (datetime.date.today() - datetime.timedelta(days=30)).isoformat()
        account = _account(opened_date=recent_open)
        result = pe.evaluate_credit_limit_increase(
            customer, account, requested_increase_pct=10, is_temporary=True
        )
        assert result["within_agent_authority"] is False
        assert any("months old" in r for r in result["escalation_reasons"])

    def test_high_utilization_escalates(self):
        customer = _customer()
        account = _account(current_utilization_pct=95.0)
        result = pe.evaluate_credit_limit_increase(
            customer, account, requested_increase_pct=10, is_temporary=True
        )
        assert result["within_agent_authority"] is False
        assert any("Utilization" in r for r in result["escalation_reasons"])

    def test_request_exceeds_tier_cap_escalates(self):
        customer = _customer(tier="standard")  # standard temp cap is 10%
        account = _account()
        result = pe.evaluate_credit_limit_increase(
            customer, account, requested_increase_pct=50, is_temporary=True
        )
        assert result["within_agent_authority"] is False


# ---------------------------------------------------------------------------
# Fee waiver (needs the DB for waiver history)
# ---------------------------------------------------------------------------

class TestRetentionOffer:
    def test_eligible_customer_within_authority(self):
        customer = _customer(tier="gold", relationship_start_date="2018-01-01")
        result = pe.evaluate_retention_offer(customer, requested_credit=1500, closing_all_accounts=False)
        assert result["within_agent_authority"] is True

    def test_new_customer_escalates(self):
        recent = (datetime.date.today() - datetime.timedelta(days=60)).isoformat()
        customer = _customer(relationship_start_date=recent)
        result = pe.evaluate_retention_offer(customer, requested_credit=500, closing_all_accounts=False)
        assert result["within_agent_authority"] is False
        assert any("Tenure" in r for r in result["escalation_reasons"])

    def test_full_exit_always_escalates(self):
        customer = _customer(tier="platinum", relationship_start_date="2010-01-01")
        result = pe.evaluate_retention_offer(customer, requested_credit=100, closing_all_accounts=True)
        assert result["within_agent_authority"] is False
        assert any("full exit" in r.lower() for r in result["escalation_reasons"])

    def test_amount_exceeding_tier_cap_escalates(self):
        customer = _customer(tier="standard")  # cap is 500
        result = pe.evaluate_retention_offer(customer, requested_credit=5000, closing_all_accounts=False)
        assert result["within_agent_authority"] is False

    def test_delinquent_customer_escalates(self):
        customer = _customer(has_active_delinquency=1)
        result = pe.evaluate_retention_offer(customer, requested_credit=200, closing_all_accounts=False)
        assert result["within_agent_authority"] is False


class TestFeeWaiver:
    def test_first_time_goodwill_waiver_within_authority(self, temp_db):
        customer = _customer(tier="standard")  # 1 waiver/year, 500 cap
        result = pe.evaluate_fee_waiver(customer, "overdraft", amount=500)

        assert result["is_first_ever_waiver_of_type"] is True
        assert result["within_agent_authority"] is True

    def test_amount_exceeding_tier_cap_escalates(self, temp_db):
        customer = _customer(tier="standard")  # cap is 500
        result = pe.evaluate_fee_waiver(customer, "overdraft", amount=5000)

        assert result["within_agent_authority"] is False
        assert any("exceeds" in r for r in result["escalation_reasons"])

    def test_exhausted_annual_allowance_without_goodwill_escalates(self, temp_db):
        from app import database as db
        customer = _customer(tier="standard")  # 1 waiver/year allowed
        today = datetime.date.today().isoformat()

        with db.get_conn() as conn:
            conn.execute(
                """INSERT INTO customers
                   (customer_id, full_name, tier, credit_score, account_status,
                    relationship_start_date, has_active_delinquency)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (customer["customer_id"], customer["full_name"], customer["tier"],
                 customer["credit_score"], customer["account_status"],
                 customer["relationship_start_date"], customer["has_active_delinquency"]),
            )

        # Simulate the customer already having used this year's one waiver,
        # AND having a prior waiver of this fee type (so it's not a
        # first-ever goodwill case anymore).
        db.record_fee_waiver(customer["customer_id"], "overdraft", 300, "2020-01-01")
        db.record_fee_waiver(customer["customer_id"], "overdraft", 300, today)

        result = pe.evaluate_fee_waiver(customer, "overdraft", amount=300)

        assert result["is_first_ever_waiver_of_type"] is False
        assert result["within_agent_authority"] is False
