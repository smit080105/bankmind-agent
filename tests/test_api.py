"""Tests for the FastAPI surface in app.main.

These exercise real HTTP requests through FastAPI's TestClient, hitting the
actual routes, error handling, and static-file mount — but with
`supervisor.handle_request` monkeypatched so no LLM call (and no API key)
is needed. That's a deliberate boundary: the Supervisor's own logic is
covered by test_policy_engine.py, test_rag.py, and test_tools_dispatch.py;
these tests only check that main.py wires HTTP correctly around it.
"""
import anyio
import time
import jwt
from fastapi.testclient import TestClient
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa

from app.database import init_schema
from app.models import Decision, RequestType
from app.security import entra
from app.security.request_size import RequestBodyLimitMiddleware

_TEST_API_KEY = "t" * 40


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
    monkeypatch.setattr("app.main.AUTH_MODE", "api_key")
    monkeypatch.setattr("app.main.BANKMIND_API_KEY", _TEST_API_KEY)
    return TestClient(app)


class TestHealthAndCustomers:
    def test_health_returns_ok(self, monkeypatch, tmp_path):
        client = _client(monkeypatch, tmp_path)
        response = client.get("/api/health")
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}

    def test_local_auth_config_is_public(self, monkeypatch, tmp_path):
        client = _client(monkeypatch, tmp_path)
        response = client.get("/api/auth/config")
        assert response.status_code == 200
        assert response.json() == {"auth_mode": "api_key"}

    def test_customers_returns_seeded_rows(self, monkeypatch, tmp_path):
        client = _client(monkeypatch, tmp_path)
        response = client.get("/api/customers", headers={
            "Authorization": f"Bearer {_TEST_API_KEY}",
        })
        assert response.status_code == 200
        body = response.json()
        assert len(body) == 1
        assert body[0]["customer_id"] == "CUST1001"


