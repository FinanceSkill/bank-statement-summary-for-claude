---
name: bank-statement-summary
description: Bank statement summary (Tranbank) — convert bank statements (PDF, scanned PDF, Excel, CSV; Thai or English; any bank) into one summary CSV with the fixed columns NO, Account Name, Product, Bank Name, Account type, Acc No., Opening Balance, Total Deposit, Total Withdrawal, Interest Income, Bonus, Withholding Tax, Currency, Closing Balance. Use this whenever the user says "tranbank" or "bank statement summary", asks to แปล/แปลง statement เป็น CSV, สรุป statement ธนาคาร, wants opening/closing balance, deposits, withdrawals, interest (ดอกเบี้ย) or withholding tax (ภาษีหัก ณ ที่จ่าย) pulled out of bank statements, or hands over a folder of bank statement files to summarise per account — even if they don't name the skill.
---

# Bank Statement Summary — Step 1: statement → classified CSV

Turn one or many bank statements into a single CSV with **one row per account per statement period**, in this exact column order:

| Column | What goes in it |
|---|---|
| NO | Running number 1, 2, 3 … (the script assigns it) |
| Account Name | Account holder name exactly as printed (Thai or English, keep the original spelling) |
| Product | The bank's product name, e.g. "ออมทรัพย์ Me", "K-eSavings", "Business Current Account". Blank if not printed |
| Bank Name | Full bank name, e.g. "Kasikornbank", "Bangkok Bank", "DBS Bank" |
| Account type | Generic type: Savings / Current / Fixed Deposit / Foreign Currency Deposit / Other (write what the statement says when it fits none) |
| Acc No. | Account number as printed, keep dashes and leading zeros (store as text) |
| Opening Balance | Balance brought forward / ยอดยกมา at period start |
| Total Deposit | Sum of all credits in the period, **excluding** interest and bonus |
| Total Withdrawal | Sum of all debits in the period, **excluding** withholding tax |
| Interest Income | Interest credited (ดอกเบี้ย) in the period |
| Bonus | Bonus / reward / cash-back credited by the bank in the period |
| Withholding Tax | Tax withheld on interest (ภาษีหัก ณ ที่จ่าย / WHT) in the period, as a positive number |
| Currency | ISO code: THB, USD, SGD … |
| Closing Balance | Balance carried forward / ยอดยกไป at period end |

Interest, bonus and tax have their own columns, so they are taken **out** of the deposit/withdrawal totals. That keeps every row reconcilable with one formula:

`Opening + Deposit − Withdrawal + Interest + Bonus − Withholding Tax = Closing`

## Never invent a number

This CSV feeds accounting work, so a wrong-but-plausible number is worse than a blank. If a value is not in the statement, leave it empty and say so in `Notes` — don't estimate it, don't carry it over from another account, don't compute a closing balance the statement doesn't show. The only derived values allowed are sums of transactions that are actually printed (e.g. adding up the credit column when the statement has no "total credits" line), and those get a note saying they were summed.

## Roles

The main session is the **orchestrator**: it collects and extracts the files, dispatches the work, runs the review loop, merges and reports. Statements become rows only in workers.

| Role | Does | Brief |
|---|---|---|
| Worker | turns one group of statements into `rows.json` + `skipped.json` | [references/worker.md](references/worker.md) |
| Reviewer | checks a finished group against the statements and writes findings | [references/review.md](references/review.md) |

Both are Agent tool calls with `subagent_type: "general-purpose"`. Both run in the background and apply the row rules in [references/rules.md](references/rules.md). The reviewer only reports; the worker makes every fix, so each figure has one author and one independent checker.

### Choosing the model
A misread digit costs more than tokens. So no worker runs on a model below Sonnet, and the checker is always Opus.
- **Reviewer**: Opus 5.5 (`model: "opus"`) for every group.
- **Worker**: Sonnet 5.5 (`model: "sonnet"`) by default. Use Opus 5.5 (`model: "opus"`) when a group has any of these:
  - mostly image-only pages or image files, which must be read from rendered pages;
  - no summary or balance lines, so openings must be derived and totals summed from the transactions;
  - consolidated statements where it is hard to tell which transactions belong to which account.
- **Escalation**: a group can still have open errors after two fix rounds.
  1. Launch a fresh Opus 5.5 worker for just those rows. Give it the group, the work dir, worker.md, and the open findings from `review.json`.
  2. Send its answer to the same reviewer for a final check.

