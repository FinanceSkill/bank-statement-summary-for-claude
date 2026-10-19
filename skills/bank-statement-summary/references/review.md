# Review brief

You review one worker group. Your job is to catch, before the rows reach the accounting CSV, every figure in `rows.json` that the statements don't support. Check against the statements themselves. Treat the worker's parser, notes and reasoning as claims to verify.

Read these first:
- `../SKILL.md`: the columns, the formula and the never-invent rule. Its Roles and Workflow sections belong to the orchestrator.
- `rules.md`: the standard you check rows against.

Inputs, image rendering and the handling of untrusted files are the same as in `worker.md`. Your scripts and images go in `$W/work/<group>/review/`.

Your output is findings. The worker makes every fix, so leave `rows.json`, `skipped.json` and `check.csv` as the worker wrote them.

## Checks
1. **Automated, every row.** Write a script that checks:
   - Opening and Closing appear verbatim in the source dump. If not, the row's Notes explain how they were derived, and the derivation is correct.
   - The row reconciles in write_csv.py.
   - Its totals equal the printed summary (after moving out interest, bonus and WHT) or the sum of the printed lines.
   - Every group file is used or skipped.
   - No account and currency appears twice in one Period.
   - Each account's closing equals its next month's opening.
2. **By hand, against the page.** Read the dump, and for scans the rendered image. Do this for:
   - every row flagged by write_csv.py or by check 1
   - every row read from an image, and every derived or summed figure
   - the first row of each layout
   - every interest, bonus and WHT figure, and any withdrawal that looks like tax
   - a sample of the remaining rows: at least 10% of them, and at least 3
3. **Fields.** Account Name, Acc No., Bank Name, Account type, Product, Currency and Period follow `rules.md` and match the statement.
4. **Skipped files.** Each reason is true:
   - a claimed duplicate really has the same account, period and figures;
   - a "not a statement" file really isn't one;
   - every skipped file truly has no row to give.

You are done when every check above has been run and every row listed in check 2 has been looked at.

## Output: `$W/work/<group>/review.json`
```json
{"verdict": "pass",
 "checked": {"rows": 0, "by_hand": 0, "skips": 0},
 "findings": [{"severity": "error", "file": "...", "period": "YYYY-MM", "acc": "...", "field": "...",
               "found": "...", "expected": "...", "evidence": "page / line / printed text"}]}
```
- `verdict` is `"pass"` or `"fix"`. Any error makes it `"fix"`.
- `severity` is `"error"` or `"warning"`:
  - `error`: the statement contradicts a figure or field, a row is missing or duplicated, or a skip is wrong.
  - `warning`: a convention or note issue that doesn't change a figure.
- `expected` is what the statement shows. Leave it empty when the statement doesn't settle it.

Final reply: the verdict, the counts, and one line per finding.

When asked to re-check, verify only the rows the worker changed or disputed. Update `review.json` and reply the same way.
