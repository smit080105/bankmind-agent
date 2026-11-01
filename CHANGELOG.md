# Changelog

## Phase 3 — HITL & Audit Demonstration
- **Pattern-based PII masking (`app/security/sanitizer.py`)**: Added reversible masking for selected identifier patterns before LLM processing. This is a demo safeguard, not comprehensive detection or PCI-DSS compliance.
- **Tamper-evident audit chain (`app/security/audit.py`)**: Linked action records with SHA-256 hashes and added a verification endpoint (`/api/audit/verify`). The hash chain is not immutable or independently anchored.
- **Human-in-the-Loop (HITL) Queue & Cockpit**: Added asynchronous underwriter escalation queue (`/api/escalations`) and review mechanism (`/api/escalations/{case_id}/review`) allowing human officers to approve, override, or reject exceptions with auto-execution.
- **Double-Entry General Ledger (`app/accounting/ledger.py`)**: Integrated financial accounting primitives enforcing $\sum \text{Debits} == \sum \text{Credits}$ for all fee waivers and retention credits.
- **API Request Idempotency**: Added `Idempotency-Key` header handling on `/api/decide` to prevent duplicate fee waivers and execution replays.
- **Deterministic policy-boundary tests (`tests/test_red_teaming.py`)**: Added 10 synthetic scenarios that check selected policy limits and escalation behavior. They do not measure general prompt-injection resistance.
- **Offline test runner (`scripts/run_evals.py`)**: Added a runner for the local pytest suite and its test-count report.
- **Three-Portal Dashboard UI**: Upgraded frontend with Customer Intake Terminal, Underwriter Cockpit, and Cryptographic Audit Inspector.

## Phase 2
- Vector RAG: replaced Phase 1's keyword-count retrieval with TF-IDF + cosine similarity over policy documents (`app/rag.py`).
- Retention offers: added `data/policies/retention_offer.yaml` with automatic escalation for full exits and delinquency.
- Multi-provider support: added Groq as third free LLM provider.
- Test suite & CI: added pytest suite and GitHub Actions workflow.

## Phase 1
- Initial architecture: SQLite customer data, deterministic policy engine, specialized agent dispatch, and ledger-console dashboard.