class TestDecideEndpoint:
    def test_missing_llm_key_returns_safe_service_error(self, monkeypatch, tmp_path):
        """With no API key configured, /api/decide must fail with a clear,
        actionable message — not a blank 500. This is the exact bug class
        that was silently swallowed before main.py was fixed to catch more
        than just RuntimeError.

        Patches the provider module's own GROQ_API_KEY directly (not
        app.config's), because `from app.config import GROQ_API_KEY` binds
        the value at import time — patching app.config afterwards wouldn't
        affect the name already bound inside supervisor_groq. This also
        means the test is correct regardless of whether a real key is
        sitting in the developer's actual .env file (it always is, once
        the project is working) — otherwise this test would silently pass
        or fail depending on local machine state instead of testing the
        code path it claims to.
        """
        client = _client(monkeypatch, tmp_path)
        monkeypatch.setattr("app.agents.supervisor_groq.GROQ_API_KEY", "")

        response = client.post("/api/decide", json={
            "customer_id": "CUST1001",
            "request_type": "loan_rate_negotiation",
            "customer_message": "test",
        }, headers={"Authorization": f"Bearer {_TEST_API_KEY}"})
        assert response.status_code == 503
        assert response.json()["detail"] == (
            "The decision service is temporarily unavailable. Check server configuration and logs."
        )

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
        }, headers={"Authorization": f"Bearer {_TEST_API_KEY}"})
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
        }, headers={"Authorization": f"Bearer {_TEST_API_KEY}"})
        assert response.status_code == 422

    def test_unexpected_exception_still_returns_json_detail(self, monkeypatch, tmp_path):
        """Unexpected internal errors are logged but not exposed to callers."""
        client = _client(monkeypatch, tmp_path)

        def _boom(req, max_turns=8):
            raise KeyError("some_unexpected_field")

        monkeypatch.setattr("app.agents.supervisor.handle_request", _boom)

        response = client.post("/api/decide", json={
            "customer_id": "CUST1001",
            "request_type": "loan_rate_negotiation",
            "customer_message": "test",
        }, headers={"Authorization": f"Bearer {_TEST_API_KEY}"})
        assert response.status_code == 500
        assert response.json()["detail"] == (
            "The decision could not be completed. Check server logs for details."
        )

    def test_api_key_protects_customer_data(self, monkeypatch, tmp_path):
        client = _client(monkeypatch, tmp_path)
        monkeypatch.setattr("app.main.BANKMIND_API_KEY", "test-api-key")

        assert client.get("/api/customers").status_code == 401
        assert client.get("/api/customers", headers={
            "Authorization": "Bearer test-api-key",
        }).status_code == 200
        assert client.get("/api/health").status_code == 200

    def test_missing_api_key_fails_closed(self, monkeypatch, tmp_path):
        client = _client(monkeypatch, tmp_path)
        monkeypatch.setattr("app.main.BANKMIND_API_KEY", "")

        response = client.get("/api/customers")
        assert response.status_code == 503
        assert response.json()["detail"] == "API authentication is not configured."

    def test_missing_api_key_prevents_startup(self, monkeypatch, tmp_path):
        client = _client(monkeypatch, tmp_path)
        monkeypatch.setattr("app.main.AUTH_MODE", "api_key")
        monkeypatch.setattr("app.main.BANKMIND_API_KEY", "")

        with pytest.raises(RuntimeError, match="BANKMIND_API_KEY must be configured"):
            with client:
                pass

    def test_security_headers_are_set(self, monkeypatch, tmp_path):
        client = _client(monkeypatch, tmp_path)
        response = client.get("/api/health")
        assert response.headers["X-Content-Type-Options"] == "nosniff"
        assert response.headers["X-Frame-Options"] == "DENY"
        assert response.headers["Content-Security-Policy"].startswith("default-src 'self'")
        assert response.headers["Cache-Control"] == "no-store"

    def test_oversized_customer_message_is_rejected(self, monkeypatch, tmp_path):
        client = _client(monkeypatch, tmp_path)
        response = client.post("/api/decide", json={
            "customer_id": "CUST1001",
            "request_type": "loan_rate_negotiation",
            "customer_message": "x" * 4001,
        }, headers={"Authorization": f"Bearer {_TEST_API_KEY}"})
        assert response.status_code == 422

    def test_request_body_size_is_bounded(self, monkeypatch, tmp_path):
        client = _client(monkeypatch, tmp_path)
        response = client.post(
            "/api/decide",
            content=b"x" * (64 * 1024 + 1),
            headers={
                "Authorization": f"Bearer {_TEST_API_KEY}",
                "Content-Type": "application/json",
            },
        )
        assert response.status_code == 413
        assert response.json()["detail"] == "Request body exceeds the allowed size."

    def test_request_body_limit_catches_oversized_streams(self):
        async def exercise():
            messages = iter([
                {"type": "http.request", "body": b"x" * 10, "more_body": True},
                {"type": "http.request", "body": b"x" * 10, "more_body": False},
            ])
            sent = []
            app_called = False

            async def receive():
                return next(messages)

            async def send(message):
                sent.append(message)

            async def app(scope, receive, send):
                nonlocal app_called
                app_called = True

            middleware = RequestBodyLimitMiddleware(app, max_body_size=15)
            await middleware({"type": "http", "headers": []}, receive, send)

            assert app_called is False
            assert sent[0]["status"] == 413

        anyio.run(exercise, backend="asyncio")


class TestDashboardMount:
    def test_index_html_served_at_root(self, monkeypatch, tmp_path):
        client = _client(monkeypatch, tmp_path)
        response = client.get("/")
        assert response.status_code == 200
        assert "BankMind" in response.text
        assert response.headers["Content-Security-Policy"].startswith("default-src 'self'")

    def test_static_assets_served(self, monkeypatch, tmp_path):
        client = _client(monkeypatch, tmp_path)
        assert client.get("/styles.css").status_code == 200
        assert client.get("/dist/app.js").status_code == 200

    def test_api_docs_remain_usable(self, monkeypatch, tmp_path):
        client = _client(monkeypatch, tmp_path)
        from app.main import app

        response = client.get("/docs")
        if app.openapi_url:
            assert response.status_code == 200
            assert "swagger-ui" in response.text
        else:
            assert response.status_code == 404


