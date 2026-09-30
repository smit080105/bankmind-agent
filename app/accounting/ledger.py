"""Double-Entry General Ledger Accounting for Autonomous Banking Actions.

In financial institutions, automated agent actions (e.g. fee waivers, retention
bonuses) cannot exist purely as status strings. They must produce real, balanced
accounting entries obeying the fundamental accounting equation:
    Assets = Liabilities + Equity
and the strict rule:
    Sum(Debits) == Sum(Credits)
"""
from dataclasses import dataclass
from typing import List
import datetime


class UnbalancedJournalEntryError(ValueError):
    """Raised when journal debits do not equal credits."""
    pass


@dataclass
class JournalLine:
    account: str
    debit: float = 0.0
    credit: float = 0.0

    def __post_init__(self):
        self.debit = round(float(self.debit), 2)
        self.credit = round(float(self.credit), 2)
        if self.debit < 0 or self.credit < 0:
            raise ValueError("Debit and credit amounts must be non-negative.")
        if self.debit > 0 and self.credit > 0:
            raise ValueError("A single line cannot have both non-zero debit and credit.")


@dataclass
class JournalEntry:
    transaction_id: str
    description: str
    timestamp: str
    lines: List[JournalLine]

    def validate(self):
        total_debits = round(sum(line.debit for line in self.lines), 2)
        total_credits = round(sum(line.credit for line in self.lines), 2)
        if total_debits != total_credits:
            raise UnbalancedJournalEntryError(
                f"Unbalanced journal entry '{self.transaction_id}': total debits ({total_debits}) "
                f"!= total credits ({total_credits})"
            )
        if total_debits == 0:
            raise UnbalancedJournalEntryError("Journal entry cannot have zero total value.")


def create_fee_waiver_entry(transaction_id: str, customer_id: str, fee_type: str, amount: float) -> JournalEntry:
    """Creates a balanced double-entry transaction for a waived customer fee:
    - Debit: Expenses:FeeWaiverGoodwill (Bank absorbs the fee as an operating expense)
    - Credit: Revenue:FeeIncome (Offsetting fee receivable)
    """
    now = datetime.datetime.now().isoformat()
    entry = JournalEntry(
        transaction_id=transaction_id,
        description=f"Fee waiver ({fee_type}) for customer {customer_id}",
        timestamp=now,
        lines=[
            JournalLine(account="Expenses:FeeWaiverGoodwill", debit=amount, credit=0.0),
            JournalLine(account="Revenue:FeeIncome", debit=0.0, credit=amount),
        ]
    )
    entry.validate()
    return entry


def create_retention_credit_entry(transaction_id: str, customer_id: str, credit_amount: float) -> JournalEntry:
    """Creates a balanced double-entry transaction for a customer retention bonus:
    - Debit: Expenses:CustomerRetentionCredit (Marketing/Retention expense)
    - Credit: Liabilities:CustomerDeposits (Increases customer bank balance)
    """
    now = datetime.datetime.now().isoformat()
    entry = JournalEntry(
        transaction_id=transaction_id,
        description=f"Retention credit bonus for customer {customer_id}",
        timestamp=now,
        lines=[
            JournalLine(account="Expenses:CustomerRetentionCredit", debit=credit_amount, credit=0.0),
            JournalLine(account="Liabilities:CustomerDeposits", debit=0.0, credit=credit_amount),
        ]
    )
    entry.validate()
    return entry
