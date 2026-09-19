# Changelog

## Phase 2
- Vector RAG: replaced Phase 1's keyword-count retrieval with TF-IDF +
  cosine similarity over policy documents (`app/rag.py`), computed locally
  via scikit-learn — no embedding API or vector DB required.
- New request type: retention offers, for customers threatening to leave
  for a competitor. Tier-capped credit, automatic escalation for full
  account exits, low tenure, or active delinquency.
- Added Groq as a third LLM provider (free, no card required) after
  Google's AI Studio "AQ." key format hit a widespread, unresolved auth
  bug on the standard Gemini API.
- Fixed a bug where a malformed tool call from the LLM could crash the
  whole request; `dispatch()` now catches and returns a clean error.
- Added a full pytest suite (policy engine, RAG, tool dispatch, and the
  FastAPI surface) plus GitHub Actions CI, an MIT license, and
  `.gitattributes` line-ending normalization.
- Fixed `main.py` only catching `RuntimeError`, which let unexpected
  provider-SDK errors surface as blank, undetailed 500s; now all
  exceptions are logged server-side and returned with a real message.
- Modernized FastAPI startup from the deprecated `on_event` decorator to
  the `lifespan` context manager.
- Added Docker support (`Dockerfile`, `docker-compose.yml`) for running
  the API + dashboard in a container.

## Phase 1
- Initial architecture: SQLite customer data, a deterministic policy
  engine (loan negotiation, fee waivers, credit limit increases), keyword
  RAG over policy docs, five specialized agents orchestrated by a
  Supervisor via LLM tool-calling (Anthropic, then Gemini added), a CLI,
  a FastAPI backend, and the ledger-console dashboard.
