#!/usr/bin/env python3
"""Dump the text (and tables) of bank statement files so they can be read and classified.

Usage:
    python3 extract_text.py <file> [<file> ...] [--password PASS] [--out DIR]

Supports .pdf (pdfplumber), .xlsx/.xlsm (openpyxl), .csv/.txt.
For each input, prints a header line, then the content page by page.
A PDF page with no extractable text is reported as "[NO TEXT - likely scanned image]"
so the caller knows to read that page visually instead.
With --out, also writes <out>/<basename>.txt for each input.
"""
import argparse
import csv
import logging
import os
import sys


def dump_pdf(path, password):
    import pdfplumber

    lines = []
    with pdfplumber.open(path, password=password or None) as pdf:
        for i, page in enumerate(pdf.pages, 1):
            lines.append(f"===== PAGE {i}/{len(pdf.pages)} =====")
            text = (page.extract_text() or "").strip()
            lines.append(text if text else "[NO TEXT - likely scanned image]")
            for t_idx, table in enumerate(page.extract_tables() or [], 1):
                lines.append(f"----- table {t_idx} (page {i}) -----")
                for row in table:
                    lines.append(" | ".join("" if c is None else str(c).replace("\n", " ") for c in row))
    return lines


def dump_xlsx(path):
    import openpyxl

    lines = []
    wb = openpyxl.load_workbook(path, data_only=True, read_only=True)
    for ws in wb.worksheets:
        lines.append(f"===== SHEET {ws.title} =====")
        for row in ws.iter_rows(values_only=True):
            if any(c is not None and str(c).strip() for c in row):
                lines.append(" | ".join("" if c is None else str(c) for c in row))
    return lines


def dump_csv(path):
    for enc in ("utf-8-sig", "cp874", "latin-1"):
        try:
            with open(path, newline="", encoding=enc) as f:
                return [f"===== CSV ({enc}) ====="] + [" | ".join(r) for r in csv.reader(f)]
        except UnicodeDecodeError:
            continue
    return ["[could not decode file]"]


def main():
    logging.disable(logging.WARNING)  # pdfminer font warnings drown the real output
    ap = argparse.ArgumentParser()
    ap.add_argument("files", nargs="+")
    ap.add_argument("--password", default="")
    ap.add_argument("--out", default="")
    args = ap.parse_args()

    for path in args.files:
        ext = os.path.splitext(path)[1].lower()
        try:
            if ext == ".pdf":
                lines = dump_pdf(path, args.password)
            elif ext in (".xlsx", ".xlsm"):
                lines = dump_xlsx(path)
            elif ext in (".csv", ".txt"):
                lines = dump_csv(path)
            else:
                lines = [f"[unsupported file type {ext}]"]
        except Exception as e:  # report and keep going with the other files
            msg = str(e) or e.__class__.__name__
            if "password" in msg.lower() or e.__class__.__name__ in ("PdfminerException", "PDFPasswordIncorrect"):
                msg += "  -> file is probably password-protected; rerun with --password"
            lines = [f"[ERROR reading file: {msg}]"]

        out = "\n".join([f"######## FILE: {path}"] + lines) + "\n"
        sys.stdout.write(out)
        if args.out:
            os.makedirs(args.out, exist_ok=True)
            with open(os.path.join(args.out, os.path.basename(path) + ".txt"), "w", encoding="utf-8") as f:
                f.write(out)


if __name__ == "__main__":
    main()
