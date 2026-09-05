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

from app.agents import (
    customer_profile_agent,
    policy_agent,
    negotiation_agent,
    execution_agent,
    escalation_agent,
)

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
                    "enum": ["loan_rate_change", "fee_waiver", "credit_limit_change"],
                },
                "params": {
                    "type": "object",
                    "description": (
                        "loan_rate_change: {loan_id, new_rate}. "
                        "fee_waiver: {fee_type, amount}. "
                        "credit_limit_change: {account_id, new_limit, is_temporary}."
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


def dispatch(tool_name: str, tool_input: dict) -> dict:
    tool_input = _decode_passthrough_fields(tool_name, tool_input)
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

    if tool_name == "execute_action":
        action_type = tool_input["action_type"]
        params = tool_input["params"]
        customer_id = tool_input["customer_id"]
        if action_type == "loan_rate_change":
            return execution_agent.execute_loan_rate_change(
                customer_id, params.get("loan_id"), params["new_rate"]
            )
        if action_type == "fee_waiver":
            return execution_agent.execute_fee_waiver(
                customer_id, params["fee_type"], params["amount"]
            )
        if action_type == "credit_limit_change":
            return execution_agent.execute_credit_limit_change(
                customer_id, params.get("account_id"), params["new_limit"], params["is_temporary"]
            )
        return {"error": f"unknown action_type {action_type}"}

    if tool_name == "escalate_case":
        return escalation_agent.escalate(
            tool_input["customer_id"], tool_input["request_type"],
            tool_input["reasons"], tool_input.get("context", {}),
        )

    return {"error": f"unknown tool {tool_name}"}
