# bankmind-agent

![Tests](https://github.com/smit080105/bankmind-agent/actions/workflows/tests.yml/badge.svg)
![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)
![Python 3.12](https://img.shields.io/badge/python-3.12-blue.svg)
![Audit: SHA--256 Chained](https://img.shields.io/badge/audit-SHA--256%20chained-success.svg)
![Security: PCI--DSS Redacted](https://img.shields.io/badge/security-PII%20sanitized-brightgreen.svg)

An enterprise-grade agentic AI banking supervisor that couples **deterministic policy engines** with **LLM orchestration** to deliver personalized banking terms, execute balanced double-entry financial transactions, manage human-in-the-loop (HITL) escalations, and cryptographically audit every decision.

---

## Architecture & Enterprise Design

```
Customer Request (Web / API)
       │
       ▼
 [PII & PCI-DSS Sanitizer]  <-- Tokenizes card numbers, accounts, emails, phone numbers
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
       │                                  └── Cryptographic SHA-256 Chained Audit Ledger
       │
       └── [Policy Exception] ────► EscalationAgent
                                          └── Asynchronous HITL Underwriter Cockpit
                                                (Approve / Override / Reject + Auto-Execute)
```

### Core Architecture Highlights

1. **Zero Hallucination of Financial Terms**: The LLM is an orchestrator and customer-facing relationship manager, *never* an arithmetic calculator. Interest rates, fee caps, and credit limits are computed deterministically via YAML rules in `data/policies/*.yaml`.
2. **FinTech Security & PCI-DSS/PII Masking**: Pre-LLM sanitization proxy tokenizes sensitive identifiers (`[CARD_TOKEN_1]`, `[ACCOUNT_TOKEN_1]`) so raw financial data is never leaked to external AI providers.
3. **Cryptographically Chained Audit Ledger**: Every action is hashed using SHA-256 chained to the preceding block ($\text{Hash}_n = \text{SHA256}(\text{Hash}_{n-1} + \dots)$). Any manual database tampering breaks the cryptographic chain and is detected instantly.
4. **Double-Entry General Ledger (GL)**: Financial actions (fee waivers, retention credits) produce balanced double-entry accounting journals adhering to $\sum \text{Debits} == \sum \text{Credits}$.
5. **Human-in-the-Loop (HITL) Escalation Queue**: Policy exceptions enter a stateful queue (`ESC-...`), enabling underwriters and relationship managers to inspect customer risk profiles, override terms with regulatory notes, and trigger downstream execution.
6. **API Request Idempotency**: Header `Idempotency-Key` prevents duplicate transaction processing or double-waivers during network retries.
7. **Adversarial Red-Teaming Benchmark**: Hardened against prompt injection, roleplay spoofing, active delinquency concealment, and authority escalation.

---

## Enterprise Benchmark & Evals

BankMind includes an automated evaluation benchmark (`scripts/run_evals.py`):

```bash
python scripts/run_evals.py
```

| Benchmark Metric | Result | Target | Verification Method |
| :--- | :--- | :--- | :--- |
| **Policy Adherence Rate** | **100.0%** | 100% | Zero financial term generation without policy approval |
| **Adversarial Jailbreak Resistance** | **100.0%** | 100% | 10/10 Prompt injection and social engineering attacks blocked |
| **Audit Ledger Cryptographic Integrity** | **VERIFIED** | 100% | SHA-256 hash-chain validation across all ledger blocks |
| **PII & PCI-DSS Tokenization** | **VERIFIED** | 100% | Bi-directional card, account, email, and phone masking |
| **Double-Entry GL Balancing** | **VERIFIED** | 100% | Strict enforcement: $\sum \text{Debits} == \sum \text{Credits}$ |
| **Request Idempotency Replay Safety** | **VERIFIED** | 100% | Cached zero-redundancy response on identical keys |

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
| `GET` | `/api/audit/verify` | Cryptographically verifies the SHA-256 audit ledger hash chain. |
| `GET` | `/api/audit/ledger` | Returns immutable audit blocks. |
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
