#!/usr/bin/env python3
"""Write classified statement rows to the summary CSV template and check that they reconcile.

Usage:
    python3 write_csv.py <rows.json> <output.csv>

<rows.json> is a JSON list, one object per account per statement period. Keys are the
template column names (see COLUMNS) plus three optional helper keys:
    "Source File"  - the statement file the row came from
    "Period"       - statement period, e.g. "2026-07"; used to split multi-month batches
    "Notes"        - list of strings: anything uncertain, missing or flagged for this row
"NO" is assigned automatically (1, 2, 3 ...) in input order; any value given is ignored.

Amounts may be numbers or strings like "1,234.56", "(1,234.56)", "THB 1,234.56".
null / "" / "-" means "not shown in the statement" and is written as an empty cell.

Writes:
    <output.csv>        - the template, UTF-8 with BOM so Excel shows Thai correctly
    <output>_notes.csv  - every blank cell, reconciliation problem and note, per row
Exit code 0 when everything reconciles, 2 when there are rows to review.
"""
import csv
import json
import os
import re
import sys
from decimal import Decimal, InvalidOperation

COLUMNS = [
    "NO", "Account Name", "Product", "Bank Name", "Account type", "Acc No.",
    "Opening Balance", "Total Deposit", "Total Withdrawal", "Interest Income",
    "Bonus", "Withholding Tax", "Currency", "Closing Balance",
]
AMOUNT_COLS = [
    "Opening Balance", "Total Deposit", "Total Withdrawal", "Interest Income",
    "Bonus", "Withholding Tax", "Closing Balance",
]
# Columns that are commonly absent from a statement; a blank here is reported but not an error.
OPTIONAL_COLS = {"Interest Income", "Bonus", "Withholding Tax", "Product"}
TOLERANCE = Decimal("0.01")


def parse_amount(v):
    if v is None:
        return None
    if isinstance(v, (int, float)):
        return Decimal(str(v))
    s = str(v).strip()
    if s in ("", "-", "--", "N/A", "n/a"):
        return None
    neg = s.startswith("(") and s.endswith(")")
    s = re.sub(r"[^0-9.\-]", "", s)
    try:
        d = Decimal(s)
    except InvalidOperation:
        raise ValueError(f"cannot read amount {v!r}")
    return -d if neg else d


def decimals(d):
    return max(2, -d.as_tuple().exponent) if d is not None else 2


def fmt(d):
    # At least 2 decimals; keep more when the statement prints more (crypto balances).
    return "" if d is None else f"{d:.{decimals(d)}f}"


def main():
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    src, out_csv = sys.argv[1], sys.argv[2]
    with open(src, encoding="utf-8") as f:
        rows = json.load(f)

    notes_path = os.path.splitext(out_csv)[0] + "_notes.csv"
    issues = []  # (NO, Acc No., Source File, Field, Issue)
    out_rows = []

    for n, row in enumerate(rows, 1):
        acc = str(row.get("Acc No.") or "")
        source = str(row.get("Source File") or "")

        def flag(field, msg):
            issues.append((n, acc, source, field, msg))

        unknown = set(row) - set(COLUMNS) - {"Source File", "Notes", "Period"}
        for k in sorted(unknown):
            flag(k, f"unknown key {k!r} ignored - check spelling against the template")

        amounts = {}
        for c in AMOUNT_COLS:
            try:
                amounts[c] = parse_amount(row.get(c))
                # Statements often print debits as negative or (bracketed); the template stores them positive.
                if c in ("Total Withdrawal", "Withholding Tax") and amounts[c] is not None:
                    amounts[c] = abs(amounts[c])
            except ValueError as e:
                amounts[c] = None
                flag(c, str(e))

        out = {"NO": n}
        for c in COLUMNS[1:]:
            if c in AMOUNT_COLS:
                out[c] = fmt(amounts[c])
            else:
                out[c] = "" if row.get(c) is None else str(row.get(c)).strip()
            if out[c] == "":
                level = "not shown in statement (left blank)" if c in OPTIONAL_COLS else "MISSING - left blank, needs review"
                flag(c, level)
        out_rows.append(out)

        o, cl = amounts["Opening Balance"], amounts["Closing Balance"]
        if o is not None and cl is not None:
            z = lambda c: amounts[c] or Decimal(0)
            simple = o + z("Total Deposit") - z("Total Withdrawal")
            full = simple + z("Interest Income") + z("Bonus") - z("Withholding Tax")
            tol = min(TOLERANCE, Decimal(1).scaleb(-max(decimals(v) for v in amounts.values())))
            if abs(full - cl) <= tol:
                pass
            elif abs(simple - cl) <= tol and (z("Interest Income") or z("Bonus") or z("Withholding Tax")):
                flag("Total Deposit/Withdrawal",
                     "interest/bonus/tax seem to be counted inside Total Deposit/Withdrawal too - "
                     "take them out of the totals so they are not double counted")
            else:
                flag("Closing Balance",
                     f"does not reconcile: Opening+Deposit-Withdrawal+Interest+Bonus-Tax = {fmt(full)}, "
                     f"statement Closing = {fmt(cl)}, difference {fmt(cl - full)}")

        for note in row.get("Notes") or []:
            flag("Note", str(note))

    with open(out_csv, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=COLUMNS)
        w.writeheader()
        w.writerows(out_rows)
    with open(notes_path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["NO", "Acc No.", "Source File", "Field", "Issue"])
        w.writerows(issues)

    blocking = [i for i in issues if "MISSING" in i[4] or "reconcile" in i[4] or "double counted" in i[4]
                or "cannot read" in i[4] or "unknown key" in i[4]]
    print(f"Wrote {len(out_rows)} rows -> {out_csv}")
    print(f"Wrote {len(issues)} notes -> {notes_path}")
    for i in blocking:
        print(f"  REVIEW row {i[0]} ({i[1] or 'no acc no'}): {i[3]}: {i[4]}")
    sys.exit(2 if blocking else 0)


if __name__ == "__main__":
    main()
