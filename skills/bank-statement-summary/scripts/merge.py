#!/usr/bin/env python3
"""Merge the worker groups into the final per-month CSVs.

usage: merge.py <workdir> <output-folder> [--one NAME.csv]

Reads
  <workdir>/groups/<g>.txt          file list per group (paths relative to <workdir>/raw/)
  <workdir>/work/<g>/rows.json      worker rows (with "Period", "Source File", "Notes")
  <workdir>/work/<g>/skipped.json   [{"file", "category", "reason", "next"}]
  <workdir>/zipmap.json             optional {"<top raw folder>": "<zip name>"}: paths are shown as <zip>/<rest>

Writes into <output-folder>
  tranbank_<YYYY-MM>.csv (+ _notes.csv) per Period via write_csv.py, or one NAME.csv with --one
  tranbank_skipped_files.csv        File, หมวดสาเหตุ, สาเหตุ, ต้องทำต่อ

Prints coverage (every listed file used or skipped), duplicate account-months and month-to-month
balance breaks. Exit code 2 when coverage, duplicates or Period values need attention.
"""
import argparse, collections, csv, glob, json, os, re, subprocess, sys
from decimal import Decimal, InvalidOperation

ap = argparse.ArgumentParser()
ap.add_argument('workdir')
ap.add_argument('out')
ap.add_argument('--one', metavar='NAME.csv', help='write every row into this one CSV instead of one per Period')
args = ap.parse_args()
W, OUT = args.workdir, args.out
WRITE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'write_csv.py')
ZIP = json.load(open(f'{W}/zipmap.json', encoding='utf-8')) if os.path.exists(f'{W}/zipmap.json') else {}
ORDER = list(ZIP)
CATEGORIES = ['ซ้ำกับไฟล์ที่ใช้แล้ว', 'ชื่อไฟล์ไม่ตรงเนื้อหา', 'ไฟล์ว่าง', 'ไม่ใช่สเตตเมนต์บัญชี', 'อ่านไม่ได้', 'อื่น ๆ']

def shown(path):
    top, _, rest = path.partition('/')
    return f'{ZIP[top]}/{rest}' if top in ZIP else path

def num(v):
    try:
        return Decimal(str(v).replace(',', '').strip()) if v not in (None, '') else None
    except InvalidOperation:
        return None

rows, skipped, problems, assigned = [], [], [], {}
for gl in sorted(glob.glob(f'{W}/groups/*.txt')):
    g = os.path.basename(gl)[:-4]
    for f in open(gl, encoding='utf-8').read().splitlines():
        if f.strip():
            assigned[f.strip()] = g
    rp, sp = f'{W}/work/{g}/rows.json', f'{W}/work/{g}/skipped.json'
    if not os.path.exists(rp):
        problems.append(f'{g}: rows.json missing')
        continue
    rows += json.load(open(rp, encoding='utf-8'))
    if os.path.exists(sp):
        skipped += json.load(open(sp, encoding='utf-8'))

used = {f.strip() for r in rows for f in str(r.get('Source File') or '').split(' | ') if f.strip()}
skip_files = {s['file'] for s in skipped}
uncovered = [f for f in assigned if f not in used and f not in skip_files]
unknown = sorted((used | skip_files) - set(assigned))

def account(r):
    return tuple(str(r.get(k) or '').strip() for k in ('Account Name', 'Bank Name', 'Acc No.', 'Currency', 'Product'))

for r in rows:
    if not re.fullmatch(r'\d{4}-\d{2}', str(r.get('Period') or '').strip()):
        problems.append(f"row without valid Period: {account(r)} {r.get('Source File')}")
        r['Period'] = 'unknown-period'
dups = [k for k, n in collections.Counter((r['Period'],) + account(r) for r in rows).items() if n > 1]

# Month-to-month chain: closing of one month should equal the opening of the next month.
breaks, series = [], collections.defaultdict(dict)
for r in rows:
    series[account(r)][r['Period']] = r
def month_no(p):
    y, m = p.split('-')
    return int(y) * 12 + int(m)
for acc, ms in series.items():
    ps = sorted(p for p in ms if p != 'unknown-period')
    for p1, p2 in zip(ps, ps[1:]):
        if month_no(p2) - month_no(p1) != 1:
            breaks.append(f'{acc[1]} {acc[2] or "(no acc no)"} {acc[3]}: no row between {p1} and {p2}')
            continue
        c, o = num(ms[p1].get('Closing Balance')), num(ms[p2].get('Opening Balance'))
        if c is not None and o is not None and c != o:
            breaks.append(f'{acc[1]} {acc[2] or "(no acc no)"} {acc[3]}: {p1} closing {c} != {p2} opening {o}')

def sort_key(r):
    top = str(r.get('Source File') or '').split('/')[0]
    return (ORDER.index(top) if top in ORDER else len(ORDER),) + tuple(x.lower() for x in account(r))

def write(batch, json_path, csv_path):
    clean = []
    for r in sorted(batch, key=lambda r: (r['Period'],) + sort_key(r) if args.one else sort_key(r)):
        c = dict(r)
        c['Source File'] = ' | '.join(shown(f.strip()) for f in str(c.get('Source File') or '').split(' | '))
        clean.append(c)
    json.dump(clean, open(json_path, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    res = subprocess.run([sys.executable, WRITE, json_path, csv_path], capture_output=True, text=True)
    open(json_path[:-5] + '_review.txt', 'w', encoding='utf-8').write(res.stdout + res.stderr)
    return len(clean), sum(1 for l in res.stdout.splitlines() if l.strip().startswith('REVIEW'))

os.makedirs(OUT, exist_ok=True)
os.makedirs(f'{W}/merge', exist_ok=True)
print('rows per output file (file, rows, review lines):')
if args.one:
    print('  ', args.one, *write(rows, f'{W}/merge/rows_all.json', os.path.join(OUT, args.one)))
else:
    by_period = collections.defaultdict(list)
    for r in rows:
        by_period[r['Period']].append(r)
    for p in sorted(by_period):
        print('  ', f'tranbank_{p}.csv', *write(by_period[p], f'{W}/merge/rows_{p}.json', f'{OUT}/tranbank_{p}.csv'))

with open(f'{OUT}/tranbank_skipped_files.csv', 'w', newline='', encoding='utf-8-sig') as fh:
    w = csv.writer(fh)
    w.writerow(['File', 'หมวดสาเหตุ', 'สาเหตุ', 'ต้องทำต่อ'])
    order = {c: i for i, c in enumerate(CATEGORIES)}
    for s in sorted(skipped, key=lambda s: (order.get(s.get('category'), len(CATEGORIES)), s['file'])):
        w.writerow([shown(s['file']), s.get('category', ''), s.get('reason', ''), s.get('next', '')])

print(f'total rows {len(rows)} | accounts {len(series)} | listed files {len(assigned)} | used {len(used & set(assigned))} | skipped {len(skipped)}')
for label, items in (('UNCOVERED (neither used nor skipped)', [f'{assigned[f]}: {f}' for f in uncovered]),
                     ('UNKNOWN source paths (not in any group list)', unknown),
                     ('DUPLICATE account-months', [str(d) for d in dups]),
                     ('PROBLEM', problems),
                     ('BALANCE BREAK (check or explain in Notes)', breaks)):
    print(f'{label}: {len(items)}')
    for i in items[:60]:
        print('   ', i)
sys.exit(2 if uncovered or unknown or dups or problems else 0)
