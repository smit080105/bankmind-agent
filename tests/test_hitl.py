"""Tests for Human-in-the-Loop (HITL) escalation queue and Underwriter Review."""
from fastapi.testclient import TestClient

from app.database import init_schema, get_escalations, get_action_ledger
from app.agents import escalation_agent
from app.main import app


class TestHITLEscalationWorkflow:
    def test_escalation_creates_pending_case(self, monkeypatch, tmp_path):
        db_path = tmp_path / "hitl_test.db"
        monkeypatch.setattr("app.database.DATABASE_PATH", db_path)
        init_schema()

        res = escalation_agent.escalate(
            customer_id="CUST1004",
            request_type="loan_rate_negotiation",
            reasons=["Credit score 550 is below policy floor."],
            context={"requested_rate": 6.5, "loan_id": "LOAN101"},
        )
        assert res["status"] == "escalated"
        assert res["case_id"].startswith("ESC-")

        # Verify case is in escalation queue
        pending = get_escalations(status="pending")
        assert len(pending) == 1
        assert pending[0]["case_id"] == res["case_id"]
        assert pending[0]["customer_id"] == "CUST1004"

    def test_underwriter_approval_via_api(self, monkeypatch, tmp_path):
        db_path = tmp_path / "hitl_api_test.db"
        monkeypatch.setattr("app.database.DATABASE_PATH", db_path)
        init_schema()

        from app.database import get_conn
        with get_conn() as conn:
            conn.execute(
                """INSERT INTO customers
                   (customer_id, full_name, tier, credit_score, account_status,
                    relationship_start_date, has_active_delinquency)
                   VALUES ('CUST1005', 'Vikram Mehta', 'gold', 740, 'active', '2019-01-01', 0)"""
            )

        client = TestClient(app)

        # 1. Trigger an escalation
        esc = escalation_agent.escalate(
            customer_id="CUST1005",
            request_type="fee_waiver",
            reasons=["Requested fee waiver $120 exceeds standard tier allowance."],
            context={"fee_type": "maintenance", "amount": 120.0},
        )
        case_id = esc["case_id"]

        # 2. Underwriter inspects list of pending escalations
        resp = client.get("/api/escalations?status=pending")
        assert resp.status_code == 200
        cases = resp.json()
        assert any(c["case_id"] == case_id for c in cases)

        # 3. Underwriter reviews and overrides/approves the waiver
        review_resp = client.post(f"/api/escalations/{case_id}/review", json={
            "decision": "override",
            "reviewer_notes": "High net-worth customer relationship, approved as one-time exception.",
            "overridden_terms": {"waived_amount": 100.0},
        })
        assert review_resp.status_code == 200
        data = review_resp.json()
        assert data["case"]["status"] == "overridden"
        assert data["execution"]["status"] == "executed"
        assert data["execution"]["amount"] == 100.0

        # 4. Verify cryptographic ledger was updated
        ledger = get_action_ledger()
        assert len(ledger) >= 2  # Escalation log + Execution log

    def test_idempotency_header_prevents_duplicate_processing(self, monkeypatch, tmp_path):
        db_path = tmp_path / "idemp_test.db"
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

        client = TestClient(app)

        call_count = 0
        from app.models import Decision, RequestType

        def _mock_handle(req, max_turns=8):
            nonlocal call_count
            call_count += 1
            return Decision(
                customer_id=req.customer_id,
                request_type=RequestType.FEE_WAIVER,
                outcome="approved",
                terms={"waived_amount": 25.0},
                reasoning="Approved fee waiver.",
                policy_citations=[],
                trace=[],
            )

        monkeypatch.setattr("app.agents.supervisor.handle_request", _mock_handle)

        payload = {
            "customer_id": "CUST1001",
            "request_type": "fee_waiver",
            "customer_message": "Please waive my late fee.",
            "requested_value": 25.0,
        }
        headers = {"Idempotency-Key": "test-key-12345"}

        # First call
        resp1 = client.post("/api/decide", json=payload, headers=headers)
        assert resp1.status_code == 200
        assert resp1.headers.get("X-Cache-Hit") is None
        assert call_count == 1

        # Second call with same idempotency key
        resp2 = client.post("/api/decide", json=payload, headers=headers)
        assert resp2.status_code == 200
        assert resp2.headers.get("X-Cache-Hit") == "true"
        assert resp2.json()["outcome"] == "approved"
        # Crucial: Supervisor handle_request was NOT called a second time
        assert call_count == 1
