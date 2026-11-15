"""Screens request wording for explicit control-evasion signals.

This is a deterministic triage aid, not a fraud finding or a substitute for
identity verification, transaction monitoring, or human investigation.
"""
import re


_SIGNAL_PATTERNS = {
    "policy_override": re.compile(
        r"\b(?:ignore|bypass|override|skip|disable)\b.{0,50}"
        r"\b(?:policy|approval|verification|security controls?|audit)\b",
        re.IGNORECASE,
    ),
    "audit_concealment": re.compile(
        r"\b(?:off the books|without logging|hide this from (?:the )?audit|"
        r"(?:do not|don't) (?:log|record) this)\b",
        re.IGNORECASE,
    ),
    "authority_impersonation": re.compile(
        r"\b(?:i am|i'm)\s+(?:the\s+)?"
        r"(?:chief risk officer|chief executive officer|bank employee|"
        r"bank manager|underwriter|system administrator)\b",
        re.IGNORECASE,
    ),
}


def review_request(customer_message: str) -> dict:
    """Return explicit text signals without inferring intent or identity."""
    indicators = [
        name
        for name, pattern in _SIGNAL_PATTERNS.items()
        if pattern.search(customer_message)
    ]
    return {
        "risk_level": "review" if indicators else "clear",
        "requires_human_review": bool(indicators),
        "indicators": indicators,
        "notice": (
            "Screening signals require human review; they are not a fraud finding."
            if indicators
            else "No configured control-evasion signals were detected."
        ),
    }
