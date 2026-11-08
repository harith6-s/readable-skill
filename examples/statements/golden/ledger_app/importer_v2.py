"""Import a bank or card statement file into the ledger.

import_bank_statement(path)
  1. Load and parse the lines   -> storage.read_lines
  2. Drop rows with a zero amount (each one is reported in errors)
  3. Post the remaining rows    -> ledger.post("cash", amount, memo), once per row, in file order
  4. Return the summary

import_card_statement(path)
  The same four steps. The sign of the amount is flipped at step 1 and the account is "card".

The answer for "nobody outside this repository uses StatementImporter or CardImporter": the classes are gone,
so a caller outside must switch to the two functions (PIN(integrate)).
"""

from ledger_app import ledger, storage

CASH_ACCOUNT = "cash"
CARD_ACCOUNT = "card"


def import_bank_statement(path):
    # PIN(behavior): the old StatementImporter("bank") stored `source` and nothing ever read it
    source = "bank"

    # --- 1. Load and parse the lines (was: load, parse_row) ---
    rows = []
    for line in storage.read_lines(path):
        date, amount, memo = line.split(",")
        rows.append({"date": date, "amount": float(amount), "memo": memo})

    # --- 2. Drop rows with a zero amount (was: validate) ---
    good, errors = _drop_zero_rows(rows)

    # --- 3. Post the remaining rows (was: post) ---
    for row in good:
        ledger.post(CASH_ACCOUNT, row["amount"], row["memo"])

    # --- 4. Return the summary (was: run) ---
    return {"posted": len(good), "errors": errors}


def import_card_statement(path):
    # PIN(behavior): the old CardImporter("card") stored `source` and nothing ever read it
    source = "card"

    # --- 1. Load and parse the lines, flipping the sign (was: load, CardImporter.parse_row) ---
    rows = []
    for line in storage.read_lines(path):
        date, amount, memo = line.split(",")
        rows.append({"date": date, "amount": -float(amount), "memo": memo})

    # --- 2. Drop rows with a zero amount (was: validate) ---
    good, errors = _drop_zero_rows(rows)

    # --- 3. Post the remaining rows (was: post) ---
    for row in good:
        ledger.post(CARD_ACCOUNT, row["amount"], row["memo"])

    # --- 4. Return the summary (was: run) ---
    return {"posted": len(good), "errors": errors}


def _drop_zero_rows(rows):
    good, errors = [], []
    for row in rows:
        if row["amount"] == 0:
            errors.append(f"zero amount on {row['date']}")
        else:
            good.append(row)
    return good, errors
