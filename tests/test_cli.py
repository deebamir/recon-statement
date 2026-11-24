from pathlib import Path

from recon_statement.cli import main

SAMPLE = Path(__file__).resolve().parent.parent / "data" / "sample"


def sample_args(out_dir, terms="UK"):
    return ["--bank", str(SAMPLE / "mock_bank_statement.csv"),
            "--cashbook", str(SAMPLE / "mock_cashbook.csv"),
            "--balances", str(SAMPLE / "mock_balances.csv"),
            "--terms", terms, "--out", str(out_dir)]


def test_cli_runs_and_writes_the_uk_excel_file(tmp_path, capsys):
    assert main(sample_args(tmp_path)) == 0
    assert (tmp_path / "reconciliation_UK.xlsx").exists()
    text = capsys.readouterr().out
    assert "DOES NOT AGREE" in text
    assert "AGREED: the books and the bank now tell the same story." in text


def test_cli_us_terms_change_the_wording(tmp_path, capsys):
    assert main(sample_args(tmp_path, "US")) == 0
    assert (tmp_path / "reconciliation_US.xlsx").exists()
    assert "Adjusted book balance" in capsys.readouterr().out


def test_cli_reports_a_missing_file(tmp_path, capsys):
    code = main(["--bank", str(tmp_path / "nope.csv"), "--out", str(tmp_path)])
    assert code == 2
    assert "File not found" in capsys.readouterr().out