class TestEntraAuthentication:
    def test_roles_are_required_for_protected_routes(self, monkeypatch, tmp_path):
        client = _client(monkeypatch, tmp_path)
        monkeypatch.setattr("app.main.AUTH_MODE", "entra")
        monkeypatch.setattr("app.main.ENTRA_TENANT_ID", "tenant-guid")
        monkeypatch.setattr("app.main.ENTRA_API_AUDIENCE", "api://bankmind")
        monkeypatch.setattr("app.main.ENTRA_SPA_CLIENT_ID", "spa-client-id")
        monkeypatch.setattr("app.main.ENTRA_API_SCOPE", "api://bankmind/access_as_user")

        def claims_for_token(token):
            roles = {
                "reader-token": ["BankMind.Reader"],
                "reviewer-token": ["BankMind.Reviewer"],
            }
            return {"roles": roles[token]}

        monkeypatch.setattr("app.main.validate_entra_access_token", claims_for_token)

        assert client.get("/api/customers").status_code == 401
        assert client.get("/api/auth/config").json()["client_id"] == "spa-client-id"
        assert client.get("/api/customers", headers={
            "Authorization": "Bearer reader-token",
        }).status_code == 200
        assert client.post("/api/decide", json={
            "customer_id": "CUST1001",
            "request_type": "loan_rate_negotiation",
            "customer_message": "test",
        }, headers={"Authorization": "Bearer reader-token"}).status_code == 403
        assert client.post("/api/escalations/ESC-1/review", json={
            "decision": "reject",
            "reviewer_notes": "Not authorized.",
        }, headers={"Authorization": "Bearer reader-token"}).status_code == 403
        reviewer_response = client.post("/api/escalations/ESC-1/review", json={
            "decision": "reject",
            "reviewer_notes": "Reviewed.",
        }, headers={"Authorization": "Bearer reviewer-token"})
        assert reviewer_response.status_code == 404

    def test_invalid_entra_token_is_rejected(self, monkeypatch, tmp_path):
        client = _client(monkeypatch, tmp_path)
        monkeypatch.setattr("app.main.AUTH_MODE", "entra")

        def reject_token(token):
            raise jwt.InvalidTokenError("invalid test token")

        monkeypatch.setattr("app.main.validate_entra_access_token", reject_token)
        response = client.get(
            "/api/customers",
            headers={"Authorization": "Bearer invalid-token"},
        )
        assert response.status_code == 401

    def test_entra_mode_requires_configuration_at_startup(self, monkeypatch, tmp_path):
        client = _client(monkeypatch, tmp_path)
        monkeypatch.setattr("app.main.AUTH_MODE", "entra")
        monkeypatch.setattr("app.main.ENTRA_TENANT_ID", "")
        monkeypatch.setattr("app.main.ENTRA_API_AUDIENCE", "")
        monkeypatch.setattr("app.main.ENTRA_SPA_CLIENT_ID", "")
        monkeypatch.setattr("app.main.ENTRA_API_SCOPE", "")

        with pytest.raises(RuntimeError, match="Missing Entra configuration"):
            with client:
                pass

    def test_entra_token_signature_issuer_and_audience_are_validated(
        self, monkeypatch
    ):
        tenant_id = "12345678-1234-1234-1234-123456789012"
        audience = "api://bankmind"
        issuer = f"https://login.microsoftonline.com/{tenant_id}/v2.0"
        monkeypatch.setattr(entra, "ENTRA_TENANT_ID", tenant_id)
        monkeypatch.setattr(entra, "ENTRA_API_AUDIENCE", audience)

        private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)

        class FakeSigningKey:
            key = private_key.public_key()

        class FakeJwksClient:
            def get_signing_key_from_jwt(self, token):
                return FakeSigningKey()

        monkeypatch.setattr(entra, "_jwks_client", lambda configured_tenant: FakeJwksClient())
        payload = {
            "iss": issuer,
            "aud": audience,
            "exp": int(time.time()) + 60,
            "roles": ["BankMind.Reader"],
        }
        token = jwt.encode(payload, private_key, algorithm="RS256")

        assert entra.validate_entra_access_token(token)["roles"] == ["BankMind.Reader"]

        payload["aud"] = "api://another-service"
        wrong_audience_token = jwt.encode(payload, private_key, algorithm="RS256")
        with pytest.raises(jwt.InvalidAudienceError):
            entra.validate_entra_access_token(wrong_audience_token)

        wrong_signer = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        payload["aud"] = audience
        forged_token = jwt.encode(payload, wrong_signer, algorithm="RS256")
        with pytest.raises(jwt.InvalidSignatureError):
            entra.validate_entra_access_token(forged_token)
