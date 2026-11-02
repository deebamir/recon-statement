"""Builds the bank reconciliation statement and writes it to Excel.

Cashbook side: cashbook balance, adjusted for items the bank has recorded
that the cashbook has not, giving the adjusted cashbook balance.
Bank side: statement balance, less unpresented cheques, plus outstanding
lodgements, giving the adjusted bank balance.
The two adjusted balances must agree. If not, the difference is flagged.
"""
import argparse
import csv
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Font

from recon_statement.config import TERMS
from recon_statement.loader import load_transactions
from recon_statement.matcher import find_matches
from recon_statement.money import fmt

PERIOD_END = date(2026, 10, 31)
TIMING_DAYS = 5  # unmatched cashbook lines this close to period end are timing items
MONEY = "#,##0.00;[Red]-#,##0.00"

# words in a bank description -> which statement heading it belongs under
BANK_ONLY_WORDS = [
    ("RETURNED CHEQUE", "dishonoured"),
    ("DIRECT DEBIT", "direct_debits"),
    ("BANK CHARGES", "bank_charges"),
    ("INTEREST", "bank_interest"),
]


@dataclass
class Statement:
    cashbook_balance: int
    bank_balance: int
    cashbook_items: list   # (heading key, Transaction): on the bank, not in the cashbook
    unpresented: list      # cashbook payments not yet on the bank (negative amounts)
    outstanding: list      # cashbook receipts not yet on the bank (positive amounts)
    unresolved_bank: list  # bank lines nobody has explained yet
    unresolved_book: list  # cashbook lines nobody has explained yet

    @property
    def adjusted_cashbook(self):
        return self.cashbook_balance + sum(t.amount_pence for _, t in self.cashbook_items)

    @property
    def adjusted_bank(self):
        # unpresented cheques are negative, so adding them takes them off
        return (self.bank_balance
                + sum(t.amount_pence for t in self.unpresented)
                + sum(t.amount_pence for t in self.outstanding))

    @property
    def difference(self):
        return self.adjusted_cashbook - self.adjusted_bank


def build_statement(bank_lines, book_lines, bank_balance, cashbook_balance,
                    period_end=PERIOD_END):
    matches, left_bank, left_book = find_matches(bank_lines, book_lines)

    cashbook_items = []
    unresolved_bank = []
    for line in left_bank:
        heading = None
        for word, key in BANK_ONLY_WORDS:
            if word in line.description.upper():
                heading = key
                break
        if heading:
            cashbook_items.append((heading, line))
        else:
            unresolved_bank.append(line)

    unpresented = []
    outstanding = []
    unresolved_book = []
    cutoff = period_end - timedelta(days=TIMING_DAYS)
    for line in left_book:
        if line.date > cutoff:  # recorded in the last few days: a timing item
            if line.amount_pence < 0:
                unpresented.append(line)
            else:
                outstanding.append(line)
        else:
            unresolved_book.append(line)

    return Statement(cashbook_balance, bank_balance, cashbook_items,
                     unpresented, outstanding, unresolved_bank, unresolved_book)


def status_text(statement):
    if statement.difference == 0:
        return f"AGREED: both adjusted balances are {fmt(statement.adjusted_bank)}."
    return (f"DOES NOT AGREE: the difference is {fmt(statement.difference)}. "
            "Review the unresolved items.")


def read_balances(path):
    with open(path, newline="", encoding="utf-8") as f:
        return {row["name"]: int(row["amount_pence"]) for row in csv.DictReader(f)}


def pounds(pence):
    return Decimal(pence) / 100


def add_line(ws, text, pence=None, bold=False):
    ws.append([text, None if pence is None else pounds(pence)])
    row = ws.max_row
    ws.cell(row=row, column=1).font = Font(bold=bold)
    if pence is not None:
        cell = ws.cell(row=row, column=2)
        cell.number_format = MONEY
        cell.font = Font(bold=bold)


