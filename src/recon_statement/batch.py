"""Batch payment matcher: finds several cashbook lines that add up to one bank line.

Typical cases: a BACS payroll run or a US ACH batch, where the bank shows one
total and the cashbook has one line per person or invoice.
A date window and two safety caps keep the search fast.
"""
from itertools import combinations

from recon_statement.loader import load_transactions
from recon_statement.matcher import find_matches
from recon_statement.models import Match
from recon_statement.money import fmt

WINDOW_DAYS = 7      # cashbook lines must be within this many days of the bank line
MIN_LINES = 2        # a batch is at least 2 lines (single lines are the matcher's job)
MAX_LINES = 6        # never try batches bigger than this
MAX_CANDIDATES = 20  # only look at the 20 closest lines
MAX_TRIES = 50_000   # stop after this many combinations for one bank line


def find_batch_matches(bank_lines, cashbook_lines):
    """Return (matches, unmatched_bank, unmatched_cashbook, skipped_bank_ids)."""
    matches = []
    skipped = []
    free_bank = list(bank_lines)
    free_book = list(cashbook_lines)

    for bank_line in list(free_bank):
        target = bank_line.amount_pence

        # candidates: same direction (in or out), not bigger than the target,
        # and close in date
        candidates = []
        for line in free_book:
            if (line.amount_pence > 0) != (target > 0):
                continue
            if abs(line.amount_pence) > abs(target):
                continue
            days = abs((bank_line.date - line.date).days)
            if days <= WINDOW_DAYS:
                candidates.append((days, line.id, line))
        candidates.sort(key=lambda c: (c[0], c[1]))
        candidates = [line for _, _, line in candidates[:MAX_CANDIDATES]]

        # try small batches first, and stop at the safety cap
        tries = 0
        found = None
        hit_cap = False
        for size in range(MIN_LINES, min(MAX_LINES, len(candidates)) + 1):
            for combo in combinations(candidates, size):
                tries += 1
                if tries > MAX_TRIES:
                    hit_cap = True
                    break
                if sum(line.amount_pence for line in combo) == target:
                    found = combo
                    break
            if found or hit_cap:
                break

        if found is None:
            if hit_cap:
                skipped.append(bank_line.id)
            continue

        same_ref = all(line.reference == bank_line.reference for line in found)
        confidence = 0.95 if same_ref else 0.80
        ids = [line.id for line in found]
        why = f"{len(found)} cashbook lines add up to {fmt(target)} ({', '.join(ids)})"
        if same_ref:
            why += f", all with reference {bank_line.reference}"

        matches.append(Match(
            bank_ids=[bank_line.id],
            ledger_ids=ids,
            rule="batch_sum",
            confidence=confidence,
            explanation=why,
        ))
        free_bank.remove(bank_line)
        for line in found:
            free_book.remove(line)

    return matches, free_bank, free_book, skipped


def main():
    bank_lines = load_transactions("data/sample/mock_bank_statement.csv", "bank")
    book_lines = load_transactions("data/sample/mock_cashbook.csv", "cashbook")
    _, left_bank, left_book = find_matches(bank_lines, book_lines)
    matches, left_bank, left_book, skipped = find_batch_matches(left_bank, left_book)

    print("BATCH MATCHES")
    for m in matches:
        print(f"  {m.bank_ids[0]} <-> {', '.join(m.ledger_ids)}  {m.rule}  {m.confidence}")
        print(f"    {m.explanation}")
    print("STILL UNMATCHED BANK LINES:", ", ".join(t.id for t in left_bank))
    print("STILL UNMATCHED CASHBOOK LINES:", ", ".join(t.id for t in left_book))
    if skipped:
        print("SEARCH STOPPED AT THE SAFETY CAP FOR:", ", ".join(skipped))


if __name__ == "__main__":
    main()
    