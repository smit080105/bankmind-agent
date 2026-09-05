"""Public entry point for the Supervisor agent.

Everything else in the app (`main.py`, `scripts/run_cli.py`) calls
`supervisor.handle_request(req)` and never needs to know which LLM is behind
it. Which provider is used is controlled by `LLM_PROVIDER` in `.env`:
  - "gemini"    (default) — free tier, via google-genai.
  - "anthropic" — needs paid API credits, via the Anthropic SDK.
"""
from app.config import LLM_PROVIDER
from app.models import Decision, DecisionRequest


def handle_request(req: DecisionRequest, max_turns: int = 8) -> Decision:
    if LLM_PROVIDER == "anthropic":
        from app.agents import supervisor_anthropic
        return supervisor_anthropic.handle_request(req, max_turns=max_turns)

    if LLM_PROVIDER == "gemini":
        from app.agents import supervisor_gemini
        return supervisor_gemini.handle_request(req, max_turns=max_turns)

    raise RuntimeError(
        f"Unknown LLM_PROVIDER '{LLM_PROVIDER}' in .env — use 'gemini' or 'anthropic'."
    )
