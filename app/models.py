"""Shared data models used across agents, the policy engine, and the API."""
from enum import Enum
from typing import Any, Optional
from pydantic import BaseModel, Field


class RequestType(str, Enum):
    LOAN_RATE_NEGOTIATION = "loan_rate_negotiation"
    FEE_WAIVER = "fee_waiver"
    CREDIT_LIMIT_INCREASE = "credit_limit_increase"
    RETENTION_OFFER = "retention_offer"


class DecisionRequest(BaseModel):
    customer_id: str
    request_type: RequestType
    customer_message: str = Field(
        ..., description="What the customer actually asked for, in their words."
    )
    requested_value: Optional[float] = Field(
        default=None,
        description="e.g. desired rate (8.5), fee amount to waive, requested credit limit increase, or retention credit amount."
    )
    loan_id: Optional[str] = None
    account_id: Optional[str] = None
    fee_type: Optional[str] = None
    closing_all_accounts: bool = Field(
        default=False,
        description="True if the customer is threatening to close every account (a full exit), not just one product."
    )


class TraceStep(BaseModel):
    agent: str
    action: str
    detail: str


class Decision(BaseModel):
    customer_id: str
    request_type: RequestType
    outcome: str            # "approved" | "denied" | "escalated"
    terms: dict[str, Any] = Field(default_factory=dict)
    reasoning: str
    policy_citations: list[str] = Field(default_factory=list)
    trace: list[TraceStep] = Field(default_factory=list)
    case_id: Optional[str] = Field(default=None, description="Tracked case ID if escalated to HITL queue")
    record_hash: Optional[str] = Field(default=None, description="Cryptographic SHA-256 ledger hash for audit integrity")
    pii_redacted: bool = Field(default=False, description="Whether sensitive PII was masked before LLM processing")


class EscalationReviewRequest(BaseModel):
    decision: str = Field(..., description="'approve', 'reject', or 'override'")
    reviewer_notes: str = Field(..., description="Justification and notes from underwriter/RM")
    overridden_terms: Optional[dict[str, Any]] = Field(default=None, description="Terms overridden by underwriter")


class AuditVerificationResponse(BaseModel):
    valid: bool
    message: str
    total_records: int
    broken_at_id: Optional[int] = None
