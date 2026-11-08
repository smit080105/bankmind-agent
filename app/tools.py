"""Tool schemas and the dispatcher that maps a tool call to the underlying
agent function.

Two schema flavors are exported from the same source of truth (TOOLS, in
Anthropic tool-use format):
  - TOOLS         — used as-is by the Anthropic supervisor.
  - GEMINI_TOOLS  — a converted copy for the Gemini supervisor. Gemini's
    function-calling schema doesn't reliably support open-ended/free-form
    objects, so pass-through object fields (an entire policy evaluation,
    an entire action's params) are represented as JSON-encoded strings
    instead. `dispatch()` transparently decodes those before use, so the
    agent functions never know or care which LLM produced the call.

Keeping this separate from the supervisor modules keeps the orchestration
loops readable and makes it trivial to add a new tool: define the schema
once here, add one line to `dispatch()`.
"""
import copy
import json
import math

from app.agents import (
    customer_profile_agent,
    policy_agent,
    negotiation_agent,
    execution_agent,
    escalation_agent,
)
from app.models import DecisionRequest, RequestType

TOOLS = [
    {
        "name": "get_customer_profile",
        "description": (
            "Fetch a customer's full profile: tier, credit score, account status, "
            "accounts, and loans. Always call this first for any request."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "customer_id": {"type": "string"},
            },
            "required": ["customer_id"],
        },
    },
    {
        "name": "check_loan_negotiation_policy",
        "description": (
            "Evaluate a loan rate negotiation request against hard policy bounds. "
            "Returns the allowed floor rate, whether it's within agent authority, "
            "and cited policy passages. Call before offering any rate."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "customer_id": {"type": "string"},
                "loan_id": {"type": "string", "description": "Optional loan id if known."},
                "requested_rate": {"type": "number", "description": "The rate the customer is asking for, if stated."},
            },
            "required": ["customer_id"],
        },
    },
    {
        "name": "negotiate_loan_rate",
        "description": (
            "Given a policy evaluation (from check_loan_negotiation_policy), compute "
            "the concrete offered rate. Only call after check_loan_negotiation_policy."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "evaluation": {"type": "object", "description": "The full object returned by check_loan_negotiation_policy."},
            },
            "required": ["evaluation"],
        },
    },
    {
        "name": "check_fee_waiver_policy",
        "description": "Evaluate a fee waiver request against hard policy bounds.",
        "input_schema": {
            "type": "object",
            "properties": {
                "customer_id": {"type": "string"},
                "fee_type": {"type": "string", "description": "e.g. overdraft, late_payment, atm"},
                "amount": {"type": "number"},
            },
            "required": ["customer_id", "fee_type", "amount"],
        },
    },
    {
        "name": "negotiate_fee_waiver",
        "description": "Compute the concrete waiver amount from a fee waiver policy evaluation.",
        "input_schema": {
            "type": "object",
            "properties": {
                "evaluation": {"type": "object"},
                "requested_amount": {"type": "number"},
            },
            "required": ["evaluation", "requested_amount"],
        },
    },
    {
        "name": "check_credit_limit_policy",
        "description": "Evaluate a credit limit / overdraft increase request against hard policy bounds.",
        "input_schema": {
            "type": "object",
            "properties": {
                "customer_id": {"type": "string"},
                "account_id": {"type": "string"},
                "requested_increase_pct": {"type": "number"},
                "is_temporary": {"type": "boolean"},
            },
            "required": ["customer_id", "account_id", "requested_increase_pct", "is_temporary"],
        },
    },
    {
        "name": "negotiate_credit_limit",
        "description": "Compute the concrete new credit limit from a credit limit policy evaluation.",
        "input_schema": {
            "type": "object",
            "properties": {
                "evaluation": {"type": "object"},
                "current_limit": {"type": "number"},
            },
            "required": ["evaluation", "current_limit"],
        },
    },
    {
        "name": "check_retention_offer_policy",
        "description": (
            "Evaluate a retention offer request against hard policy bounds — use this "
            "when a customer is threatening to close an account or leave for a "
            "competitor bank, as opposed to negotiating one product's terms."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "customer_id": {"type": "string"},
                "requested_credit": {
                    "type": "number",
                    "description": "The retention credit amount the customer wants or that seems needed to retain them, if known.",
                },
                "closing_all_accounts": {
                    "type": "boolean",
                    "description": "True if the customer is closing every account (full exit), not just one product.",
                },
            },
            "required": ["customer_id"],
        },
    },
    {
        "name": "negotiate_retention_offer",
        "description": "Compute the concrete retention credit from a retention offer policy evaluation.",
        "input_schema": {
            "type": "object",
            "properties": {
                "evaluation": {"type": "object"},
            },
            "required": ["evaluation"],
        },
    },
    {
        "name": "execute_action",
        "description": (
            "Execute an approved action and write it to the audit ledger. Only call "
            "this after a negotiate_* tool has returned offer_possible=true and you "
            "have decided to proceed."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "customer_id": {"type": "string"},
                "action_type": {
                    "type": "string",
                    "enum": ["loan_rate_change", "fee_waiver", "credit_limit_change", "retention_credit"],
                },
                "params": {
                    "type": "object",
                    "description": (
                        "loan_rate_change: {loan_id, new_rate}. "
                        "fee_waiver: {fee_type, amount}. "
                        "credit_limit_change: {account_id, new_limit, is_temporary}. "
                        "retention_credit: {credit_amount}."
                    ),
                },
            },
            "required": ["customer_id", "action_type", "params"],
        },
    },
    {
        "name": "escalate_case",
        "description": (
            "Escalate this case to a human because it falls outside agent authority. "
            "Call this whenever a check_*_policy tool returned within_agent_authority=false."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "customer_id": {"type": "string"},
                "request_type": {"type": "string"},
                "reasons": {"type": "array", "items": {"type": "string"}},
                "context": {"type": "object"},
            },
            "required": ["customer_id", "request_type", "reasons"],
        },
    },
]


