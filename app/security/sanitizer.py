"""PII and PCI-DSS Data Sanitizer for FinTech Banking Agents.

In banking and regulated financial environments, raw customer identifiers
(card numbers, account numbers, tax IDs, emails, phone numbers) must NEVER
be sent in plaintext to external LLM providers.

This module provides a bidirectional tokenization proxy:
1. Sensitive values in customer messages or prompts are replaced with synthetic tokens
   (e.g., [CARD_TOKEN_1], [ACCOUNT_TOKEN_1]).
2. The agent reasoning and tool execution run with tokenized data.
3. The response can be safely de-tokenized for human relationship managers.
"""
import re
from typing import Dict, Tuple

# Pre-compiled regex patterns for financial PII/PCI data
_CARD_PATTERN = re.compile(r"\b(?:\d{4}[ -]?){3}\d{4}\b")
_ACCOUNT_PATTERN = re.compile(r"\bACC\d{3,10}\b", re.IGNORECASE)
_EMAIL_PATTERN = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b")
_PHONE_PATTERN = re.compile(r"\b(?:\+?\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b")
_SSN_PATTERN = re.compile(r"\b\d{3}-\d{2}-\d{4}\b")
_AADHAAR_PATTERN = re.compile(r"\b\d{4}\s\d{4}\s\d{4}\b")


class PIISanitizer:
    """Sanitizes text by replacing sensitive PII with reversible tokens."""

    @classmethod
    def sanitize(cls, text: str) -> Tuple[str, Dict[str, str]]:
        """Scans text and replaces PII/PCI with tokens.
        
        Returns:
            sanitized_text: The scrubbed string.
            token_map: Mapping from token -> original sensitive value.
        """
        if not text:
            return text, {}

        token_map: Dict[str, str] = {}
        sanitized = text

        def _replace_matches(pattern: re.Pattern, prefix: str, current_text: str) -> str:
            matches = list(pattern.finditer(current_text))
            for i, match in enumerate(matches, 1):
                val = match.group(0)
                # Check if this exact value was already mapped to a token
                existing_token = next((t for t, v in token_map.items() if v == val), None)
                if existing_token:
                    token = existing_token
                else:
                    token = f"[{prefix}_{len([k for k in token_map if k.startswith(f'[{prefix}_')]) + 1}]"
                    token_map[token] = val
                current_text = current_text.replace(val, token)
            return current_text

        sanitized = _replace_matches(_CARD_PATTERN, "CARD_TOKEN", sanitized)
        sanitized = _replace_matches(_SSN_PATTERN, "SSN_TOKEN", sanitized)
        sanitized = _replace_matches(_AADHAAR_PATTERN, "NATIONAL_ID_TOKEN", sanitized)
        sanitized = _replace_matches(_ACCOUNT_PATTERN, "ACCOUNT_TOKEN", sanitized)
        sanitized = _replace_matches(_EMAIL_PATTERN, "EMAIL_TOKEN", sanitized)
        sanitized = _replace_matches(_PHONE_PATTERN, "PHONE_TOKEN", sanitized)

        return sanitized, token_map

    @classmethod
    def restore(cls, text: str, token_map: Dict[str, str]) -> str:
        """Inverts tokenization, restoring original sensitive values."""
        if not text or not token_map:
            return text

        restored = text
        for token, original in token_map.items():
            restored = restored.replace(token, original)
        return restored
