"""The Supervisor agent, backed by Groq.

Groq's API is OpenAI-compatible: tool calls come back as
`message.tool_calls`, each with a `.function.arguments` string that must be
JSON-decoded (unlike Anthropic, which hands back an already-parsed dict).
Otherwise this loop is structurally identical to the Anthropic and Gemini
implementations, which matters for auditability — all three providers must
produce the same shape of reasoning trace.
"""
import json

from groq import Groq

from app.config import GROQ_API_KEY, GROQ_MODEL
from app.models import Decision, DecisionRequest, TraceStep
from app.tools import GROQ_TOOLS, dispatch
from app.agents.supervisor_common import (
    SYSTEM_PROMPT,
    customer_request_text,
    agent_for_tool,
)


def handle_request(req: DecisionRequest, max_turns: int = 8) -> Decision:
    if not GROQ_API_KEY:
        raise RuntimeError(
            "GROQ_API_KEY is not set. Get a free key (no card required) at "
            "https://console.groq.com/keys and add it to .env."
        )

    client = Groq(api_key=GROQ_API_KEY)
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": customer_request_text(req)},
    ]
    trace: list[TraceStep] = []
    citations: set[str] = set()
    outcome = "denied"
    terms: dict = {}

    for _ in range(max_turns):
        response = client.chat.completions.create(
            model=GROQ_MODEL,
            max_tokens=1500,
            messages=messages,
            tools=GROQ_TOOLS,
            tool_choice="auto",
        )

        message = response.choices[0].message
        tool_calls = message.tool_calls or []

        if not tool_calls:
            final_text = message.content or "(no response text)"
            return Decision(
                customer_id=req.customer_id,
                request_type=req.request_type,
                outcome=outcome,
                terms=terms,
                reasoning=final_text,
                policy_citations=sorted(citations),
                trace=trace,
            )

        # Echo the assistant's turn (including its tool_calls) back into the
        # conversation before appending tool results — required for
        # multi-turn tool calling, same as the other two providers.
        messages.append(message.model_dump(exclude_unset=True))

        for tool_call in tool_calls:
            try:
                tool_input = json.loads(tool_call.function.arguments)
            except json.JSONDecodeError as e:
                tool_input = {}
                result = {"error": f"Malformed tool arguments JSON: {e}"}
            else:
                result = dispatch(tool_call.function.name, tool_input)

            trace.append(TraceStep(
                agent=agent_for_tool(tool_call.function.name),
                action=tool_call.function.name,
                detail=json.dumps(tool_input)[:300],
            ))

            if tool_call.function.name == "escalate_case":
                outcome = "escalated"
            elif tool_call.function.name == "execute_action":
                outcome = "approved"
                terms = result

            if isinstance(result, dict) and result.get("citations"):
                citations.update(result["citations"])

            messages.append({
                "role": "tool",
                "tool_call_id": tool_call.id,
                "content": json.dumps(result, default=str),
            })

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