# Tool name -> set of input field names that carry a whole nested object
# (a policy evaluation, an action's params, escalation context). Anthropic's
# tool-use schema is fine passing these through as untyped "object" — Gemini's
# schema is not, so for GEMINI_TOOLS these become JSON-encoded strings, and
# dispatch() decodes them back into dicts before calling the agent function.
_PASSTHROUGH_OBJECT_FIELDS = {
    "negotiate_loan_rate": {"evaluation"},
    "negotiate_fee_waiver": {"evaluation"},
    "negotiate_credit_limit": {"evaluation"},
    "negotiate_retention_offer": {"evaluation"},
    "execute_action": {"params"},
    "escalate_case": {"context"},
}


def _build_gemini_tools() -> list[dict]:
    """Deep-copies TOOLS and rewrites pass-through object fields to strings."""
    gemini_tools = []
    for tool in TOOLS:
        tool_copy = copy.deepcopy(tool)
        fields_to_flatten = _PASSTHROUGH_OBJECT_FIELDS.get(tool_copy["name"], set())
        props = tool_copy["input_schema"]["properties"]
        for field in fields_to_flatten:
            if field in props:
                original_desc = props[field].get("description", "")
                props[field] = {
                    "type": "string",
                    "description": (
                        f"{original_desc} Pass this as a JSON-encoded string "
                        f"(e.g. '{{\"key\": \"value\"}}'), not a nested object."
                    ).strip(),
                }
        gemini_tools.append(tool_copy)
    return gemini_tools


GEMINI_TOOLS = _build_gemini_tools()


def _build_groq_tools() -> list[dict]:
    """Groq's API is OpenAI-compatible: each tool wraps under
    {"type": "function", "function": {...}}. Unlike Gemini, its schema
    validation is permissive enough to accept our open-ended "object"
    passthrough fields as-is — no JSON-string workaround needed here."""
    return [
        {
            "type": "function",
            "function": {
                "name": t["name"],
                "description": t["description"],
                "parameters": t["input_schema"],
            },
        }
        for t in TOOLS
    ]


GROQ_TOOLS = _build_groq_tools()


def _decode_passthrough_fields(tool_name: str, tool_input: dict) -> dict:
    """If a pass-through object field arrived as a JSON string (Gemini), decode it."""
    fields = _PASSTHROUGH_OBJECT_FIELDS.get(tool_name, set())
    if not fields:
        return tool_input
    decoded = dict(tool_input)
    for field in fields:
        value = decoded.get(field)
        if isinstance(value, str):
            try:
                decoded[field] = json.loads(value)
            except json.JSONDecodeError:
                pass  # leave as-is; downstream will surface a clear KeyError
    return decoded


def dispatch(
    tool_name: str,
    tool_input: dict,
    request: DecisionRequest | None = None,
) -> dict:
    """Public entry point. Never lets an agent-layer exception escape and
    crash the Supervisor's tool-calling loop — a malformed or unexpected
    tool call from the LLM should surface as an error result the model can
    see and react to, not a 500 that ends the whole request.

    The trusted request is supplied by the Supervisor, never by the LLM. It
    binds customer access and execution authorization to the original API call.
    """
    try:
        return _dispatch_impl(tool_name, tool_input, request)
    except Exception as e:  # noqa: BLE001 - deliberately broad, see docstring
        return {"error": f"{type(e).__name__}: {e}"}


