# recon-statement

Python tool that matches bank statement lines to cashbook lines and produces the formal **bank reconciliation statement** used in UK and US accounting, proving the difference is nil.

> **Status: early development (v0.1.0 in progress).** Only the project foundations are built so far. See the status table below. All data in this project is **mock data**, clearly labelled, with no real bank or company information.

## The problem

Most open-source reconciliation tools only match rows, and are tied to one ERP or one country. An accountant also needs the formal statement at the end: the cashbook balance adjusted for items the bank has recorded, the bank balance adjusted for timing items, and proof that the two adjusted balances agree.

## What it will do

1. **Statement generator:** build the two-sided reconciliation statement, flag any difference, and export to Excel with a sign-off block (prepared by, reviewed by, date). A config switch picks UK terms (unpresented cheques, outstanding lodgements) or US terms (outstanding checks, deposits in transit).
2. **Batch payment matcher:** find which ledger lines add up to one bank total (BACS runs, payroll, ACH batches), within a date window and with a safety cap so it stays fast.
3. **Exception triage:** classify unmatched items (timing difference, missing bank charge, possible duplicate, transposed digits, reversed sign), suggest a journal entry, and report the ageing of unreconciled items.

Every match will record the rule that produced it and a confidence score, so the result can be explained to an auditor.

## Status

| Phase | What | Status |
|---|---|---|
| 1 | Project structure, money helpers, data models, UK/US terms config | Done |
| 2 | Mock data generator with planted errors | Planned |
| 3 | Matching engine | Planned |
| 4 | Statement generator and Excel output | Planned |
| 5 | Batch payment matcher | Planned |
| 6 | Exception triage and ageing report | Planned |
| 7 | Tests and GitHub Actions | Planned |
| 8 | Documentation and release v0.1.0 | Planned |

## What exists today

- `money.py`: converts amounts to whole **integer pence** and back (12.34 is stored as 1234), so there are no floating-point rounding errors.
- `models.py`: the `Transaction` and `Match` objects.
- `config.py`: UK and US wording for the statement labels.

## How to run

Requires Python 3.10 or newer.

```powershell
git clone https://github.com/deebamir/recon-statement.git
cd recon-statement
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -e .
python -c "from recon_statement.money import to_pence, fmt; print(to_pence('12.34'), fmt(1234))"
```

The last line should print `1234 12.34`. On macOS or Linux, activate with `source .venv/bin/activate` instead.

## Project layout

```
src/recon_statement/   the package
tests/                 automated tests
data/sample/           mock data
docs/design.md         design decisions
```

## Design decisions

- **Money is integer pence.** Never floats.
- **Sign convention:** money in is positive, money out is negative, on both the bank and cashbook sides.
- **Terminology** is held in one config dictionary, so the logic never hardcodes UK or US wording.

See `docs/design.md` for more.

## Assumptions and limitations

- Early-stage project: most features above are planned, not built.
- Mock data only. It has not been tested on real bank files.
- Single currency per reconciliation.
- It is a learning and portfolio project, not accounting software, and does not replace professional judgement.

## Licence

MIT. See [LICENSE](LICENSE).
