#!/usr/bin/env python3
"""Run extract_text.py on every statement under RAW, mirroring the tree as OUT/<relative path>.txt.

usage: bulk_extract.py <raw-dir> <text-dir> [--ext .pdf,.xlsx,.csv]

The password is taken from a PW<token> in the file name when present. 8 files run in parallel.
Prints the files whose dump has an error or an image-only page; those need image work.
"""
import argparse, os, re, subprocess, sys
from concurrent.futures import ThreadPoolExecutor

ap = argparse.ArgumentParser()
ap.add_argument('raw')
ap.add_argument('out')
ap.add_argument('--ext', default='.pdf,.xlsx,.xlsm,.xls,.csv', help='comma-separated extensions to include')
args = ap.parse_args()
EXT = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'extract_text.py')
exts = tuple(e.strip().lower() for e in args.ext.split(','))

jobs = []
for root, _, files in os.walk(args.raw):
    for fn in sorted(files):
        if fn.lower().endswith(exts):
            p = os.path.join(root, fn)
            m = re.search(r'PW\s*([0-9A-Za-z]+)', fn)
            jobs.append((p, m.group(1) if m else '', os.path.join(args.out, os.path.relpath(p, args.raw) + '.txt')))

def run(job):
    p, pw, out = job
    os.makedirs(os.path.dirname(out), exist_ok=True)
    cmd = [sys.executable, EXT, p] + (['--password', pw] if pw else [])
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
        txt = r.stdout + (('\n[STDERR]\n' + r.stderr[-2000:]) if r.returncode else '')
    except subprocess.TimeoutExpired:
        txt = '[ERROR timeout]'
    with open(out, 'w', encoding='utf-8') as f:
        f.write(txt)
    return out, ('ERROR' in txt[:3000] or 'NO TEXT' in txt)

with ThreadPoolExecutor(8) as ex:
    flagged = [o for o, bad in ex.map(run, jobs) if bad]
print(len(jobs), 'files extracted;', len(flagged), 'with errors or image-only pages:')
for o in flagged:
    print('  ', os.path.relpath(o, args.out))
