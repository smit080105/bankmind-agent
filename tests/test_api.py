"""Tests for the FastAPI surface in app.main.

These exercise real HTTP requests through FastAPI's TestClient, hitting the
actual routes, error handling, and static-file mount — but with
`supervisor.handle_request` monkeypatched so no LLM call (and no API key)
is needed. That's a deliberate boundary: the Supervisor's own logic is
covered by test_policy_engine.py, test_rag.py, and test_tools_dispatch.py;
these tests only check that main.py wires HTTP correctly around it.
"""
from fastapi.testclient import TestClient

from app.database import init_schema
from app.models import Decision, RequestType


def _client(monkeypatch, tmp_path):
    db_path = tmp_path / "test.db"
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

    from app.main import app
    return TestClient(app)


class TestHealthAndCustomers:
    def test_health_returns_ok(self, monkeypatch, tmp_path):
        client = _client(monkeypatch, tmp_path)
        response = client.get("/api/health")
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}

    def test_customers_returns_seeded_rows(self, monkeypatch, tmp_path):
        client = _client(monkeypatch, tmp_path)
        response = client.get("/api/customers")
        assert response.status_code == 200
        body = response.json()
        assert len(body) == 1
        assert body[0]["customer_id"] == "CUST1001"


class TestDecideEndpoint:
    def test_missing_llm_key_returns_actionable_500(self, monkeypatch, tmp_path):
        """With no API key configured for any provider, /api/decide must
        fail with a clear, actionable message — not a blank 500. This is
        the exact bug class that was silently swallowed before main.py
        was fixed to catch more than just RuntimeError."""
        client = _client(monkeypatch, tmp_path)
        response = client.post("/api/decide", json={
            "customer_id": "CUST1001",
            "request_type": "loan_rate_negotiation",
            "customer_message": "test",
        })
        assert response.status_code == 500
        assert "API_KEY" in response.json()["detail"] or "not set" in response.json()["detail"]

    def test_successful_decision_round_trips(self, monkeypatch, tmp_path):
        """Mock the Supervisor entirely to verify main.py correctly
        serializes a Decision back out over HTTP."""
        client = _client(monkeypatch, tmp_path)

        fake_decision = Decision(
            customer_id="CUST1001",
            request_type=RequestType.LOAN_RATE_NEGOTIATION,
            outcome="approved",
            terms={"new_rate": 9.8},
            reasoning="Matched competitor rate within policy.",
            policy_citations=["loan_negotiation.md — Competitor matching"],
            trace=[],
        )
        monkeypatch.setattr(
            "app.agents.supervisor.handle_request", lambda req, max_turns=8: fake_decision
        )

        response = client.post("/api/decide", json={
            "customer_id": "CUST1001",
            "request_type": "loan_rate_negotiation",
            "customer_message": "match my rate please",
        })
        assert response.status_code == 200
        body = response.json()
        assert body["outcome"] == "approved"
        assert body["terms"]["new_rate"] == 9.8

    def test_invalid_request_type_returns_422(self, monkeypatch, tmp_path):
        client = _client(monkeypatch, tmp_path)
        response = client.post("/api/decide", json={
            "customer_id": "CUST1001",
            "request_type": "not_a_real_type",
            "customer_message": "test",
        })
        assert response.status_code == 422

    def test_unexpected_exception_still_returns_json_detail(self, monkeypatch, tmp_path):
        """A non-RuntimeError exception (e.g. a provider SDK error) must
        still come back as JSON with a `detail` field the dashboard can
        display — not an opaque, undetailed 500."""
        client = _client(monkeypatch, tmp_path)

        def _boom(req, max_turns=8):
            raise KeyError("some_unexpected_field")

        monkeypatch.setattr("app.agents.supervisor.handle_request", _boom)

        response = client.post("/api/decide", json={
            "customer_id": "CUST1001",
            "request_type": "loan_rate_negotiation",
            "customer_message": "test",
        })
        assert response.status_code == 500
        assert "detail" in response.json()
        assert "KeyError" in response.json()["detail"]


class TestDashboardMount:
    def test_index_html_served_at_root(self, monkeypatch, tmp_path):
        client = _client(monkeypatch, tmp_path)
        response = client.get("/")
        assert response.status_code == 200
        assert "BankMind" in response.text

    def test_static_assets_served(self, monkeypatch, tmp_path):
        client = _client(monkeypatch, tmp_path)
        assert client.get("/styles.css").status_code == 200
        assert client.get("/app.js").status_code == 200
