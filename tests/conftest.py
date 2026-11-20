"""Shared test setup: loads the mock data and a helper to build transactions."""
import csv
from datetime import date
from pathlib import Path

import pytest

from recon_statement.loader import load_transactions
from recon_statement.models import Transaction
from recon_statement.statement import read_balances

SAMPLE = Path(__file__).resolve().parent.parent / "data" / "sample"


@pytest.fixture
def bank_lines():
    return load_transactions(SAMPLE / "mock_bank_statement.csv", "bank")


@pytest.fixture
def book_lines():
    return load_transactions(SAMPLE / "mock_cashbook.csv", "cashbook")


@pytest.fixture
def balances():
    return read_balances(SAMPLE / "mock_balances.csv")


@pytest.fixture
def answer_key():
    with open(SAMPLE / "mock_answer_key.csv", newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


@pytest.fixture
def make_txn():
    """Build a Transaction quickly: make_txn("B1", 10, "text", "REF", 12345, "bank")."""
    def make(txn_id, day, description, reference, pence, source):
        return Transaction(txn_id, date(2026, 10, day), description,
                           reference, pence, source)
    return make