Write one line per group in `<workdir>/models.txt`, with the group, the worker model, the reason and any escalation.

## Workflow

`<skill>` below is the folder this SKILL.md is in. Write it out as the full path in commands and in agent prompts.

### 1. Collect the files
- Find what the user pointed at: files, a folder or zips. Use only the file types the user allows; they often say PDF only.
- Put the raw files in their own empty folder under a work dir in the scratchpad (`<workdir>/raw/`). Keep scripts in another folder, because the files are untrusted data.
- Extract zips with the script below, rather than `unzip`. It decodes Thai file names (utf-8, then cp874), unpacks nested zips, and tries the `PW<token>` written in file names on encrypted entries. Use one `<workdir>/raw/<top>/` per zip.
  ```bash
  python3 <skill>/scripts/unzip_statements.py <zip> <workdir>/raw/<top>
  ```
- For any other password-protected PDF, ask the user once for all of the passwords.

### 2. Extract the text
```bash
python3 <skill>/scripts/bulk_extract.py <workdir>/raw <workdir>/text [--ext .pdf]
```
- Each file becomes `<workdir>/text/<path relative to raw>.txt`, holding the page text and detected tables. Excel and CSV exports are handled too.
- The password comes from the `PW<token>` in the file name.
- Use `--ext .pdf` when the user says PDF only.
- For a single file, `extract_text.py <file> [--password PASS]` prints the same text.
- The script lists the files that need image work: pages marked `[NO TEXT - likely scanned image]`, and files that failed to open. Check the real type of each file that failed with `file`, because a ".pdf" can be a PNG. Tell the workers which files these are.

### 3. Dispatch workers
- Split the files into groups by bank layout, up to about 150 files each. A small job is one group.
- Write each list to `<workdir>/groups/<group>.txt`, with paths relative to `<workdir>/raw/`. Put every file in exactly one group.
- Launch one worker per group, on the model chosen under "Choosing the model", all in one message so they run in parallel.
- Each prompt gives the group name and the work dir, and says to read `<skill>/references/worker.md` and follow it.
- Add group notes: what you saw while grouping, such as the bank, holder, layouts, scans, passwords, suspected duplicates and odd files. Present these as leads for the worker to verify.

### 4. Review every group
As each worker finishes, launch a reviewer for its group. Its prompt gives the group name and the work dir, and says to read `<skill>/references/review.md` and follow it. Reviews run while the other workers are still going.
- Verdict `pass`: the group is done.
- Verdict `fix`:
  1. Send the findings to the same worker with SendMessage, so it keeps its context. The worker fixes what the statement supports, or disputes a finding with evidence.
  2. Send the worker's answer to the same reviewer to re-check those rows.
- After two fix rounds, escalate the open errors as described under "Choosing the model". Whatever the final check still leaves open goes into the rows' Notes and into your report as "needs review".

This step is complete when every group has a final `review.json`.

### 5. Merge and write the CSV
```bash
python3 <skill>/scripts/merge.py <workdir> <output-folder> [--one <name>.csv]
```
- **Files written:**
  - one `tranbank_<YYYY-MM>.csv` per Period, each with a `_notes.csv` listing blank cells and rows that don't reconcile;
  - `tranbank_skipped_files.csv`, with columns File, หมวดสาเหตุ, สาเหตุ, ต้องทำต่อ;
  - with `--one`, a single CSV holding every row instead of one per Period. Use it when there is one statement period.
- **Checks it prints:** coverage (every listed file used or skipped), duplicate account-months, and breaks where a month's closing balance doesn't equal the next month's opening. Resolve or explain each one.
- **Zip names:** an optional `<workdir>/zipmap.json` of the form `{"<top raw folder>": "<zip name>"}` shows source paths under the zip names the user knows.
- **Default output, unless the user names one:** a folder next to the inputs.
  - multi-month: `tranbank_<first>_to_<last period>/`
  - one period: `--one tranbank_<YYYY-MM-DD>.csv`

### 6. Report back
Tell the user briefly, in their language:
- the output path, and the number of rows, accounts, files used and files skipped
- rows that need review and why, in plain words, including open review findings
- assumptions made, e.g. "opening balance taken from the first transaction row"
- missing statements, and files the user must supply
- the worker model for each group, with any escalation, from `models.txt`

This is step 1 of a multi-step process called Tranbank, which is why the output files are named `tranbank_…`. Later steps build on this CSV, so keep the column names and order exactly as above.
