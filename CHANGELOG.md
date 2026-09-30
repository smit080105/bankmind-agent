# Changelog

## Phase 3 — Enterprise Hardening, HITL & Cryptographic Audit
- **FinTech Security Layer (`app/security/sanitizer.py`)**: Added bidirectional PII and PCI-DSS data sanitizer that automatically masks card numbers, account numbers, emails, and phone numbers before LLM processing.
- **Cryptographic Audit Ledger (`app/security/audit.py`)**: Upgraded `action_ledger` to an immutable SHA-256 hash-chained ledger ($\text{Hash}_n = \text{SHA256}(\text{Hash}_{n-1} + \dots)$) with automated tamper-detection endpoint (`/api/audit/verify`).
- **Human-in-the-Loop (HITL) Queue & Cockpit**: Added asynchronous underwriter escalation queue (`/api/escalations`) and review mechanism (`/api/escalations/{case_id}/review`) allowing human officers to approve, override, or reject exceptions with auto-execution.
- **Double-Entry General Ledger (`app/accounting/ledger.py`)**: Integrated financial accounting primitives enforcing $\sum \text{Debits} == \sum \text{Credits}$ for all fee waivers and retention credits.
- **API Request Idempotency**: Added `Idempotency-Key` header handling on `/api/decide` to prevent duplicate fee waivers and execution replays.
- **Adversarial Red-Teaming Benchmark (`tests/test_red_teaming.py`)**: Added 10-scenario red-teaming test suite verifying 100% defense against prompt injection, roleplay spoofing, and policy circumvention.
- **Automated Evals Runner (`scripts/run_evals.py`)**: Standalone scorecard script executing the offline benchmark suite and generating an enterprise metrics report.
- **Three-Portal Dashboard UI**: Upgraded frontend with Customer Intake Terminal, Underwriter Cockpit, and Cryptographic Audit Inspector.

## Phase 2
- Vector RAG: replaced Phase 1's keyword-count retrieval with TF-IDF + cosine similarity over policy documents (`app/rag.py`).
- Retention offers: added `data/policies/retention_offer.yaml` with automatic escalation for full exits and delinquency.
- Multi-provider support: added Groq as third free LLM provider.
- Test suite & CI: added pytest suite and GitHub Actions workflow.

## Phase 1
- Initial architecture: SQLite customer data, deterministic policy engine, specialized agent dispatch, and ledger-console dashboard.
