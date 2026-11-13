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
- Added configurable API-key protection, restrictive CORS defaults, bounded inputs, safer API error handling, and atomic one-time escalation review.

These are project features, not measured production outcomes. Adjust the wording to match your contribution and verify details before using them on a resume.

## Scope and limitations

This is a local portfolio demonstration using synthetic sample data. It is not a banking service and must not be used for real customer data, financial decisions, or transactions. PII masking uses patterns and is not comprehensive or a substitute for a reviewed data-protection program. The hash chain is tamper-evident for verified records, but is not an immutable or independently anchored audit system. The application does not implement production authentication or authorization and makes no regulatory-compliance claim.

The customer-facing agent is an AI relationship-manager assistant, not a human bank manager. It is designed to explain supported workflow outcomes clearly, apply the demo's deterministic rules, and route exceptions for human review. The numeric limits in the policy files are illustrative portfolio settings, not claims about universal banking practice or regulatory standards. A real institution must set and validate its own jurisdiction-specific policies, customer-fairness controls, approval authority, disclosures, and complaint-handling process with qualified compliance and legal teams before deployment.

## Security configuration

- Set `BANKMIND_API_KEY` to a unique, high-entropy secret of at least 32 characters before exposing the service. When configured, all `/api/*` routes except `/api/health` require `Authorization: Bearer <key>`. The dashboard accepts the key in its header and keeps it in tab-scoped `sessionStorage`.
- If the key is unset, authentication is disabled for local development and the server logs a warning. Docker Compose refuses to start without the key. Do not expose an unauthenticated development instance to a network.
- `CORS_ALLOWED_ORIGINS` is a comma-separated allowlist; it defaults to the two local dashboard origins rather than `*`.
- Request sizes/values and human override fields are validated, unexpected decision failures are logged server-side rather than returned to clients, and an escalation can transition out of `pending` only once.
- Each LLM tool call is bound to the original request/customer. The execution dispatcher recomputes policy against database state immediately before writing an action; model-provided policy results are not treated as execution authorization.
- The dashboard/API-key flow is intended for a local portfolio demo. Use HTTPS and a real identity provider, role-based authorization, secret management, persistent rate limiting, and independently protected audit storage before any shared or production deployment. PII masking and the SHA-256 chain do not provide compliance or production data security.

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

# 3. Configure environment (PowerShell: Copy-Item .env.example .env)
cp .env.example .env
# Set LLM_PROVIDER (groq recommended for free tier), provider API key, and
# BANKMIND_API_KEY (generate with: python -c "import secrets; print(secrets.token_urlsafe(32))")

# 4. Initialize database
python scripts/init_db.py

# 5. Run test suite (deterministic, runs offline with zero LLM API costs)
pytest tests/ -v
```

---

## License

MIT License. See [LICENSE](LICENSE) for details.
