"""Tests for FinTech Security: PII Sanitizer and Cryptographic Audit Ledger."""
import json
import pytest

from app.security.sanitizer import PIISanitizer
from app.security import audit
from app.database import init_schema, record_action, get_action_ledger, get_conn


class TestPIISanitizer:
    def test_sanitizes_credit_card_numbers(self):
        text = "Customer wants to pay using 4111-2222-3333-4444 on account ACC1001."
        sanitized, token_map = PIISanitizer.sanitize(text)
        assert "4111-2222-3333-4444" not in sanitized
        assert "ACC1001" not in sanitized
        assert "[CARD_TOKEN_1]" in sanitized
        assert "[ACCOUNT_TOKEN_1]" in sanitized

        # Test reversal
        restored = PIISanitizer.restore(sanitized, token_map)
        assert restored == text

    def test_sanitizes_emails_and_phone_numbers(self):
        text = "Contact customer at john.doe@bank.com or +1 555-123-4567 regarding loan."
        sanitized, token_map = PIISanitizer.sanitize(text)
        assert "john.doe@bank.com" not in sanitized
        assert "555-123-4567" not in sanitized
        assert "[EMAIL_TOKEN_1]" in sanitized
        assert "[PHONE_TOKEN_1]" in sanitized

    def test_handles_empty_or_clean_text(self):
        clean = "I want a personal loan rate reduction."
        sanitized, token_map = PIISanitizer.sanitize(clean)
        assert sanitized == clean
        assert len(token_map) == 0


class TestCryptographicAuditLedger:
    def test_hash_chain_integrity(self, monkeypatch, tmp_path):
        db_path = tmp_path / "audit_test.db"
        monkeypatch.setattr("app.database.DATABASE_PATH", db_path)
        init_schema()

        # Add 3 records
        rec1 = record_action("CUST1001", "loan_rate_change", json.dumps({"rate": 9.5}), "2026-09-30T10:00:00", "executed")
        rec2 = record_action("CUST1002", "fee_waiver", json.dumps({"fee": 25.0}), "2026-09-30T10:05:00", "executed")
        rec3 = record_action("CUST1003", "escalation", json.dumps({"reasons": ["low credit"]}), "2026-09-30T10:10:00", "escalated")

        assert rec1["prev_hash"] == audit.GENESIS_HASH
        assert rec2["prev_hash"] == rec1["record_hash"]
        assert rec3["prev_hash"] == rec2["record_hash"]

        ledger = get_action_ledger()
        is_valid, msg, broken_id = audit.verify_chain(ledger)
        assert is_valid is True
        assert broken_id is None

    def test_tamper_detection(self, monkeypatch, tmp_path):
        db_path = tmp_path / "tamper_test.db"
        monkeypatch.setattr("app.database.DATABASE_PATH", db_path)
        init_schema()

        record_action("CUST1001", "loan_rate_change", json.dumps({"rate": 9.5}), "2026-09-30T10:00:00", "executed")
        record_action("CUST1002", "fee_waiver", json.dumps({"fee": 25.0}), "2026-09-30T10:05:00", "executed")
        record_action("CUST1003", "fee_waiver", json.dumps({"fee": 50.0}), "2026-09-30T10:10:00", "executed")

        # Rogue database edit: Tamper with record 2 details (e.g. changing fee 25 to 500)
        with get_conn() as conn:
            conn.execute("UPDATE action_ledger SET details = ? WHERE id = 2", (json.dumps({"fee": 500.0}),))

        ledger = get_action_ledger()
        is_valid, msg, broken_id = audit.verify_chain(ledger)
        assert is_valid is False
        assert broken_id == 2
        assert "Tampered record at id=2" in msg
