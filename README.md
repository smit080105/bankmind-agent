# bankmind-agent

![Tests](https://github.com/smit080105/bankmind-agent/actions/workflows/tests.yml/badge.svg)
![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)
![Python 3.12](https://img.shields.io/badge/python-3.12-blue.svg)
![Audit: SHA--256 Chained](https://img.shields.io/badge/audit-SHA--256%20chained-success.svg)
![Security: PII Sanitization](https://img.shields.io/badge/security-PII%20sanitization-brightgreen.svg)

A portfolio project demonstrating an agentic banking workflow that combines **deterministic policy checks** with **LLM orchestration** to evaluate requests, manage human-in-the-loop (HITL) escalations, record double-entry transactions, and maintain a tamper-evident audit chain.

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
2. **PII Sanitization**: The customer message is sanitized before it is sent to the LLM provider. This is a project-level safeguard, not a claim of PCI-DSS compliance.
3. **Tamper-Evident Audit Chain**: Action records are linked using SHA-256 hashes. The verification endpoint checks returned ledger records for changes that break the chain.
4. **Double-Entry General Ledger (GL)**: Financial actions (fee waivers, retention credits) produce balanced double-entry accounting journals adhering to $\sum \text{Debits} == \sum \text{Credits}$.
5. **Human-in-the-Loop (HITL) Escalation Queue**: Policy exceptions enter a stateful queue (`ESC-...`), enabling underwriters and relationship managers to inspect customer risk profiles, override terms with regulatory notes, and trigger downstream execution.
6. **API Request Idempotency**: Header `Idempotency-Key` prevents duplicate transaction processing or double-waivers during network retries.
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

The dashboard provides three specialized portals:
* 🏛️ **Customer Intake Terminal**: Submit requests, test with realistic customer profiles, inspect policy citations, and view live trace steps.
* 🛡️ **Underwriter Cockpit (HITL)**: Review pending escalations, inspect customer risk context, and approve, override, or reject with audit justifications.
* 🔐 **Cryptographic Audit Inspector**: View transaction blocks and verify SHA-256 cryptographic chain integrity with one click.

Run the web interface:
```bash
uvicorn app.main:app --reload
```
Open **http://localhost:8000/**.

---

## API Surface

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `POST` | `/api/decide` | Evaluates request with supervisor (supports `Idempotency-Key`). |
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

# 3. Configure environment
cp .env.example .env
# Set LLM_PROVIDER (groq recommended for free tier) and API key

# 4. Initialize database
python scripts/init_db.py

# 5. Run test suite (deterministic, runs offline with zero LLM API costs)
pytest tests/ -v
```

---

## License

MIT License. See [LICENSE](LICENSE) for details.
