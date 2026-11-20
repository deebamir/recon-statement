from openpyxl import load_workbook

from recon_statement.config import TERMS
from recon_statement.statement import Statement, build_statement, status_text, write_excel


def make_statement(bank_lines, book_lines, balances):
    return build_statement(bank_lines, book_lines,
                           balances["bank_closing"], balances["cashbook_closing"])


def test_adjusted_balances_and_difference(bank_lines, book_lines, balances):
    s = make_statement(bank_lines, book_lines, balances)
    assert s.adjusted_cashbook == 701335  # 7,013.35
    assert s.adjusted_bank == 696735      # 6,967.35
    assert s.difference == 4600           # 46.00, from the planted errors


def test_unresolved_items_are_the_planted_errors(bank_lines, book_lines, balances):
    s = make_statement(bank_lines, book_lines, balances)
    assert [t.id for t in s.unresolved_bank] == ["BK07", "BK08"]
    assert [t.id for t in s.unresolved_book] == ["CB09", "CB10", "CB11"]


def test_timing_and_bank_only_items_are_sorted_correctly(bank_lines, book_lines, balances):
    s = make_statement(bank_lines, book_lines, balances)
    assert [t.id for t in s.unpresented] == ["CB12"]
    assert [t.id for t in s.outstanding] == ["CB13"]
    assert sorted(key for key, _ in s.cashbook_items) == [
        "bank_charges", "bank_interest", "direct_debits", "dishonoured"]


def test_difference_is_flagged(bank_lines, book_lines, balances):
    s = make_statement(bank_lines, book_lines, balances)
    assert "DOES NOT AGREE" in status_text(s)
    assert "46.00" in status_text(s)


def test_balanced_statement_says_agreed():
    s = Statement(100000, 100000, [], [], [], [], [])
    assert s.difference == 0
    assert status_text(s).startswith("AGREED")


def test_uk_and_us_terms_have_the_same_keys():
    assert TERMS["UK"].keys() == TERMS["US"].keys()
    assert TERMS["UK"]["unpresented"] == "Unpresented cheques"
    assert TERMS["US"]["unpresented"] == "Outstanding checks"
    assert TERMS["UK"]["outstanding_deposits"] == "Outstanding lodgements"
    assert TERMS["US"]["outstanding_deposits"] == "Deposits in transit"


def sheet_text(path):
    ws = load_workbook(path)["Reconciliation"]
    return " | ".join(str(cell.value) for row in ws.iter_rows()
                      for cell in row if cell.value is not None)


def test_excel_uk_has_uk_terms_and_signoff(bank_lines, book_lines, balances, tmp_path):
    s = make_statement(bank_lines, book_lines, balances)
    path = tmp_path / "uk.xlsx"
    write_excel(s, path, "UK")
    text = sheet_text(path)
    assert "Unpresented cheques" in text
    assert "Outstanding lodgements" in text
    assert "Prepared by" in text
    assert "Reviewed by" in text
    assert "DOES NOT AGREE" in text


def test_excel_us_uses_us_terms(bank_lines, book_lines, balances, tmp_path):
    s = make_statement(bank_lines, book_lines, balances)
    path = tmp_path / "us.xlsx"
    write_excel(s, path, "US")
    text = sheet_text(path)
    assert "Outstanding checks" in text
    assert "Deposits in transit" in text
    assert "Unpresented cheques" not in text


def test_excel_balances_are_correct(bank_lines, book_lines, balances, tmp_path):
    s = make_statement(bank_lines, book_lines, balances)
    path = tmp_path / "uk.xlsx"
    write_excel(s, path, "UK")
    ws = load_workbook(path)["Reconciliation"]
    values = {row[0]: row[1] for row in ws.iter_rows(values_only=True) if row[0]}
    assert round(float(values["Adjusted cashbook balance"]), 2) == 7013.35
    assert round(float(values["Adjusted bank balance"]), 2) == 6967.35