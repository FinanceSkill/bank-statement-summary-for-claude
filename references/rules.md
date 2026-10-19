# Tranbank row rules

Workers apply these when they build rows. Reviewers check rows against them. The column definitions, the reconciliation formula and the never-invent rule are in `../SKILL.md`.

## Rows and periods
- **One row per account, per currency, per statement period.** The period is normally a calendar month.
  - A consolidated statement gives several rows.
  - Different periods are never merged.
- **Period** (`"YYYY-MM"`) comes from the statement's own dates. File names and folders are often wrong.
  - If the range is not a calendar month (a credit-card cycle, a statement dated the 10th), use the month the transactions fall in, and write the exact range in Notes.
  - If one PDF spans several months and prints a running balance, make one row per month. The month-end balance is the printed balance after that month's last transaction.
  - Otherwise make one row for the whole span and note it.
- **Duplicates**: the same account and period can appear in two files, e.g. one file in two folders, a re-issued statement, or an overlapping multi-month file.
  - Make one row.
  - Put the other file in skipped.json, with the matching figures as evidence.
  - If two files cover consecutive parts of one month and their balances chain, make one row and list both in Source File, joined with ` | `.
- **Not a statement**: a ".pdf" that is really an image, an online-banking screen print, a notice or letter, a payment advice, or a single transfer confirmation.
  - Skip it.
  - Exception: if it covers a month that no statement covers, and it shows that whole month's transactions and a balance, use it and say so in Notes.

## Balances and totals
- **Opening / Closing**: ยอดยกมา / Balance B/F / Beginning Balance, and ยอดยกไป / Balance C/F / Ending Balance.
  - If there is no explicit line, the opening is the balance before the first transaction (balance − credit + debit of row 1), and the closing is the last balance shown.
  - Add the note "opening derived from first transaction".
- **No transactions in the period**:
  - If a balance is printed: Opening = Closing = the printed balance, totals 0, and the note "no transactions in period".
  - If no balance is printed at all (e.g. SCB "No Data Available"): leave both balances blank. A neighbouring month's balance may go in Notes "for reference" only, never in the cell.
- **Totals**:
  - Prefer the statement's summary lines (Total Deposits / รวมฝาก, Total Withdrawals / รวมถอน), then move interest, bonus and WHT out of them.
  - With no summary, sum the printed lines and add the note "totals summed from transactions".
- **Interest / Bonus / WHT**: scan the descriptions.
  - Interest: `INT`, `ดอกเบี้ย`, `Interest Credit`, `CR INT`.
  - WHT: `WHT`, `TAX`, `ภาษี`, `หักภาษี ณ ที่จ่าย`.
  - Bonus: bonus, reward, cashback, referral, promotion.
  - Interest printed net, with the tax only in a footnote: record gross interest and the tax separately if both are shown. Otherwise record what is shown and note it.
  - Tax payments to the Revenue Department are ordinary withdrawals, not WHT.
- **Amounts**:
  - Write them as strings exactly as printed; commas are fine.
  - Keep every printed decimal; crypto may carry 8 or more.
  - Withdrawal and WHT are positive.
  - Watch for separate debit and credit columns, negatives in brackets, and text extraction that merges adjacent columns. Cross-check any suspicious number against the table dump or the rendered page.
- **A row that doesn't reconcile** (`Opening + Deposit − Withdrawal + Interest + Bonus − WHT ≠ Closing`):
  - Go back to the statement and look for a missed page, interest counted twice, a misread digit or a merged column.
  - Fix what the statement supports. Otherwise keep the numbers as printed and say why in Notes.
  - Leave every figure as the statement shows it, even when the formula stays unbalanced.

## Field conventions
Keep these identical across groups and batches.
- **Account Name**: as printed, keeping the original spelling.
- **Bank Name**: the institution's full English name as printed, not the logo text.
  - If the bank shows only as a logo, confirm it from the domain, SWIFT code or footer, and note it.
  - Use the same name for the same bank across groups and batches. If earlier Tranbank output exists, reuse its names.
  - Thai banks use these names: Kasikornbank, Siam Commercial Bank, Krungthai Bank, Bangkok Bank, Krungsri (Bank of Ayudhya), United Overseas Bank (Thai), Krungthai Card (KTC).
  - When a bank books through a separate legal entity (e.g. an Islamic banking arm), use the entity printed on the statement.
- **Account type**: one of Savings, Current, Fixed Deposit, Foreign Currency Deposit, Credit Card, E-money Account, Crypto Wallet, Investment Account.
  - When the statement prints a type, follow it, e.g. "Current Accounts" or "Savings Accounts".
  - When none fits, use the statement's own wording.
  - Payment and e-money providers that are not banks use E-money Account, e.g. Wise, PayPal or Stripe balances.
  - Fiat sub-accounts of a multi-currency account use Current, unless the statement says otherwise.
  - Crypto sub-accounts use Crypto Wallet.
  - Brokers and investment platforms use Investment Account.
- **Product**: the product name as printed, else blank. For crypto, put the network here, e.g. "USDT TRC20" or "USDC ERC20".
- **Currency**: the ISO 4217 code.
  - Crypto keeps its ticker (USDT, BTC, SOL, TON …).
  - A multi-currency account gives one row per currency.
- **Acc No.**, in order of preference:
  1. The account number as printed, with dashes and leading zeros.
  2. The IBAN or wallet ID as printed.
  3. Blank, with a note. An IBAN printed in another month may go in Notes for reference.
- **Credit cards**:
  - Opening = −(previous balance owed). Closing = −(new balance owed).
  - Deposit = payments + credits and refunds.
  - Withdrawal = purchases + fees + interest charged + cash advances.
  - Leave Interest Income blank.
  - Add the note "credit card: balance owed shown as negative".
- **Brokers / investment platforms**:
  - Opening and Closing are the cash balance or the total value, as the statement reports it. Say which in Notes.
  - Deposit and Withdrawal hold only real transfers in and out.
  - Interest credited goes to Interest Income.
  - Trading P&L, fees and FX revaluation fit no column. Write their amounts in Notes, so the reconciliation gap is explained.
- **Internal transfers** between the holder's own accounts stay in Deposit or Withdrawal. Name the counterparty account in Notes when it is obvious.
- **Notes**: short strings in English.
