"""The Supervisor agent, backed by Claude (Anthropic tool-use).

Orchestrates the specialist agents through Claude tool-calling, then packages
the outcome into a `Decision` with a full reasoning trace for audit.
"""
import json

from anthropic import Anthropic

from app.config import ANTHROPIC_API_KEY, ANTHROPIC_MODEL
from app.models import Decision, DecisionRequest, TraceStep
from app.tools import TOOLS, dispatch
from app.agents.supervisor_common import (
    SYSTEM_PROMPT,
    customer_request_text,
    agent_for_tool,
)


def handle_request(req: DecisionRequest, max_turns: int = 8) -> Decision:
    if not ANTHROPIC_API_KEY:
        raise RuntimeError(
            "ANTHROPIC_API_KEY is not set. Add it to .env, or set "
            "LLM_PROVIDER=gemini to use the free tier instead."
        )

    client = Anthropic(api_key=ANTHROPIC_API_KEY)
    messages = [{"role": "user", "content": customer_request_text(req)}]
    trace: list[TraceStep] = []
    citations: set[str] = set()
    outcome = "denied"
    terms: dict = {}

    for _ in range(max_turns):
        response = client.messages.create(
            model=ANTHROPIC_MODEL,
            max_tokens=1500,
            system=SYSTEM_PROMPT,
            tools=TOOLS,
            messages=messages,
        )

        tool_use_blocks = [b for b in response.content if b.type == "tool_use"]

        if not tool_use_blocks:
            final_text = "".join(
                b.text for b in response.content if b.type == "text"
            )
            return Decision(
                customer_id=req.customer_id,
                request_type=req.request_type,
                outcome=outcome,
                terms=terms,
                reasoning=final_text,
                policy_citations=sorted(citations),
                trace=trace,
            )

        messages.append({"role": "assistant", "content": response.content})
        tool_results = []

        for block in tool_use_blocks:
            result = dispatch(block.name, block.input)

            trace.append(TraceStep(
                agent=agent_for_tool(block.name),
                action=block.name,
                detail=json.dumps(block.input)[:300],
            ))

            if block.name == "escalate_case":
                outcome = "escalated"
            elif block.name == "execute_action":
                outcome = "approved"
                terms = result

            if isinstance(result, dict) and result.get("citations"):
                citations.update(result["citations"])

            tool_results.append({
                "type": "tool_result",
                "tool_use_id": block.id,
                "content": json.dumps(result, default=str),
            })

        messages.append({"role": "user", "content": tool_results})

    return Decision(
        customer_id=req.customer_id,
        request_type=req.request_type,
        outcome="escalated",
        terms=terms,
        reasoning="Reached maximum reasoning turns without a resolved outcome; "
                  "escalating for manual review as a safety fallback.",
        policy_citations=sorted(citations),
        trace=trace,
    )
