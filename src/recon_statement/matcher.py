"""Matching engine: pairs bank lines with cashbook lines, one to one.

Rules run from strictest to loosest. Every match records the rule that
made it, a confidence score and a plain-English explanation.
"""
from recon_statement.loader import load_transactions
from recon_statement.models import Match
from recon_statement.money import fmt

# rule name, confidence, must the reference be the same?, max days apart
RULES = [
    ("exact_amount_and_reference", 0.98, True, 5),
    ("amount_and_close_date", 0.70, False, 3),
]


def find_matches(bank_lines, cashbook_lines):
    """Return (matches, unmatched_bank, unmatched_cashbook)."""
    matches = []
    free_bank = list(bank_lines)
    free_book = list(cashbook_lines)

    for rule_name, confidence, need_reference, max_days in RULES:
        for bank_line in list(free_bank):
            candidates = []
            for book_line in free_book:
                if book_line.amount_pence != bank_line.amount_pence:
                    continue
                if need_reference and book_line.reference != bank_line.reference:
                    continue
                days = abs((bank_line.date - book_line.date).days)
                if days > max_days:
                    continue
                candidates.append((days, book_line))

            if not candidates:
                continue

            # closest date wins; if tied, the lower id wins
            days, best = min(candidates, key=lambda c: (c[0], c[1].id))

            why = f"Same amount {fmt(bank_line.amount_pence)}"
            if need_reference:
                why += f", same reference {bank_line.reference}"
            why += f", {days} day(s) apart"

            matches.append(Match(
                bank_ids=[bank_line.id],
                ledger_ids=[best.id],
                rule=rule_name,
                confidence=confidence,
                explanation=why,
            ))
            free_bank.remove(bank_line)
            free_book.remove(best)

    return matches, free_bank, free_book


def main():
    bank_lines = load_transactions("data/sample/mock_bank_statement.csv", "bank")
    book_lines = load_transactions("data/sample/mock_cashbook.csv", "cashbook")
    matches, left_bank, left_book = find_matches(bank_lines, book_lines)

    print("MATCHES")
    for m in matches:
        print(f"  {m.bank_ids[0]} <-> {m.ledger_ids[0]}  {m.rule}  "
              f"{m.confidence}  ({m.explanation})")

    print("UNMATCHED BANK LINES")
    for t in left_bank:
        print(f"  {t.id}  {t.date}  {t.description}  {fmt(t.amount_pence)}")

    print("UNMATCHED CASHBOOK LINES")
    for t in left_book:
        print(f"  {t.id}  {t.date}  {t.description}  {fmt(t.amount_pence)}")


if __name__ == "__main__":
    main()