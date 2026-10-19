"""Tests for the bundled scripts, on synthetic data only (never real statements).

Run: python3 -m unittest discover tests
"""
import csv, json, os, subprocess, sys, tempfile, unittest, zipfile

SCRIPTS = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'skills', 'bank-statement-summary', 'scripts')
COLUMNS = ['NO', 'Account Name', 'Product', 'Bank Name', 'Account type', 'Acc No.', 'Opening Balance', 'Total Deposit',
           'Total Withdrawal', 'Interest Income', 'Bonus', 'Withholding Tax', 'Currency', 'Closing Balance']


def run(script, *args):
    return subprocess.run([sys.executable, os.path.join(SCRIPTS, script), *args], capture_output=True, text=True)


def row(period, source, opening, deposit, closing, acc='111', name='A Co', bank='Siam Commercial Bank',
        currency='THB', product=None, interest=None, wht=None):
    return {'Account Name': name, 'Product': product, 'Bank Name': bank, 'Account type': 'Savings', 'Acc No.': acc,
            'Opening Balance': opening, 'Total Deposit': deposit, 'Total Withdrawal': '0', 'Interest Income': interest,
            'Bonus': None, 'Withholding Tax': wht, 'Currency': currency, 'Closing Balance': closing,
            'Period': period, 'Source File': source, 'Notes': []}


def dump(obj, path):
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(obj, f, ensure_ascii=False)


def write_text(path, text):
    with open(path, 'w', encoding='utf-8') as f:
        f.write(text)


def read_csv(path):
    with open(path, encoding='utf-8-sig') as f:
        return list(csv.reader(f))


class WriteCsvTest(unittest.TestCase):
    def test_columns_reconciliation_and_crypto_decimals(self):
        with tempfile.TemporaryDirectory() as d:
            rows = [row('2026-01', 'a.pdf', '1,000.00', '500.00', '1,510.00', interest='12.00', wht='2.00'),
                    row('2026-01', 'b.pdf', '1.12345678', '1', '2.12345678', acc='', currency='USDT', product='USDT TRC20'),
                    row('2026-01', 'c.pdf', '100.00', '50.00', '999.00', acc='333')]
            dump(rows, f'{d}/rows.json')
            res = run('write_csv.py', f'{d}/rows.json', f'{d}/out.csv')
            self.assertEqual(res.returncode, 2, res.stdout)        # row c does not reconcile
            out = read_csv(f'{d}/out.csv')
            self.assertEqual(out[0], COLUMNS)
            self.assertEqual(out[1][6:14], ['1000.00', '500.00', '0.00', '12.00', '', '2.00', 'THB', '1510.00'])
            self.assertEqual(out[2][6], '1.12345678')               # every printed decimal kept
            self.assertTrue(os.path.exists(f'{d}/out_notes.csv'))


class MergeTest(unittest.TestCase):
    def make_workdir(self, d):
        os.makedirs(f'{d}/groups')
        for g in ('a', 'b'):
            os.makedirs(f'{d}/work/{g}')
        write_text(f'{d}/groups/a.txt', 'z1/a1.pdf\nz1/a2.pdf\nz1/a3.pdf\n')
        write_text(f'{d}/groups/b.txt', 'z2/b1.pdf\nz2/b2.pdf\nz2/b3.pdf\n')
        dump({'z1': 'first.zip', 'z2': 'second.zip'}, f'{d}/zipmap.json')
        dump([row('2026-01', 'z1/a1.pdf', '100.00', '50.00', '150.00'),
              row('2026-02', 'z1/a2.pdf', '140.00', '10.00', '150.00'),      # opening != January closing
              row('2026-04', 'z1/a3.pdf', '150.00', '0', '150.00')],         # March missing
             f'{d}/work/a/rows.json')
        dump([row('2026-01', 'z2/b1.pdf', '5.00', '0', '5.00', name='B Ltd', acc='222'),
              row('2026-01', 'z2/b2.pdf', '5.00', '0', '5.00', name='B Ltd', acc='222')],  # duplicate month
             f'{d}/work/b/rows.json')
        dump([{'file': 'z2/b3.pdf', 'category': 'ซ้ำกับไฟล์ที่ใช้แล้ว', 'reason': 'ซ้ำกับ b1', 'next': 'ไม่ต้องทำอะไร'}],
             f'{d}/work/b/skipped.json')

    def test_per_month_output_and_checks(self):
        with tempfile.TemporaryDirectory() as d:
            self.make_workdir(d)
            res = run('merge.py', d, f'{d}/out')
            self.assertEqual(res.returncode, 2, res.stdout)        # duplicate account-month
            self.assertIn('DUPLICATE account-months: 1', res.stdout)
            self.assertIn('2026-01 closing 150.00 != 2026-02 opening 140.00', res.stdout)
            self.assertIn('no row between 2026-02 and 2026-04', res.stdout)
            self.assertIn('UNCOVERED (neither used nor skipped): 0', res.stdout)
            for p in ('2026-01', '2026-02', '2026-04'):
                self.assertTrue(os.path.exists(f'{d}/out/tranbank_{p}.csv'))
            skipped = read_csv(f'{d}/out/tranbank_skipped_files.csv')
            self.assertEqual(skipped[0], ['File', 'หมวดสาเหตุ', 'สาเหตุ', 'ต้องทำต่อ'])
            self.assertEqual(skipped[1][0], 'second.zip/b3.pdf')  # zip names applied

    def test_one_file(self):
        with tempfile.TemporaryDirectory() as d:
            self.make_workdir(d)
            run('merge.py', d, f'{d}/out', '--one', 'all.csv')
            self.assertEqual(len(read_csv(f'{d}/out/all.csv')), 1 + 5)


class UnzipTest(unittest.TestCase):
    def test_thai_name_without_utf8_flag(self):
        thai = 'สเตตเมนต์-01-2026.pdf'
        with tempfile.TemporaryDirectory() as d:
            # Write the name as raw cp874 bytes with no UTF-8 flag, the way Windows zip tools do.
            info = zipfile.ZipInfo(thai.encode('cp874').decode('cp437'))
            original = zipfile.ZipInfo._encodeFilenameFlags
            zipfile.ZipInfo._encodeFilenameFlags = lambda self: (self.filename.encode('cp437'), self.flag_bits)
            try:
                with zipfile.ZipFile(f'{d}/in.zip', 'w') as z:
                    z.writestr(info, b'%PDF-1.4 test')
            finally:
                zipfile.ZipInfo._encodeFilenameFlags = original
            res = run('unzip_statements.py', f'{d}/in.zip', f'{d}/raw')
            self.assertEqual(res.returncode, 0, res.stderr)
            self.assertTrue(os.path.exists(os.path.join(d, 'raw', thai)), os.listdir(f'{d}/raw'))


if __name__ == '__main__':
    unittest.main()
