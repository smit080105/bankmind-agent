"""Tests for Double-Entry General Ledger accounting and transaction balancing."""
import pytest
from app.accounting.ledger import (
    JournalEntry,
    JournalLine,
    UnbalancedJournalEntryError,
    create_fee_waiver_entry,
    create_retention_credit_entry,
)
from app.agents import execution_agent
from app.database import init_schema, get_general_ledger_entries


class TestDoubleEntryLedger:
    def test_balanced_journal_passes(self):
        entry = JournalEntry(
            transaction_id="TX-101",
            description="Test balanced entry",
            timestamp="2026-09-30T10:00:00",
            lines=[
                JournalLine(account="Expenses:FeeWaiverGoodwill", debit=100.0, credit=0.0),
                JournalLine(account="Revenue:FeeIncome", debit=0.0, credit=100.0),
            ]
        )
        entry.validate()  # Should not raise

    def test_unbalanced_journal_raises_error(self):
        entry = JournalEntry(
            transaction_id="TX-102",
            description="Test unbalanced entry",
            timestamp="2026-09-30T10:00:00",
            lines=[
                JournalLine(account="Expenses:FeeWaiverGoodwill", debit=100.0, credit=0.0),
                JournalLine(account="Revenue:FeeIncome", debit=0.0, credit=50.0),
            ]
        )
        with pytest.raises(UnbalancedJournalEntryError) as exc_info:
            entry.validate()
        assert "total debits (100.0) != total credits (50.0)" in str(exc_info.value)

    def test_fee_waiver_posts_balanced_general_ledger(self, monkeypatch, tmp_path):
        db_path = tmp_path / "gl_test.db"
        monkeypatch.setattr("app.database.DATABASE_PATH", db_path)
        init_schema()

        from app.database import get_conn
        with get_conn() as conn:
            conn.execute(
                """INSERT INTO customers
                   (customer_id, full_name, tier, credit_score, account_status,
                    relationship_start_date, has_active_delinquency)
                   VALUES ('CUST1001', 'Ananya Rao', 'gold', 742, 'active', '2018-01-01', 0)"""
            )

        res = execution_agent.execute_fee_waiver("CUST1001", "overdraft", 75.0)
        assert res["status"] == "executed"
        assert "transaction_id" in res

        gl_rows = get_general_ledger_entries(tx_id=res["transaction_id"])
        assert len(gl_rows) == 2
        debits = sum(r["debit"] for r in gl_rows)
        credits = sum(r["credit"] for r in gl_rows)
        assert debits == credits == 75.0
