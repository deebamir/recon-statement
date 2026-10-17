# Design notes

## Money
All amounts are stored as whole integer pence (12.34 is stored as 1234).
Floats are never used, so there are no rounding errors.

## Sign convention
Money in is positive. Money out is negative. This applies to both the bank
side and the cashbook side.

## Data flow
load -> match -> triage -> statement -> Excel

## Core objects
- Transaction: id, date, description, reference, amount_pence, source
- Match: bank ids, ledger ids, rule, confidence, explanation

## UK / US terms
One dictionary in config.py maps neutral keys to UK or US wording, so the
logic never hardcodes labels.