def _dispatch_impl(
    tool_name: str,
    tool_input: dict,
    request: DecisionRequest | None = None,
) -> dict:
    tool_input = _decode_passthrough_fields(tool_name, tool_input)
    if (
        request is not None
        and "customer_id" in tool_input
        and tool_input["customer_id"] != request.customer_id
    ):
        return {"error": "Tool call blocked: customer does not match the request."}
    request_scoped_tools = {
        "check_loan_negotiation_policy": RequestType.LOAN_RATE_NEGOTIATION,
        "negotiate_loan_rate": RequestType.LOAN_RATE_NEGOTIATION,
        "check_fee_waiver_policy": RequestType.FEE_WAIVER,
        "negotiate_fee_waiver": RequestType.FEE_WAIVER,
        "check_credit_limit_policy": RequestType.CREDIT_LIMIT_INCREASE,
        "negotiate_credit_limit": RequestType.CREDIT_LIMIT_INCREASE,
        "check_retention_offer_policy": RequestType.RETENTION_OFFER,
        "negotiate_retention_offer": RequestType.RETENTION_OFFER,
    }
    if (
        request is not None
        and tool_name in request_scoped_tools
        and request_scoped_tools[tool_name] != request.request_type
    ):
        return {"error": "Tool call blocked: tool does not match the request type."}
    if (
        request is not None
        and tool_name == "escalate_case"
        and tool_input.get("request_type") != request.request_type.value
    ):
        return {"error": "Tool call blocked: escalation type does not match the request."}

    if tool_name == "get_customer_profile":
        return customer_profile_agent.get_customer_profile(tool_input["customer_id"])

    if tool_name == "check_loan_negotiation_policy":
        from app import database as db
        customer = db.get_customer(tool_input["customer_id"])
        loan = None
        if tool_input.get("loan_id"):
            loans = db.get_loans(tool_input["customer_id"])
            loan = next((l for l in loans if l["loan_id"] == tool_input["loan_id"]), None)
        return policy_agent.check_loan_negotiation(
            customer, loan, tool_input.get("requested_rate")
        )

    if tool_name == "negotiate_loan_rate":
        return negotiation_agent.negotiate_loan_rate(tool_input["evaluation"])

    if tool_name == "check_fee_waiver_policy":
        from app import database as db
        customer = db.get_customer(tool_input["customer_id"])
        return policy_agent.check_fee_waiver(
            customer, tool_input["fee_type"], tool_input["amount"]
        )

    if tool_name == "negotiate_fee_waiver":
        return negotiation_agent.negotiate_fee_waiver(
            tool_input["evaluation"], tool_input["requested_amount"]
        )

    if tool_name == "check_credit_limit_policy":
        from app import database as db
        customer = db.get_customer(tool_input["customer_id"])
        accounts = db.get_accounts(tool_input["customer_id"])
        account = next((a for a in accounts if a["account_id"] == tool_input["account_id"]), None)
        return policy_agent.check_credit_limit_increase(
            customer, account, tool_input["requested_increase_pct"], tool_input["is_temporary"]
        )

    if tool_name == "negotiate_credit_limit":
        return negotiation_agent.negotiate_credit_limit(
            tool_input["evaluation"], tool_input["current_limit"]
        )

    if tool_name == "check_retention_offer_policy":
        from app import database as db
        customer = db.get_customer(tool_input["customer_id"])
        return policy_agent.check_retention_offer(
            customer,
            tool_input.get("requested_credit"),
            tool_input.get("closing_all_accounts", False),
        )

    if tool_name == "negotiate_retention_offer":
        return negotiation_agent.negotiate_retention_offer(tool_input["evaluation"])

    if tool_name == "execute_action":
        if request is None:
            return {"error": "Execution blocked: trusted request context is missing."}
        action_type = tool_input["action_type"]
        params = tool_input["params"]
        customer_id = tool_input["customer_id"]
        return _execute_policy_checked(action_type, customer_id, params, request)

    if tool_name == "escalate_case":
        return escalation_agent.escalate(
            tool_input["customer_id"], tool_input["request_type"],
            tool_input["reasons"], tool_input.get("context", {}),
        )

    return {"error": f"unknown tool {tool_name}"}


