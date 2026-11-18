"""Exception triage: explains every item the matchers could not pair.

Each unmatched item is classified (timing difference, missing bank charge,
possible duplicate, transposed digits, reversed sign ...), given a confidence
score and a plain-English reason and, where the cashbook is wrong, a suggested
journal entry. An ageing report shows how old the unreconciled items are.
"""
from dataclasses import dataclass
from datetime import timedelta

from recon_statement.batch import find_batch_matches
from recon_statement.loader import load_transactions
from recon_statement.matcher import find_matches
from recon_statement.money import fmt
from recon_statement.statement import (BANK_ONLY_WORDS, PERIOD_END, TIMING_DAYS,
                                       build_statement, read_balances)

CASH = "Cash at bank"

# statement heading -> (category name, the other account in the journal)
BANK_ONLY_ACCOUNTS = {
    "bank_charges": ("missing_bank_charge", "Bank charges (expense)"),
    "bank_interest": ("bank_interest", "Bank interest received (income)"),
    "direct_debits": ("direct_debit", "Expense account for the payee"),
    "dishonoured": ("dishonoured_cheque", "Trade receivables (the customer)"),
}

AGE_BUCKETS = [("0-7 days", 0, 7), ("8-14 days", 8, 14),
               ("15-30 days", 15, 30), ("Over 30 days", 31, 36500)]


@dataclass
class ExceptionItem:
    category: str
    bank_ids: list
    cashbook_ids: list
    confidence: float
    explanation: str
    journal: list          # lines of (account, debit_pence, credit_pence); empty if none
    cashbook_effect: int   # change to the cashbook balance once the journal is posted


def journal_for(effect, other_account):
    """Journal lines for a change to the cashbook balance."""
    amount = abs(effect)
    if effect > 0:  # the cashbook balance goes up
        return [(CASH, amount, 0), (other_account, 0, amount)]
    return [(other_account, amount, 0), (CASH, 0, amount)]


def is_transposition(a, b):
    """True if two amounts differ only by two neighbouring digits swapped (54 vs 45)."""
    if (a > 0) != (b > 0):
        return False
    sa, sb = str(abs(a)), str(abs(b))
    if len(sa) != len(sb) or sa == sb:
        return False
    diff = [i for i in range(len(sa)) if sa[i] != sb[i]]
    return (len(diff) == 2 and diff[1] == diff[0] + 1
            and sa[diff[0]] == sb[diff[1]] and sa[diff[1]] == sb[diff[0]])


def triage(bank_lines, book_lines, period_end=PERIOD_END):
    """Return (exceptions, unreconciled bank lines, unreconciled cashbook lines)."""
    matches, left_bank, left_book = find_matches(bank_lines, book_lines)
    batch_matches, left_bank, left_book, skipped = find_batch_matches(left_bank, left_book)
    matched_ids = {i for m in matches + batch_matches for i in m.ledger_ids}
    matched_book = [t for t in book_lines if t.id in matched_ids]
    all_left_bank = list(left_bank)  # kept for the ageing report
    all_left_book = list(left_book)

    found = []

    # 1. possible duplicates: a cashbook line that copies one already matched
    for line in list(left_book):
        for other in matched_book:
            if (other.amount_pence == line.amount_pence
                    and other.reference == line.reference
                    and other.description == line.description):
                found.append(ExceptionItem(
                    "possible_duplicate", [], [line.id], 0.80,
                    f"{line.id} looks like a second copy of {other.id} "
                    f"({line.description}, {fmt(line.amount_pence)}), "
                    f"which is already matched to the bank",
                    journal_for(-line.amount_pence, "Account originally charged"),
                    -line.amount_pence))
                left_book.remove(line)
                break

    # 2. reversed sign or transposed digits: same reference, amounts disagree
    for bank_line in list(left_bank):
        for book_line in list(left_book):
            if book_line.reference != bank_line.reference:
                continue
            if book_line.amount_pence == -bank_line.amount_pence:
                category = "reversed_sign"
                tail = "same amount with the opposite sign"
            elif is_transposition(bank_line.amount_pence, book_line.amount_pence):
                category = "transposed_digits"
                tail = "same digits swapped"
            else:
                continue
            effect = bank_line.amount_pence - book_line.amount_pence  # bank is right
            found.append(ExceptionItem(
                category, [bank_line.id], [book_line.id], 0.85,
                f"Same reference {bank_line.reference}: bank "
                f"{fmt(bank_line.amount_pence)} vs cashbook "
                f"{fmt(book_line.amount_pence)}, {tail}",
                journal_for(effect, "Account originally posted to"), effect))
            left_bank.remove(bank_line)
            left_book.remove(book_line)
            break

    # 3. items on the bank statement that the cashbook never recorded
    for line in list(left_bank):
        for word, key in BANK_ONLY_WORDS:
            if word in line.description.upper():
                category, account = BANK_ONLY_ACCOUNTS[key]
                found.append(ExceptionItem(
                    category, [line.id], [], 0.90,
                    f"{line.description} ({fmt(line.amount_pence)}) is on the bank "
                    f"statement but not in the cashbook",
                    journal_for(line.amount_pence, account), line.amount_pence))
                left_bank.remove(line)
                break

    # 4. timing differences: recorded in the last few days of the period
    cutoff = period_end - timedelta(days=TIMING_DAYS)
    for line in list(left_book):
        if line.date > cutoff:
            what = "payment not yet presented" if line.amount_pence < 0 \
                else "receipt not yet on the statement"
            found.append(ExceptionItem(
                "timing_difference", [], [line.id], 0.70,
                f"{line.description} ({fmt(line.amount_pence)}) was recorded on "
                f"{line.date}, near the period end: {what}",
                [], 0))
            left_book.remove(line)

    # 5. anything left needs a human
    for line in left_bank + left_book:
        is_bank = line.source == "bank"
        found.append(ExceptionItem(
            "unexplained", [line.id] if is_bank else [], [] if is_bank else [line.id],
            0.0, f"{line.description} ({fmt(line.amount_pence)}): no rule explains "
                 f"this item, so a person must review it",
            [], 0))

    return found, all_left_bank, all_left_book


def ageing(lines, period_end=PERIOD_END):
    """Count and total value of unreconciled lines in each age bucket."""
    rows = []
    for name, low, high in AGE_BUCKETS:
        bucket = [t for t in lines if low <= (period_end - t.date).days <= high]
        rows.append((name, len(bucket), sum(abs(t.amount_pence) for t in bucket)))
    return rows


def main():
    bank_lines = load_transactions("data/sample/mock_bank_statement.csv", "bank")
    book_lines = load_transactions("data/sample/mock_cashbook.csv", "cashbook")
    balances = read_balances("data/sample/mock_balances.csv")

    exceptions, left_bank, left_book = triage(bank_lines, book_lines)

    print("EXCEPTIONS")
    for e in exceptions:
        ids = ", ".join(e.bank_ids + e.cashbook_ids)
        print(f"  {e.category:<22}{ids:<12}confidence {e.confidence:.2f}")
        print(f"    {e.explanation}")
        for account, debit, credit in e.journal:
            side, amount = ("Dr", debit) if debit else ("Cr", credit)
            print(f"    {side} {account:<34}{fmt(amount):>10}")

    print()
    print(f"AGEING OF UNRECONCILED ITEMS (as at {PERIOD_END})")
    for name, count, value in ageing(left_bank + left_book):
        print(f"  {name:<14}{count:>3} items {fmt(value):>10}")

    statement = build_statement(bank_lines, book_lines,
                                balances["bank_closing"], balances["cashbook_closing"])
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


if __name__ == "__main__":
    main()