def write_excel(statement, path, terms_name):
    words = TERMS[terms_name]
    wb = Workbook()
    ws = wb.active
    ws.title = "Reconciliation"
    ws.column_dimensions["A"].width = 62
    ws.column_dimensions["B"].width = 16

    add_line(ws, words["title"], bold=True)
    add_line(ws, "MOCK DATA: MOCK Demo Trading Ltd (a made-up company)")
    add_line(ws, f"As at {PERIOD_END.strftime('%d %B %Y')}")
    ws.append([])

    add_line(ws, "A. Cashbook side", bold=True)
    add_line(ws, words["cashbook_balance"], statement.cashbook_balance)
    for key, item in statement.cashbook_items:
        add_line(ws, f"   {words[key]}: {item.description} ({item.date})",
                 item.amount_pence)
    add_line(ws, words["adjusted_cashbook"], statement.adjusted_cashbook, bold=True)
    ws.append([])

    add_line(ws, "B. Bank side", bold=True)
    add_line(ws, words["bank_balance"], statement.bank_balance)
    for item in statement.unpresented:
        add_line(ws, f"   Less {words['unpresented']}: {item.description} ({item.date})",
                 item.amount_pence)
    for item in statement.outstanding:
        add_line(ws, f"   Add {words['outstanding_deposits']}: {item.description} ({item.date})",
                 item.amount_pence)
    add_line(ws, words["adjusted_bank"], statement.adjusted_bank, bold=True)
    ws.append([])

    add_line(ws, "Difference (cashbook less bank)", statement.difference, bold=True)
    ws.append([status_text(statement)])
    colour = "007A33" if statement.difference == 0 else "C00000"
    ws.cell(row=ws.max_row, column=1).font = Font(bold=True, color=colour)
    ws.append([])

    if statement.unresolved_bank or statement.unresolved_book:
        add_line(ws, "Unresolved items (not yet explained)", bold=True)
        for item in statement.unresolved_bank:
            add_line(ws, f"   Bank only: {item.description} ({item.date})", item.amount_pence)
        for item in statement.unresolved_book:
            add_line(ws, f"   Cashbook only: {item.description} ({item.date})", item.amount_pence)
        ws.append([])

    add_line(ws, "Sign-off", bold=True)
    ws.append(["Prepared by: ______________________", "Date: ____________"])
    ws.append(["Reviewed by: ______________________", "Date: ____________"])

    wb.save(path)


def main():
    parser = argparse.ArgumentParser(description="Build the bank reconciliation statement.")
    parser.add_argument("--terms", choices=["UK", "US"], default="UK",
                        help="UK or US wording (default UK)")
    parser.add_argument("--out", default="output", help="folder for the Excel file")
    args = parser.parse_args()

    bank_lines = load_transactions("data/sample/mock_bank_statement.csv", "bank")
    book_lines = load_transactions("data/sample/mock_cashbook.csv", "cashbook")
    balances = read_balances("data/sample/mock_balances.csv")
    statement = build_statement(bank_lines, book_lines,
                                balances["bank_closing"], balances["cashbook_closing"])

    words = TERMS[args.terms]
    print(f"{args.terms} terms")
    print(f"{words['adjusted_cashbook']}: {fmt(statement.adjusted_cashbook)}")
    print(f"{words['adjusted_bank']}: {fmt(statement.adjusted_bank)}")
    print(f"Difference: {fmt(statement.difference)}")
    print(status_text(statement))
    print(f"Unresolved items: {len(statement.unresolved_bank)} on the bank, "
          f"{len(statement.unresolved_book)} in the cashbook")

    out_dir = Path(args.out)
    out_dir.mkdir(exist_ok=True)
    path = out_dir / f"reconciliation_{args.terms}.xlsx"
    write_excel(statement, path, args.terms)
    print("Excel file written to", path)


if __name__ == "__main__":
    main()