def _execute_policy_checked(
    action_type: str,
    customer_id: str,
    params: dict,
    request: DecisionRequest,
) -> dict:
    """Re-evaluates policy using trusted request fields immediately before execution."""
    from app import database as db
    from app import policy_engine

    action_requests = {
        "loan_rate_change": RequestType.LOAN_RATE_NEGOTIATION,
        "fee_waiver": RequestType.FEE_WAIVER,
        "credit_limit_change": RequestType.CREDIT_LIMIT_INCREASE,
        "retention_credit": RequestType.RETENTION_OFFER,
    }
    if action_type not in action_requests:
        return {"error": f"Execution blocked: unsupported action '{action_type}'."}
    if action_requests[action_type] != request.request_type:
        return {"error": "Execution blocked: action type does not match the request."}
    if customer_id != request.customer_id:
        return {"error": "Execution blocked: customer does not match the request."}

    customer = db.get_customer(request.customer_id)
    if not customer:
        return {"error": "Execution blocked: customer was not found."}

    def valid_number(value) -> bool:
        return (
            isinstance(value, (int, float))
            and not isinstance(value, bool)
            and math.isfinite(value)
        )

    def blocked(reasons: list[str]) -> dict:
        return {"error": "Execution blocked by policy: " + "; ".join(reasons)}

    if action_type == "loan_rate_change":
        if set(params) - {"loan_id", "new_rate"} or not valid_number(params.get("new_rate")):
            return {"error": "Execution blocked: invalid loan rate parameters."}
        if params.get("loan_id") != request.loan_id:
            return {"error": "Execution blocked: loan ID does not match the request."}
        loan = None
        if request.loan_id:
            loan = next(
                (item for item in db.get_loans(request.customer_id)
                 if item["loan_id"] == request.loan_id),
                None,
            )
            if not loan:
                return {"error": "Execution blocked: loan does not belong to this customer."}
        evaluation = policy_engine.evaluate_loan_negotiation(
            customer, loan, request.requested_value
        )
        new_rate = params["new_rate"]
        upper_bound = request.requested_value
        if upper_bound is None:
            upper_bound = evaluation["floor_rate"]
        if not evaluation["within_agent_authority"]:
            return blocked(evaluation["escalation_reasons"])
        if not evaluation["floor_rate"] <= new_rate <= min(upper_bound, evaluation["base_rate"]):
            return {"error": "Execution blocked: loan rate is outside the authorized offer range."}
        return execution_agent.execute_loan_rate_change(
            customer_id, request.loan_id, new_rate
        )

    if action_type == "fee_waiver":
        if set(params) != {"fee_type", "amount"} or not valid_number(params.get("amount")):
            return {"error": "Execution blocked: invalid fee waiver parameters."}
        if (
            not request.fee_type
            or params["fee_type"] != request.fee_type
            or request.requested_value is None
            or params["amount"] > request.requested_value
        ):
            return {"error": "Execution blocked: fee terms do not match the request."}
        evaluation = policy_engine.evaluate_fee_waiver(
            customer, request.fee_type, request.requested_value
        )
        if not evaluation["within_agent_authority"]:
            return blocked(evaluation["escalation_reasons"])
        return execution_agent.execute_fee_waiver(
            customer_id, request.fee_type, params["amount"]
        )

    if action_type == "credit_limit_change":
        if set(params) != {"account_id", "new_limit", "is_temporary"}:
            return {"error": "Execution blocked: invalid credit limit parameters."}
        if (
            not valid_number(params["new_limit"])
            or not isinstance(params["is_temporary"], bool)
            or request.account_id is None
            or params["account_id"] != request.account_id
            or params["is_temporary"] != request.is_temporary
            or request.requested_value is None
        ):
            return {"error": "Execution blocked: credit limit terms do not match the request."}
        account = next(
            (item for item in db.get_accounts(request.customer_id)
             if item["account_id"] == request.account_id),
            None,
        )
        if not account or not valid_number(account.get("credit_limit")) or account["credit_limit"] <= 0:
            return {"error": "Execution blocked: account or current limit is invalid."}
        increase_pct = (
            (params["new_limit"] / account["credit_limit"]) - 1
        ) * 100
        if not 0 <= increase_pct <= request.requested_value:
            return {"error": "Execution blocked: credit limit exceeds the requested increase."}
        evaluation = policy_engine.evaluate_credit_limit_increase(
            customer, account, request.requested_value, request.is_temporary
        )
        if not evaluation["within_agent_authority"]:
            return blocked(evaluation["escalation_reasons"])
        return execution_agent.execute_credit_limit_change(
            customer_id, request.account_id, params["new_limit"], request.is_temporary
        )

    if set(params) != {"credit_amount"} or not valid_number(params.get("credit_amount")):
        return {"error": "Execution blocked: invalid retention credit parameters."}
    if (
        request.requested_value is None
        or params["credit_amount"] > request.requested_value
    ):
        return {"error": "Execution blocked: retention terms do not match the request."}
    evaluation = policy_engine.evaluate_retention_offer(
        customer, request.requested_value, request.closing_all_accounts
    )
    if not evaluation["within_agent_authority"]:
        return blocked(evaluation["escalation_reasons"])
    return execution_agent.execute_retention_credit(
        customer_id, params["credit_amount"]
    )
