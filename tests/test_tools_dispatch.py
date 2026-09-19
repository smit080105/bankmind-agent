"""Tests for app.tools — the dispatcher that both LLM providers call into.

The pass-through JSON-string decoding is the trickiest piece here: Anthropic
sends nested objects natively, Gemini's schema can't, so those fields arrive
as JSON strings and must be transparently decoded before reaching the agent
functions. Both shapes need to keep working.
"""
import json

from app.tools import TOOLS, GEMINI_TOOLS, dispatch


class TestGeminiToolConversion:
    def test_same_tool_count_and_names(self):
        assert len(TOOLS) == len(GEMINI_TOOLS)
        assert {t["name"] for t in TOOLS} == {t["name"] for t in GEMINI_TOOLS}

    def test_passthrough_fields_become_strings(self):
        gemini_negotiate = next(t for t in GEMINI_TOOLS if t["name"] == "negotiate_loan_rate")
        assert gemini_negotiate["input_schema"]["properties"]["evaluation"]["type"] == "string"

        anthropic_negotiate = next(t for t in TOOLS if t["name"] == "negotiate_loan_rate")
        assert anthropic_negotiate["input_schema"]["properties"]["evaluation"]["type"] == "object"


class TestDispatch:
    def test_get_customer_profile_unknown_customer(self, temp_db):
        result = dispatch("get_customer_profile", {"customer_id": "NOBODY"})
        assert result["found"] is False

    def test_negotiate_loan_rate_accepts_native_dict(self):
        """Anthropic-style call: evaluation arrives as an actual dict."""
        evaluation = {
            "within_agent_authority": True,
            "floor_rate": 9.75,
            "base_rate": 11.0,
            "requested_rate": 9.8,
            "max_discount_bps": 125,
        }
        result = dispatch("negotiate_loan_rate", {"evaluation": evaluation})
        assert result["offer_possible"] is True
        assert result["offered_rate"] == 9.8

    def test_negotiate_loan_rate_accepts_json_string(self):
        """Gemini-style call: evaluation arrives as a JSON-encoded string."""
        evaluation = {
            "within_agent_authority": True,
            "floor_rate": 9.75,
            "base_rate": 11.0,
            "requested_rate": 9.8,
            "max_discount_bps": 125,
        }
        result = dispatch("negotiate_loan_rate", {"evaluation": json.dumps(evaluation)})
        assert result["offer_possible"] is True
        assert result["offered_rate"] == 9.8

    def test_malformed_tool_input_returns_error_dict_not_a_crash(self):
        """If a tool input is malformed in a way that trips up the agent
        function, dispatch() must catch it and hand back an error the LLM
        can see — not let an exception blow up the whole request."""
        result = dispatch("negotiate_loan_rate", {"evaluation": "{not valid json"})
        assert "error" in result

    def test_negotiate_retention_offer_accepts_json_string(self):
        evaluation = {
            "within_agent_authority": True,
            "max_credit": 2500,
            "requested_credit": 1500,
        }
        result = dispatch("negotiate_retention_offer", {"evaluation": json.dumps(evaluation)})
        assert result["offer_possible"] is True
        assert result["granted_credit"] == 1500

    def test_unknown_tool_returns_error_dict(self):
        result = dispatch("not_a_real_tool", {})
        assert "error" in result
