"""Mock data generator for recon-statement.

ALL DATA HERE IS MADE UP (company: MOCK Demo Trading Ltd).
Every error is planted on purpose and listed in mock_answer_key.csv,
so the tests know the right answers.

Money is whole pence. Money in is positive, money out is negative.
"""
import csv
from datetime import date
from decimal import Decimal
from pathlib import Path

from recon_statement.models import Transaction
from recon_statement.money import fmt, to_pence

OUT_DIR = Path("data/sample")
OPENING = to_pence("10000.00")
EXPECTED_ADJUSTED = to_pence("6967.35")  # both sides agree here once fixed


def bank(txn_id, day, description, reference, amount):
    return Transaction(txn_id, date(2026, 10, day), description,
                       reference, to_pence(amount), "bank")


def book(txn_id, day, description, reference, amount):
    return Transaction(txn_id, date(2026, 10, day), description,
                       reference, to_pence(amount), "cashbook")


BANK_LINES = [
    bank("BK01", 2, "CREDIT ACME LTD", "INV1001", "1200.00"),
    bank("BK02", 3, "STANDING ORDER RENT", "RENT-OCT", "-850.00"),
    bank("BK03", 8, "CREDIT BROWN AND CO", "INV1002", "450.00"),
    bank("BK04", 12, "CHEQUE 0101", "CHQ0101", "-300.00"),
    bank("BK05", 16, "BACS PAYROLL RUN", "PAY-OCT", "-3000.00"),
    bank("BK06", 22, "CHEQUE 0103", "CHQ0103", "-125.00"),
    bank("BK07", 23, "CHEQUE 0104", "CHQ0104", "-45.00"),
    bank("BK08", 24, "PAYMENT REF-77", "REF-77", "-90.00"),
    bank("BK09", 25, "DIRECT DEBIT ELECTRIC", "DD-ELEC", "-60.00"),
    bank("BK10", 27, "RETURNED CHEQUE BROWN AND CO", "RTN-INV1002", "-450.00"),
    bank("BK11", 30, "BANK CHARGES OCT", "BCHG", "-15.00"),
    bank("BK12", 31, "INTEREST", "INT", "2.35"),
]

CASHBOOK_LINES = [
    book("CB01", 2, "Receipt Acme Ltd", "INV1001", "1200.00"),
    book("CB02", 3, "Rent October", "RENT-OCT", "-850.00"),
    book("CB03", 7, "Receipt Brown and Co", "INV1002", "450.00"),
    book("CB04", 10, "Cheque Wilson Supplies", "CHQ0101", "-300.00"),
    book("CB05", 15, "Wages Alice", "PAY-OCT", "-1200.00"),
    book("CB06", 15, "Wages Bob", "PAY-OCT", "-1000.00"),
    book("CB07", 15, "Wages Carol", "PAY-OCT", "-800.00"),
    book("CB08", 20, "Cheque Office Supplies", "CHQ0103", "-125.00"),
    book("CB09", 20, "Cheque Office Supplies", "CHQ0103", "-125.00"),
    book("CB10", 21, "Cheque Cleaning Co", "CHQ0104", "-54.00"),
    book("CB11", 24, "Supplier credit", "REF-77", "90.00"),
    book("CB12", 28, "Cheque Stationery Plus", "CHQ0102", "-500.00"),
    book("CB13", 30, "Receipt Green Ltd", "INV1003", "750.00"),
]

# category, bank ids, cashbook ids, note
ANSWER_KEY = [
    ("exact_match", "BK01", "CB01", "same amount and reference"),
    ("exact_match", "BK02", "CB02", "same amount and reference"),
    ("exact_match", "BK03", "CB03", "bank is 1 day later"),
    ("exact_match", "BK04", "CB04", "bank is 2 days later"),
    ("batch_payment", "BK05", "CB05|CB06|CB07", "3 wages add up to 3000.00"),
    ("possible_duplicate", "BK06", "CB08|CB09", "CB09 is the duplicate"),
    ("transposed_digits", "BK07", "CB10", "45.00 in bank, 54.00 in cashbook"),
    ("reversed_sign", "BK08", "CB11", "bank paid 90.00, cashbook shows +90.00"),
    ("direct_debit", "BK09", "", "on bank only, not in cashbook"),
    ("dishonoured_cheque", "BK10", "", "on bank only, not in cashbook"),
    ("missing_bank_charge", "BK11", "", "on bank only, not in cashbook"),
    ("bank_interest", "BK12", "", "on bank only, not in cashbook"),
    ("unpresented_cheque", "", "CB12", "in cashbook, not yet on bank"),
    ("outstanding_lodgement", "", "CB13", "in cashbook, not yet on bank"),
]


def pounds(pence):
    return f"{Decimal(pence) / 100:.2f}"


def write_transactions(filename, lines):
    with open(OUT_DIR / filename, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["id", "date", "description", "reference",
                         "amount_pence", "amount"])
        for t in lines:
            writer.writerow([t.id, t.date.isoformat(), t.description,
                             t.reference, t.amount_pence, pounds(t.amount_pence)])


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    write_transactions("mock_bank_statement.csv", BANK_LINES)
    write_transactions("mock_cashbook.csv", CASHBOOK_LINES)

    with open(OUT_DIR / "mock_answer_key.csv", "w", newline="",
              encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["category", "bank_ids", "cashbook_ids", "note"])
        writer.writerows(ANSWER_KEY)

    bank_close = OPENING + sum(t.amount_pence for t in BANK_LINES)
    book_close = OPENING + sum(t.amount_pence for t in CASHBOOK_LINES)
    with open(OUT_DIR / "mock_balances.csv", "w", newline="",
              encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["name", "amount_pence"])
        writer.writerow(["bank_opening", OPENING])
        writer.writerow(["bank_closing", bank_close])
        writer.writerow(["cashbook_opening", OPENING])
        writer.writerow(["cashbook_closing", book_close])
        writer.writerow(["expected_adjusted_balance", EXPECTED_ADJUSTED])

    print("MOCK data written to", OUT_DIR)
    print("Bank closing balance:     ", fmt(bank_close))
    print("Cashbook closing balance: ", fmt(book_close))
    print("Expected once all fixed:  ", fmt(EXPECTED_ADJUSTED))


if __name__ == "__main__":
    main()