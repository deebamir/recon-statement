import csv

from recon_statement import generator
from recon_statement.money import fmt, to_pence


def test_to_pence_converts_pounds_to_whole_pence():
    assert to_pence("12.34") == 1234
    assert to_pence("1200") == 120000
    assert to_pence("-0.05") == -5


def test_money_adds_exactly():
    # with floats, 0.1 + 0.2 is 0.30000000000000004
    assert to_pence("0.10") + to_pence("0.20") == to_pence("0.30")


def test_fmt_shows_pounds_with_commas():
    assert fmt(1234) == "12.34"
    assert fmt(-300000) == "-3,000.00"
    assert fmt(0) == "0.00"


def test_generator_writes_four_mock_files(tmp_path, monkeypatch):
    monkeypatch.setattr(generator, "OUT_DIR", tmp_path)
    generator.main()

    names = {p.name for p in tmp_path.iterdir()}
    assert names == {"mock_bank_statement.csv", "mock_cashbook.csv",
                     "mock_answer_key.csv", "mock_balances.csv"}

    with open(tmp_path / "mock_balances.csv", newline="", encoding="utf-8") as f:
        balances = {row["name"]: int(row["amount_pence"]) for row in csv.DictReader(f)}
    assert balances["bank_closing"] == 671735
    assert balances["cashbook_closing"] == 753600
    assert balances["expected_adjusted_balance"] == 696735


def test_generator_uses_integer_pence_only():
    for line in generator.BANK_LINES + generator.CASHBOOK_LINES:
        assert isinstance(line.amount_pence, int)