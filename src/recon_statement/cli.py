"""Command line interface for recon-statement.

Example:
    recon-statement --terms UK --out output

Reads a bank CSV, a cashbook CSV and a balances CSV, builds the bank
reconciliation statement, explains every unmatched item and writes the
statement to Excel.
"""
import argparse
from datetime import date
from pathlib import Path

from recon_statement.config import TERMS
from recon_statement.loader import load_transactions
from recon_statement.money import fmt
from recon_statement.statement import (PERIOD_END, build_statement, read_balances,
                                       status_text, write_excel)
from recon_statement.triage import ageing, triage

SAMPLE = Path("data") / "sample"


def make_parser():
    parser = argparse.ArgumentParser(
        prog="recon-statement",
        description="Match bank and cashbook lines and build the bank "
                    "reconciliation statement.",
    )
    parser.add_argument("--bank", default=str(SAMPLE / "mock_bank_statement.csv"),
                        help="bank statement CSV (default: the mock sample)")
    parser.add_argument("--cashbook", default=str(SAMPLE / "mock_cashbook.csv"),
                        help="cashbook CSV (default: the mock sample)")
    parser.add_argument("--balances", default=str(SAMPLE / "mock_balances.csv"),
                        help="balances CSV with bank_closing and cashbook_closing rows")
    parser.add_argument("--terms", choices=["UK", "US"], default="UK",
                        help="UK or US wording (default UK)")
    parser.add_argument("--period-end", type=date.fromisoformat, default=PERIOD_END,
                        help="period end date as YYYY-MM-DD (default 2026-10-31)")
    parser.add_argument("--out", default="output",
                        help="folder for the Excel file (default: output)")
    return parser


def print_exceptions(exceptions):
    print("EXCEPTIONS")
    for e in exceptions:
        ids = ", ".join(e.bank_ids + e.cashbook_ids)
        print(f"  {e.category:<22}{ids:<12}confidence {e.confidence:.2f}")
        print(f"    {e.explanation}")
        for account, debit, credit in e.journal:
            side, amount = ("Dr", debit) if debit else ("Cr", credit)
            print(f"    {side} {account:<34}{fmt(amount):>10}")


def main(argv=None):
    args = make_parser().parse_args(argv)

    try:
        bank_lines = load_transactions(args.bank, "bank")
        book_lines = load_transactions(args.cashbook, "cashbook")
        balances = read_balances(args.balances)
    except FileNotFoundError as error:
        print(f"File not found: {error.filename}")
        return 2

    if "bank_closing" not in balances or "cashbook_closing" not in balances:
        print("The balances file needs rows named bank_closing and cashbook_closing.")
        return 2

    words = TERMS[args.terms]
    statement = build_statement(bank_lines, book_lines,
                                balances["bank_closing"], balances["cashbook_closing"],
                                period_end=args.period_end)

    print(f"{args.terms} terms, period end {args.period_end}")
    print(f"{words['adjusted_cashbook']}: {fmt(statement.adjusted_cashbook)}")
    print(f"{words['adjusted_bank']}: {fmt(statement.adjusted_bank)}")
    print(f"Difference: {fmt(statement.difference)}")
    print(status_text(statement))

    exceptions, left_bank, left_book = triage(bank_lines, book_lines,
                                              period_end=args.period_end)
    print()
    print_exceptions(exceptions)

    print()
    print(f"AGEING OF UNRECONCILED ITEMS (as at {args.period_end})")
    for name, count, value in ageing(left_bank + left_book, period_end=args.period_end):
        print(f"  {name:<14}{count:>3} items {fmt(value):>10}")

    corrected = balances["cashbook_closing"] + sum(e.cashbook_effect for e in exceptions)
    difference = corrected - statement.adjusted_bank
    print()
    print("AFTER POSTING THE SUGGESTED JOURNALS")
    print(f"Corrected cashbook balance: {fmt(corrected)}")
    print(f"Adjusted bank balance: {fmt(statement.adjusted_bank)}")
    print(f"Difference: {fmt(difference)}")
    if difference == 0:
        print("AGREED: the books and the bank now tell the same story.")
    else:
        print("STILL DOES NOT AGREE: review the unexplained items.")

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"reconciliation_{args.terms}.xlsx"
    write_excel(statement, path, args.terms, period_end=args.period_end)
    print()
    print("Excel file written to", path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())