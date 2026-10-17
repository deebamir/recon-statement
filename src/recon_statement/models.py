from dataclasses import dataclass
from datetime import date

@dataclass(frozen=True)
class Transaction:
    id: str
    date: date
    description: str
    reference: str
    amount_pence: int
    source: str # "bank" or "cashbook"

@dataclass
class Match:
    bank_ids: list[str]
    ledger_ids: list[str]
    rule: str
    confidence: float
    explanation: str
    