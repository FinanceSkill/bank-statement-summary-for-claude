# Tranbank

A [Claude Code](https://claude.com/claude-code) skill that turns bank statements into one summary CSV per month. It handles PDF, scanned PDF, Excel and CSV statements, in Thai or English, from any bank. The CSV has **one row per account, per currency, per month** and a fixed set of 14 columns, ready for accounting work.

> **ภาษาไทย:** สกิลสำหรับ Claude Code ที่แปลงสเตตเมนต์ธนาคาร (PDF, PDF สแกน, Excel, CSV ภาษาไทยหรืออังกฤษ) เป็น CSV สรุปรายบัญชีรายเดือน 14 คอลัมน์
> - ทุกแถวกระทบยอดได้ และห้ามแต่งตัวเลข: ถ้าสเตตเมนต์ไม่มีตัวเลขนั้น จะเว้นว่างและเขียนเหตุผลไว้
> - Sonnet ทำงาน และ Opus ตรวจทุกกลุ่มเทียบกับสเตตเมนต์จริง

## Output

The columns, in this order:

`NO, Account Name, Product, Bank Name, Account type, Acc No., Opening Balance, Total Deposit, Total Withdrawal, Interest Income, Bonus, Withholding Tax, Currency, Closing Balance`

Interest, bonus and withholding tax have their own columns, so they are kept out of the deposit and withdrawal totals. Every row is then checked with:

```
Opening + Deposit − Withdrawal + Interest + Bonus − Withholding Tax = Closing
```

**Never invent a number.** If a value isn't in the statement, its cell is left blank and the reason goes in the notes file. The only derived figures are sums of printed transactions, and each is labelled as summed.

The output folder holds:
- `tranbank_<YYYY-MM>.csv`: one per month, UTF-8 with BOM so Thai displays correctly in Excel.
- `tranbank_<YYYY-MM>_notes.csv`: every blank cell, every row that doesn't reconcile, and the notes for each row.
- `tranbank_skipped_files.csv`: each input file that produced no row (duplicate, empty, not a statement, …), with the evidence and what to do next. Written in Thai.

## How it works

```
orchestrator (main session)
  1 collect files ─ 2 extract text ─ 3 group by bank layout
                                         │
                ┌────────────────────────┼────────────────────────┐
           worker (Sonnet)          worker (Sonnet)          worker (Opus*)     rows.json + skipped.json
                │                        │                        │
           reviewer (Opus)          reviewer (Opus)          reviewer (Opus)    review.json: pass / fix
                │ fix → same worker → re-check (≤ 2 rounds, then an Opus worker for what's left)
                └────────────────────────┼────────────────────────┘
  5 merge: one CSV per month + coverage, duplicate and balance-chain checks ─ 6 report
```

| Role | Model | Does |
|---|---|---|
| Orchestrator | your session | extracts, groups, dispatches, runs the review loop, merges, reports |
| Worker | Sonnet by default | turns one group of statements into rows |
| Reviewer | always Opus | checks the rows against the statements; reports findings, never edits |

\* A worker runs on Opus when its group is mostly scanned images, has no summary or balance lines, or holds consolidated statements that are hard to split by account. No worker runs below Sonnet: a misread digit costs more than the tokens saved.

## Requirements

- Claude Code with subagents (the Agent tool), and access to Sonnet and Opus.
- Python 3.9+ with `pdfplumber` (PDF) and `openpyxl` (Excel):
  ```bash
  pip install pdfplumber openpyxl
  ```

## Install

```bash
git clone https://github.com/sinuthotmail/tranbank ~/.claude/skills/tranbank
```

## Use

In Claude Code:

```
/tranbank ~/Downloads/statements.zip ~/Downloads/kbank-2026-09.pdf  PDF only
```

You can also ask in plain words, e.g. "แปลง statement พวกนี้เป็น CSV". The skill triggers on its own.

- **Passwords:** PDF passwords written in file names as `PW<token>` are used automatically. For any other password the skill asks you once, for all files together.
- **Zips:** zips from Windows that store Thai file names in a non-UTF-8 encoding are handled.

## Files

| Path | What |
|---|---|
| `SKILL.md` | roles, model choice, and the orchestrator's workflow |
| `references/rules.md` | row rules: periods, duplicates, balances, totals, interest/WHT, field conventions |
| `references/worker.md` | the worker's brief |
| `references/review.md` | the reviewer's brief |
| `scripts/unzip_statements.py` | extract zips: decode Thai file names, handle nested zips, try `PW<token>` passwords |
| `scripts/bulk_extract.py` | text and tables of every file, mirrored into a text tree, 8 files in parallel |
| `scripts/extract_text.py` | text and tables of a single file |
| `scripts/write_csv.py` | write the CSV template, check reconciliation, write the notes file |
| `scripts/merge.py` | merge the worker groups and write the per-month CSVs and the skipped list; checks coverage, duplicates and the month-to-month balance chain |

## Privacy

During a session, Claude reads the statement contents, the same as any file you open in Claude Code. The output CSVs hold account numbers and balances. Keep statements and outputs out of this repository: the included `.gitignore` excludes PDFs, zips, CSVs, spreadsheets and images.

## Status

This is step 1 of a multi-step process. Later steps will build on this CSV, so the column names and their order are fixed.
