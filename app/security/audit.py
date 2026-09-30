"""Cryptographically Chained Audit Ledger (Tamper-Evident SHA-256 Chain).

In regulatory banking (SOX, SOC 2 Type II, BCBS 239), audit logs for automated
agent decisions must be immutable and verifiable against tampering.

Each action record contains:
1. `prev_hash`: The SHA-256 hash of the immediately preceding ledger block.
2. `record_hash`: The SHA-256 hash over (prev_hash + customer_id + action_type + details + timestamp + outcome).

If an attacker or rogue administrator modifies any record in SQLite after the fact,
the entire subsequent hash chain breaks, providing cryptographic proof of tampering.
"""
import hashlib
import json
from typing import Dict, Any, Tuple


GENESIS_HASH = "0" * 64


def compute_record_hash(
    prev_hash: str,
    customer_id: str,
    action_type: str,
    details_json: str,
    executed_on: str,
    outcome: str,
) -> str:
    """Computes SHA-256 hash for an audit ledger block."""
    payload = f"{prev_hash}|{customer_id}|{action_type}|{details_json}|{executed_on}|{outcome}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def verify_chain(records: list[dict[str, Any]]) -> Tuple[bool, str, int | None]:
    """Verifies the integrity of a list of audit ledger records in chronological order.
    
    Returns:
        (is_valid, message, broken_at_id)
    """
    if not records:
        return True, "Ledger is empty; chain is valid.", None

    expected_prev = GENESIS_HASH

    for i, record in enumerate(records):
        rec_id = record.get("id", i + 1)
        prev_hash = record.get("prev_hash", GENESIS_HASH)
        record_hash = record.get("record_hash", "")

        # 1. Verify prev_hash linkage
        if prev_hash != expected_prev:
            return False, f"Broken link at record id={rec_id}: expected prev_hash {expected_prev[:12]}..., got {prev_hash[:12]}...", rec_id

        # 2. Recompute current record hash
        computed_hash = compute_record_hash(
            prev_hash=prev_hash,
            customer_id=record["customer_id"],
            action_type=record["action_type"],
            details_json=record["details"],
            executed_on=record["executed_on"],
            outcome=record["outcome"],
        )

        if computed_hash != record_hash:
            return False, f"Tampered record at id={rec_id}: content hash mismatch.", rec_id

        expected_prev = record_hash

    return True, f"Cryptographic integrity verified across {len(records)} records.", None
