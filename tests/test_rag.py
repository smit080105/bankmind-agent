"""Tests for app.rag — the keyword-scored retrieval over policy markdown."""
from app import rag


class TestPolicyRetrieval:
    def test_loan_query_returns_loan_negotiation_content(self):
        results = rag.retrieve_policy_context(
            "loan rate negotiation discount escalation", source_filter="loan_negotiation"
        )
        assert len(results) > 0
        assert all(c.source == "loan_negotiation" for c in results)

    def test_fee_waiver_query_does_not_return_loan_docs(self):
        results = rag.retrieve_policy_context(
            "overdraft fee waiver goodwill", source_filter="fee_waiver"
        )
        assert len(results) > 0
        assert all(c.source == "fee_waiver" for c in results)

    def test_nonsense_query_returns_nothing(self):
        results = rag.retrieve_policy_context("zzz_nonexistent_topic_qqq")
        assert results == []

    def test_retention_offer_query_returns_retention_docs(self):
        results = rag.retrieve_policy_context(
            "retention credit tenure full exit", source_filter="retention_offer"
        )
        assert len(results) > 0
        assert all(c.source == "retention_offer" for c in results)

    def test_format_context_handles_empty_list(self):
        formatted = rag.format_context_for_prompt([])
        assert "No directly relevant" in formatted

    def test_format_context_includes_source_and_heading(self):
        results = rag.retrieve_policy_context(
            "credit limit eligibility utilization", source_filter="credit_limit"
        )
        formatted = rag.format_context_for_prompt(results)
        assert "credit_limit" in formatted
