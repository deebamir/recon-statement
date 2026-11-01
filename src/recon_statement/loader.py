"""Reads the CSV files into Transaction objects."""
import csv
from datetime import date

from recon_statement.models import Transaction


def load_transactions(path, source):
    """Read a CSV file. source is 'bank' or 'cashbook'."""
    lines = []
    with open(path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            lines.append(Transaction(
                id=row["id"],
                date=date.fromisoformat(row["date"]),
                description=row["description"],
                reference=row["reference"],
                amount_pence=int(row["amount_pence"]),
                source=source,
            ))
    return lines