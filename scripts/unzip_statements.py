#!/usr/bin/env python3
"""Extract statement zips, decoding Thai file names (utf-8, then cp874) that `unzip` mangles.

usage: unzip_statements.py <zip> <dest-dir>

Nested zips are extracted next to themselves into <name>__unzipped/. Encrypted entries are tried with
the PW<token> found in the entry's or the zip's file name; entries that still fail are listed, not fatal.
"""
import os, re, sys, zipfile

def fixname(info):
    if info.flag_bits & 0x800:          # name already flagged as UTF-8
        return info.filename
    raw = info.filename.encode('cp437')
    for enc in ('utf-8', 'cp874'):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            pass
    return info.filename

def tokens(*names):
    return [m.group(1).encode() for n in names for m in re.finditer(r'PW\s*([0-9A-Za-z]+)', n)]

def extract(zpath, dest):
    n = 0
    with zipfile.ZipFile(zpath) as z:
        for info in z.infolist():
            name = fixname(info)
            if name.endswith('/') or '__MACOSX' in name or name.endswith('.DS_Store'):
                continue
            parts = [p for p in name.split('/') if p not in ('', '.', '..')]
            out = os.path.join(dest, *parts)
            data = None
            for pwd in [None] + tokens(name, os.path.basename(zpath)):
                try:
                    data = z.read(info, pwd=pwd)
                    break
                except RuntimeError:
                    continue
            if data is None:
                print('SKIPPED (encrypted, no working PW<token> in the names):', zpath, '::', name)
                continue
            os.makedirs(os.path.dirname(out), exist_ok=True)
            with open(out, 'wb') as f:
                f.write(data)
            n += 1
            if out.lower().endswith('.zip'):
                print('nested zip:', out)
                n += extract(out, out[:-4] + '__unzipped')
    return n

if __name__ == '__main__':
    print(extract(sys.argv[1], sys.argv[2]), 'files ->', sys.argv[2])
