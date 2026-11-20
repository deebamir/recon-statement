from recon_statement import batch
from recon_statement.batch import find_batch_matches
from recon_statement.matcher import find_matches


# ---------- one-to-one matcher ----------

def test_finds_the_five_one_to_one_matches(bank_lines, book_lines):
    matches, left_bank, left_book = find_matches(bank_lines, book_lines)
    pairs = {(m.bank_ids[0], m.ledger_ids[0]) for m in matches}
    assert pairs == {("BK01", "CB01"), ("BK02", "CB02"), ("BK03", "CB03"),
                     ("BK04", "CB04"), ("BK06", "CB08")}


def test_every_match_is_explainable(bank_lines, book_lines):
    matches, _, _ = find_matches(bank_lines, book_lines)
    for m in matches:
        assert m.rule
        assert 0 < m.confidence <= 1
        assert m.explanation


def test_duplicate_cheque_is_left_unmatched(bank_lines, book_lines):
    _, _, left_book = find_matches(bank_lines, book_lines)
    assert "CB09" in [t.id for t in left_book]
    assert "CB08" not in [t.id for t in left_book]


def test_each_line_is_used_once(bank_lines, book_lines):
    matches, _, _ = find_matches(bank_lines, book_lines)
    bank_ids = [i for m in matches for i in m.bank_ids]
    book_ids = [i for m in matches for i in m.ledger_ids]
    assert len(bank_ids) == len(set(bank_ids))
    assert len(book_ids) == len(set(book_ids))


def test_looser_rule_matches_when_reference_differs(make_txn):
    bank = [make_txn("B1", 10, "CREDIT", "AAA", 5000, "bank")]
    book = [make_txn("C1", 12, "Receipt", "BBB", 5000, "cashbook")]
    matches, left_bank, left_book = find_matches(bank, book)
    assert len(matches) == 1
    assert matches[0].rule == "amount_and_close_date"
    assert matches[0].confidence == 0.70


def test_no_match_when_amounts_differ_or_dates_are_far_apart(make_txn):
    bank = [make_txn("B1", 10, "CREDIT", "AAA", 5000, "bank")]
    book = [make_txn("C1", 10, "Receipt", "AAA", 5001, "cashbook"),
            make_txn("C2", 25, "Receipt", "AAA", 5000, "cashbook")]
    matches, left_bank, left_book = find_matches(bank, book)
    assert matches == []
    assert len(left_bank) == 1 and len(left_book) == 2


# ---------- batch matcher ----------

def leftovers(bank_lines, book_lines):
    _, left_bank, left_book = find_matches(bank_lines, book_lines)
    return left_bank, left_book


def test_payroll_run_is_matched_to_three_wages_lines(bank_lines, book_lines):
    left_bank, left_book = leftovers(bank_lines, book_lines)
    matches, new_bank, new_book, skipped = find_batch_matches(left_bank, left_book)

    assert len(matches) == 1
    m = matches[0]
    assert m.bank_ids == ["BK05"]
    assert sorted(m.ledger_ids) == ["CB05", "CB06", "CB07"]
    assert m.rule == "batch_sum"
    assert m.confidence == 0.95
    assert skipped == []
    assert "BK05" not in [t.id for t in new_bank]
    assert "CB05" not in [t.id for t in new_book]


def test_batch_confidence_is_lower_when_references_differ(make_txn):
    bank = [make_txn("B1", 10, "BACS RUN", "Z", -3000, "bank")]
    book = [make_txn("C1", 10, "Wages A", "A", -1000, "cashbook"),
            make_txn("C2", 10, "Wages B", "B", -2000, "cashbook")]
    matches, _, _, _ = find_batch_matches(bank, book)
    assert len(matches) == 1
    assert matches[0].confidence == 0.80


def test_batch_date_window_is_respected(bank_lines, book_lines, monkeypatch):
    monkeypatch.setattr(batch, "WINDOW_DAYS", 0)
    left_bank, left_book = leftovers(bank_lines, book_lines)
    matches, _, _, _ = find_batch_matches(left_bank, left_book)
    assert matches == []


def test_safety_cap_stops_the_search_and_reports_it(bank_lines, book_lines, monkeypatch):
    monkeypatch.setattr(batch, "MAX_TRIES", 1)
    left_bank, left_book = leftovers(bank_lines, book_lines)
    matches, new_bank, _, skipped = find_batch_matches(left_bank, left_book)
    assert matches == []
    assert "BK05" in skipped
    assert "BK05" in [t.id for t in new_bank]


def test_single_lines_are_not_treated_as_batches(make_txn):
    bank = [make_txn("B1", 10, "PAYMENT", "A", -1000, "bank")]
    book = [make_txn("C1", 10, "Payment", "A", -1000, "cashbook")]
    matches, _, _, _ = find_batch_matches(bank, book)
    assert matches == []