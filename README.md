# bankmind-agent

![Tests](https://github.com/smit080105/bankmind-agent/actions/workflows/tests.yml/badge.svg)
![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)
![Python 3.12](https://img.shields.io/badge/python-3.12-blue.svg)
![Audit: SHA--256 Chained](https://img.shields.io/badge/audit-SHA--256%20chained-success.svg)
![PII: Pattern masking](https://img.shields.io/badge/PII-pattern%20masking-blue.svg)

A portfolio project demonstrating an agentic banking workflow that combines **deterministic policy checks** with **LLM orchestration** to evaluate requests, manage human-in-the-loop (HITL) escalations, record double-entry transactions, and maintain a tamper-evident audit chain.

---

## Resume-ready project summary

**BankMind** is a Python/FastAPI portfolio application that demonstrates a human-supervised banking operations workflow. It combines LLM tool orchestration with deterministic policy rules, SQLite persistence, and a browser-based review dashboard.

Resume bullets you can adapt:

- Built a multi-provider LLM agent workflow with specialist tools and request-scoped authorization; tool executions recheck deterministic policy against current database state.
- Implemented YAML-driven policy checks and retrieval over policy documents, with human review for requests outside automated authority.
- Added idempotent API request handling, a SHA-256 hash-chained action ledger, and balanced double-entry journals for supported demo transactions.
- Developed a responsive dashboard for customer intake, underwriter review, and audit-chain inspection, backed by FastAPI endpoints.
- Added an offline pytest suite covering policy boundaries, API behavior, escalation workflows, sanitization, audit verification, and accounting invariants.
- Added Entra access-token validation with role-scoped API permissions, a local-demo API-key mode, restrictive CORS defaults, bounded inputs, safer API error handling, and atomic one-time escalation review.

These are project features, not measured production outcomes. Adjust the wording to match your contribution and verify details before using them on a resume.

## Scope and limitations

This is a portfolio demonstration using synthetic sample data. It is not a banking service and must not be used for real customer data, financial decisions, or transactions. PII masking uses patterns and is not comprehensive or a substitute for a reviewed data-protection program. The hash chain is tamper-evident for verified records, but is not an immutable or independently anchored audit system. Entra authentication is an integration foundation that still requires tenant-specific app registration, role assignments, deployment review, and operational controls; it makes no regulatory-compliance claim.

The customer-facing agent is an AI relationship-manager assistant, not a human bank manager. It is designed to explain supported workflow outcomes clearly, apply the demo's deterministic rules, and route exceptions for human review. The numeric limits in the policy files are illustrative portfolio settings, not claims about universal banking practice or regulatory standards. A real institution must set and validate its own jurisdiction-specific policies, customer-fairness controls, approval authority, disclosures, and complaint-handling process with qualified compliance and legal teams before deployment.

## Security configuration

- `AUTH_MODE=api_key` uses a single shared bearer key and is for local demos only. The API refuses to start if that key is missing or shorter than 32 characters. The dashboard keeps it in tab-scoped `sessionStorage`, which remains accessible to same-origin JavaScript.
- `AUTH_MODE` defaults to `entra`, which fails startup unless its required configuration is present. For local demos, explicitly set `AUTH_MODE=api_key` and configure the local key.
- Set `AUTH_MODE=entra` to require Entra v2 access tokens. The API validates the RS256 signature against tenant JWKS and checks issuer, audience, and expiry. The browser uses MSAL with authorization-code/PKCE flow; access tokens remain in MSAL's session storage. Set `ENTRA_TENANT_ID`, `ENTRA_API_AUDIENCE`, `ENTRA_SPA_CLIENT_ID`, and `ENTRA_API_SCOPE`; optionally set `ENTRA_REDIRECT_URI`.
- Configure an Entra API app registration to expose the delegated scope named in `ENTRA_API_SCOPE` and define app roles with values `BankMind.Reader`, `BankMind.Reviewer`, and `BankMind.Operator`. Assign users/groups explicitly. Reader permits data reads, Reviewer permits reads and escalation review, and Operator permits reads and decision submission. The API rejects valid tokens lacking the required role.
- `GET /api/auth/config` is public and returns only non-secret SPA configuration so the dashboard can initialize MSAL. `/api/health` is also public. Interactive API docs and OpenAPI schema are disabled when `AUTH_MODE=entra`; they remain available in local API-key mode.
- `CORS_ALLOWED_ORIGINS` is a comma-separated allowlist; it defaults to the two local dashboard origins rather than `*`.
- Request bodies are limited to 64 KiB, model values and human override fields are validated, API responses are marked `no-store`, and a restrictive Content Security Policy is set. Unexpected decision failures are logged server-side rather than returned to clients, and an escalation can transition out of `pending` only once.
- Each LLM tool call is bound to the original request/customer. The execution dispatcher recomputes policy against database state immediately before writing an action; model-provided policy results are not treated as execution authorization.
- Docker runs as an unprivileged user, uses a read-only root filesystem, drops Linux capabilities, and binds its published port to localhost. Place it behind a TLS-terminating reverse proxy; if that proxy is in another container, configure a private Docker network and an explicit, non-public app port binding.
- Entra integration does not make the application production-ready by itself. Configure and review the tenant/app registrations and role assignments; add persistent rate limiting at the deployment gateway, managed secrets, Python dependency locking/updating, encrypted database storage/backups, and separately controlled append-only audit export. Terminate TLS at a trusted proxy, pin container images to reviewed digests, set the production CORS origins, and enable GitHub secret scanning/push protection. Define provider retention settings and data-minimization controls before sending any real data to an LLM. Pattern-based masking and the local SHA-256 chain are not substitutes for these controls or a compliance program.

CI runs the test suite, `detect-secrets` against tracked files, Bandit, `pip-audit`, and `npm audit`. Review `.secrets.baseline` before approving any baseline additions; enable GitHub secret scanning and push protection as an additional repository control.

---

## Architecture Overview

```
Customer Request (Web / API)
       │
       ▼
 [PII Sanitizer]            <-- Masks patterns in the customer message
       │
       ▼
[Supervisor Orchestrator]   <-- Groq (Llama/GPT-OSS), Gemini, or Claude tool-calling
       │
       ├──► CustomerProfileAgent   --> SQLite Core Data Layer
       ├──► FraudReviewAgent       --> Deterministic control-evasion signal screening
       ├──► PolicyComplianceAgent  --> Deterministic Rules Engine (YAML) + Vector RAG
       ├──► NegotiationAgent       --> Computes optimal terms within hard policy bounds
       │
    Decision Gate:
       ├── [Within Bounds] ───────► ExecutionAgent
       │                                  ├── Balanced Double-Entry Journal (Debits == Credits)
       │                                  └── SHA-256 Chained Audit Ledger
       │
       └── [Policy Exception] ────► EscalationAgent
                                          └── Asynchronous HITL Underwriter Cockpit
                                                (Approve / Override / Reject + Auto-Execute)
```

### Core Architecture Highlights

1. **Deterministic Policy Checks**: The LLM orchestrates tools; policy limits and eligibility decisions are evaluated by Python rules using YAML policy data in `data/policies/*.yaml`.
2. **PII Pattern Masking**: The customer message is passed through a pattern-based sanitizer before it is sent to the LLM provider. It is a demo safeguard, not comprehensive PII detection or a compliance control.
3. **Tamper-Evident Audit Chain**: Action records are linked using SHA-256 hashes. The verification endpoint checks returned ledger records for changes that break the chain; this does not protect against a privileged actor rewriting and recomputing the ledger.
4. **Double-Entry General Ledger (GL)**: Financial actions (fee waivers, retention credits) produce balanced double-entry accounting journals adhering to $\sum \text{Debits} == \sum \text{Credits}$.
5. **Human-in-the-Loop (HITL) Escalation Queue**: Policy exceptions enter a stateful queue (`ESC-...`), enabling underwriters and relationship managers to inspect customer risk profiles, override terms with regulatory notes, and trigger downstream execution.
6. **API Request Idempotency**: Header `Idempotency-Key` prevents duplicate transaction processing or double-waivers during network retries. Reusing a key with a different request returns HTTP 409.
7. **Adversarial Policy Tests**: Deterministic policy tests cover requests such as excessive waivers, delinquency, high utilization, and attempts to bypass underwriting. They do not measure an LLM's general prompt-injection resistance.
8. **Fraud-review triage**: A deterministic text screen flags explicit policy-evasion, audit-concealment, or authority-impersonation cues for human review. Flags are not fraud findings; the execution path repeats the screen before any action, and only a human reviewer can resolve an escalation.

---

## Offline Evaluation

Run the offline regression suite with:

```bash
python scripts/run_evals.py
```

The runner executes pytest without requiring live LLM credentials and reports test counts from pytest's JUnit report. Tests cover policy evaluation, tool dispatch, sanitization, audit-chain verification, accounting, API behavior, and HITL workflows. Results depend on the current test run; no fixed benchmark scores are presented.

---

## Interactive Dashboard

The dashboard provides three workflows:
* **Customer intake**: Submit sample requests, inspect policy citations, and view agent trace steps.
* **Underwriter review (HITL)**: Review pending escalations and approve, override, or reject requests with notes.
* **Audit ledger**: Inspect recorded actions and verify the SHA-256 hash chain.

Run the web interface:
```bash
uvicorn app.main:app --reload
```
Open **http://localhost:8000/**.

---

## API Surface

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `GET` | `/api/auth/config` | Public, non-secret configuration used to initialize local-key mode or Entra MSAL sign-in. |
| `POST` | `/api/decide` | Evaluates request with supervisor (supports `Idempotency-Key`; key reuse with a different request returns HTTP 409). |
| `GET` | `/api/escalations` | Lists pending escalations in the HITL underwriter queue. |
| `GET` | `/api/escalations/{case_id}` | Retrieves full context and risk flags for an escalated case. |
| `POST` | `/api/escalations/{case_id}/review` | Approves, rejects, or overrides an escalated case with audit trail. |
| `GET` | `/api/audit/verify` | Verifies the returned audit records against the SHA-256 hash chain. |
| `GET` | `/api/audit/ledger` | Returns audit records linked by the SHA-256 hash chain. |
| `GET` | `/api/accounting/ledger` | Inspects balanced double-entry General Ledger journal records. |
| `GET` | `/api/customers` | Populates customer selector. |
| `GET` | `/api/health` | Health check endpoint. |

---

## Setup & Testing

```bash
# 1. Clone & activate virtual environment
git clone https://github.com/smit080105/bankmind-agent.git
cd bankmind-agent
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 2. Install dependencies
pip install -r requirements.txt
pip install -r requirements-dev.txt
npm ci
npm run build:frontend

# 3. Configure environment (PowerShell: Copy-Item .env.example .env)
cp .env.example .env
# Set LLM_PROVIDER and the provider API key. For local demo, set
# AUTH_MODE=api_key and BANKMIND_API_KEY. For Entra, set AUTH_MODE=entra
# and the ENTRA_* values above.

# 4. Initialize database
python scripts/init_db.py

# 5. Run test suite (deterministic, runs offline with zero LLM API costs)
pytest tests/ -v
```

---

## License

MIT License. See [LICENSE](LICENSE) for details.
