"""The Supervisor agent, backed by Gemini via the current `google-genai` SDK
(NOT the deprecated `google-generativeai` package).

Manual (non-automatic) function calling is used deliberately: automatic
function calling in this SDK expects plain Python callables with type-hinted
signatures, which doesn't fit our tool functions (they take a single dict
built from the agent-layer results). Driving the loop by hand also keeps
this implementation structurally identical to the Anthropic one, which
matters for auditability — both providers must produce the same shape of
reasoning trace.
"""
import json

from google import genai
from google.genai import types

from app.config import GEMINI_API_KEY, GEMINI_MODEL
from app.models import Decision, DecisionRequest, TraceStep
from app.tools import GEMINI_TOOLS, dispatch
from app.agents.supervisor_common import (
    SYSTEM_PROMPT,
    customer_request_text,
    agent_for_tool,
)


def _build_tool() -> types.Tool:
    declarations = [
        types.FunctionDeclaration(
            name=t["name"],
            description=t["description"],
            parameters=t["input_schema"],
        )
        for t in GEMINI_TOOLS
    ]
    return types.Tool(function_declarations=declarations)


def _json_safe(obj):
    """Round-trips through json.dumps(default=str) so datetimes etc. don't
    break the function_response payload, which must be a plain dict."""
    return json.loads(json.dumps(obj, default=str))


def handle_request(req: DecisionRequest, max_turns: int = 8) -> Decision:
    if not GEMINI_API_KEY:
        raise RuntimeError(
            "GEMINI_API_KEY is not set. Get a free key at "
            "https://aistudio.google.com/apikey and add it to .env."
        )

    client = genai.Client(api_key=GEMINI_API_KEY)
    tool = _build_tool()
    config = types.GenerateContentConfig(
        system_instruction=SYSTEM_PROMPT,
        tools=[tool],
        automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
    )

    contents: list[types.Content] = [
        types.Content(role="user", parts=[types.Part.from_text(text=customer_request_text(req))])
    ]

    trace: list[TraceStep] = []
    citations: set[str] = set()
    outcome = "denied"
    terms: dict = {}

    for _ in range(max_turns):
        response = client.models.generate_content(
            model=GEMINI_MODEL,
            contents=contents,
            config=config,
        )

        candidate = response.candidates[0]
        parts = candidate.content.parts or []
        function_calls = [p.function_call for p in parts if p.function_call]

        if not function_calls:
            final_text = "".join(p.text for p in parts if p.text) or "(no response text)"
            return Decision(
                customer_id=req.customer_id,
                request_type=req.request_type,
                outcome=outcome,
                terms=terms,
                reasoning=final_text,
                policy_citations=sorted(citations),
                trace=trace,
            )

        # Echo the model's turn (including its function_call parts) back into
        # the conversation before appending our function_response parts —
        # Gemini's multi-turn function calling requires this, same as
        # Anthropic requires echoing the assistant's tool_use blocks.
        contents.append(candidate.content)

        response_parts = []
        for fc in function_calls:
            tool_input = dict(fc.args) if fc.args else {}
            result = dispatch(fc.name, tool_input)

            trace.append(TraceStep(
                agent=agent_for_tool(fc.name),
                action=fc.name,
                detail=json.dumps(_json_safe(tool_input))[:300],
            ))

            if fc.name == "escalate_case":
                outcome = "escalated"
            elif fc.name == "execute_action":
                outcome = "approved"
                terms = result

            if isinstance(result, dict) and result.get("citations"):
                citations.update(result["citations"])

            response_parts.append(
                types.Part.from_function_response(
                    name=fc.name,
                    response={"result": _json_safe(result)},
                )
            )

        contents.append(types.Content(role="user", parts=response_parts))

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
