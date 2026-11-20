from collections import Counter

from recon_statement.triage import ageing, is_transposition, journal_for, triage


def test_nine_exceptions_with_the_expected_categories(bank_lines, book_lines):
    exceptions, _, _ = triage(bank_lines, book_lines)
    counts = dict(Counter(e.category for e in exceptions))
    assert counts == {
        "possible_duplicate": 1, "transposed_digits": 1, "reversed_sign": 1,
        "direct_debit": 1, "dishonoured_cheque": 1, "missing_bank_charge": 1,
        "bank_interest": 1, "timing_difference": 2,
    }


def test_exceptions_match_the_answer_key(bank_lines, book_lines, answer_key):
    exceptions, _, _ = triage(bank_lines, book_lines)
    found = {e.category: e for e in exceptions}

    def ids(text):
        return [part for part in text.split("|") if part]

    for row in answer_key:
        category = row["category"]
        if category in ("transposed_digits", "reversed_sign", "direct_debit",
                        "dishonoured_cheque", "missing_bank_charge", "bank_interest"):
            assert found[category].bank_ids == ids(row["bank_ids"])
            assert found[category].cashbook_ids == ids(row["cashbook_ids"])
        if category == "possible_duplicate":
            # the key lists both cashbook lines; triage flags the second copy
            assert found[category].cashbook_ids == [ids(row["cashbook_ids"])[1]]

    timing = {i for e in exceptions if e.category == "timing_difference"
              for i in e.cashbook_ids}
    key_timing = {row["cashbook_ids"] for row in answer_key
                  if row["category"] in ("unpresented_cheque", "outstanding_lodgement")}
    assert timing == key_timing


def test_every_journal_balances(bank_lines, book_lines):
    exceptions, _, _ = triage(bank_lines, book_lines)
    for e in exceptions:
        debits = sum(d for _, d, _ in e.journal)
        credits = sum(c for _, _, c in e.journal)
        assert debits == credits


def test_journals_bring_the_cashbook_to_the_bank_figure(bank_lines, book_lines, balances):
    exceptions, _, _ = triage(bank_lines, book_lines)
    corrected = balances["cashbook_closing"] + sum(e.cashbook_effect for e in exceptions)
    assert corrected == balances["expected_adjusted_balance"]  # 6,967.35


def test_timing_differences_need_no_journal(bank_lines, book_lines):
    exceptions, _, _ = triage(bank_lines, book_lines)
    for e in exceptions:
        if e.category == "timing_difference":
            assert e.journal == []
            assert e.cashbook_effect == 0


def test_ageing_buckets(bank_lines, book_lines):
    _, left_bank, left_book = triage(bank_lines, book_lines)
    assert ageing(left_bank + left_book) == [
        ("0-7 days", 8, 195735), ("8-14 days", 3, 22400),
        ("15-30 days", 0, 0), ("Over 30 days", 0, 0)]


def test_transposition_detector():
    assert is_transposition(-4500, -5400)
    assert is_transposition(1234, 1243)
    assert is_transposition(1234, 1324)
    assert not is_transposition(4500, -5400)  # different signs
    assert not is_transposition(1234, 4321)   # more than one swap
    assert not is_transposition(1000, 1000)   # identical
    assert not is_transposition(12, 123)      # different lengths


def test_journal_for_direction():
    assert journal_for(900, "X") == [("Cash at bank", 900, 0), ("X", 0, 900)]
    assert journal_for(-900, "X") == [("X", 900, 0), ("Cash at bank", 0, 900)]


def test_item_nothing_explains_is_marked_unexplained(make_txn):
    bank = [make_txn("B1", 10, "MYSTERY PAYMENT", "X1", -12345, "bank")]
    exceptions, _, _ = triage(bank, [])
    assert len(exceptions) == 1
    assert exceptions[0].category == "unexplained"
    assert exceptions[0].bank_ids == ["B1"]