# bankmind-agent

![Tests](https://github.com/smit080105/bankmind-agent/actions/workflows/tests.yml/badge.svg)
![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)
![Python 3.12](https://img.shields.io/badge/python-3.12-blue.svg)

An agentic AI banking supervisor that uses customer data, RAG, specialized agents,
policy constraints, and tool calling to provide personalized banking decisions,
negotiate offers, execute actions, and escalate exceptional cases.

## Phase 1 scope

Phase 1 builds the **foundational architecture** — everything later phases plug into:

1. **Mock customer data layer** (SQLite) — customers, accounts, loans, transactions,
   credit tiers, relationship history.
2. **Deterministic policy engine** — hardcoded banking rules (rate floors, discount
   caps by tier, fee-waiver limits, escalation thresholds) that no agent is allowed
   to negotiate past. Rules live in `data/policies/*.yaml` so they're editable
   without touching code.
3. **Lightweight RAG** over policy documents (`data/policies/*.md`) so agents can
   cite *why* a decision was made, not just *what* the decision was.
4. **Specialized agents**, each a focused tool-using unit:
   - `CustomerProfileAgent` — pulls and summarizes a customer's full picture.
   - `PolicyComplianceAgent` — validates any proposed action against the rules engine + RAG.
   - `NegotiationAgent` — computes the best offer within policy bounds given the
     customer's ask.
   - `ExecutionAgent` — "executes" an approved action (mocked — logs a ledger entry).
   - `EscalationAgent` — flags anything outside agent authority for a human.
5. **Supervisor agent** — the orchestrator. Takes a request, routes it through the
   right specialists using Claude tool-calling, and returns a final decision with
   a full reasoning trace (for audit — required in banking).
6. **FastAPI surface** — one endpoint (`POST /decide`) plus a CLI runner so you can
   test end-to-end without a frontend yet.

### What's deliberately NOT in Phase 1
- No real core-banking integration (execution is mocked/logged).
- No auth/session layer.
- No frontend (this becomes the API your dashboard will call in a later phase).
- RAG is simple keyword+embedding retrieval over local markdown, not a vector DB —
  swap in Postgres+pgvector or a hosted vector store later; the `rag.py` interface
  is written so that swap doesn't touch agent code.

## Architecture

```
Customer request
      |
      v
 SupervisorAgent  <-- orchestrates via Claude tool-calling
      |
      +--> CustomerProfileAgent  --> SQLite (customers.db)
      |
      +--> PolicyComplianceAgent --> policy_engine.py (hard rules)
      |                          --> rag.py (policy doc lookup)
      |
      +--> NegotiationAgent      --> computes offer within bounds
      |
      +--> ExecutionAgent        --> mocked action + ledger log
      |
      +--> EscalationAgent       --> flags for human review
      |
      v
 Decision object (action, terms, reasoning trace, policy citations)
```

The Supervisor never lets the LLM freelance on numbers. `NegotiationAgent` computes
bounds deterministically from `policy_engine.py`; the LLM chooses *among* policy-
compliant options and explains the reasoning — it cannot output a rate or waiver
the engine hasn't pre-approved as a valid range.

## LLM provider

The Supervisor's LLM backend is swappable via `LLM_PROVIDER` in `.env`:

- **`gemini`** (default) — free tier, no card required. Get a key at
  https://aistudio.google.com/apikey. Uses the current `google-genai` SDK
  (NOT the deprecated `google-generativeai` package).
- **`anthropic`** — needs paid API credits at
  https://console.anthropic.com/settings/billing.

Everything else (policy engine, RAG, database, FastAPI, CLI) is identical
either way — `app/agents/supervisor.py` just dispatches to
`supervisor_gemini.py` or `supervisor_anthropic.py` based on the setting.

## Setup

```bash
python3 -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env            # set LLM_PROVIDER and the matching API key
python scripts/init_db.py       # creates + seeds data/customers.db
```

## Run

**Dashboard (recommended — a real UI):**
```bash
uvicorn app.main:app --reload
```
Open **http://localhost:8000/** — a ledger-style console where you pick a
customer, describe the request (or click a sample), and see the supervisor's
decision: outcome stamp, reasoning, terms, cited policy passages, and the
full agent trace. The API it calls lives under `/api/*`
(`/api/decide`, `/api/customers`, `/api/health`); Swagger docs are still at
`/docs` if you want to hit the API directly.

**CLI (no browser needed):**
```bash
python scripts/run_cli.py
```

## Testing

The deterministic core — policy engine, RAG retrieval, and the tool
dispatcher (including the Anthropic/Gemini schema conversion) — is covered
by pytest. These tests never call an LLM, so they run offline and free:

```bash
pip install -r requirements-dev.txt
pytest tests/ -v
```

CI runs this same suite on every push via GitHub Actions
(`.github/workflows/tests.yml`).

## Next phases (not built yet)
- Phase 2: swap keyword RAG for embeddings + vector store, add more request types
  (overdraft waiver, credit limit increase, retention offers).
- Phase 3: real core-banking connector behind `ExecutionAgent`, auth, audit log
  persistence, human-in-the-loop escalation queue (ties into the dashboard pattern
  from the IoT project).
- Phase 4: frontend dashboard for relationship managers to review agent decisions.
