"""
Tests for the CSV import module

Run from the folder containing cisco_cdr_analyzer:
    python -m unittest discover -s cisco_cdr_analyzer/tests -t .
"""

import os
import shutil
import tempfile
import unittest
from pathlib import Path

from cisco_cdr_analyzer import CiscoCDRAnalyzer, CSVImporter

PACKAGE_DIR = Path(__file__).resolve().parent.parent
SAMPLE_CDR = PACKAGE_DIR / 'cdr.csv'
SAMPLE_CMR = PACKAGE_DIR / 'cmr.csv'


class CSVImporterTest(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.db = os.path.join(self.tmp, 'store.db')
        self.importer = CSVImporter(self.db)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _write(self, name: str, text: str, encoding: str = 'utf-8') -> str:
        path = os.path.join(self.tmp, name)
        with open(path, 'w', encoding=encoding, newline='') as f:
            f.write(text)
        return path

    def test_detects_record_type(self):
        cdr = self.importer.import_file(SAMPLE_CDR)
        cmr = self.importer.import_file(SAMPLE_CMR)
        self.assertEqual(cdr.record_type, 'cdr')
        self.assertEqual(cmr.record_type, 'cmr')
        self.assertTrue(cdr.ok and cmr.ok)
        self.assertEqual(cdr.rows_inserted, 3)
        self.assertEqual(cmr.rows_inserted, 5)

    def test_same_file_is_skipped(self):
        self.importer.import_file(SAMPLE_CDR)
        again = self.importer.import_file(SAMPLE_CDR)
        self.assertTrue(again.skipped)
        self.assertEqual(self.importer.stats()['cdr_records'], 3)

    def test_force_reimport_ignores_duplicates(self):
        self.importer.import_file(SAMPLE_CDR)
        again = self.importer.import_file(SAMPLE_CDR, force=True)
        self.assertEqual(again.rows_inserted, 0)
        self.assertEqual(again.rows_duplicate, 3)

    def test_type_row_semicolon_and_latin1(self):
        text = (
            'cdrRecordType;globalCallID_callId;dateTimeOrigination;callingPartyNumber;'
            'finalCalledPartyNumber;duration;pkid;origDeviceName\n'
            'INTEGER;INTEGER;INTEGER;VARCHAR(50);VARCHAR(50);INTEGER;UNIQUEIDENTIFIER;VARCHAR(129)\n'
            '1;100;1700000000;1001;2002;60;a-1;SEPMüller\n'
            '1;101;1700000100;1002;2003;0;a-2;SEPAAA\n'
        )
        path = self._write('cdr_latin1.csv', text, encoding='latin-1')
        result = self.importer.import_file(path)
        self.assertTrue(result.ok, result.error)
        self.assertEqual(result.rows_read, 2)

        df = self.importer.load_cdr()
        self.assertEqual(len(df), 2)
        self.assertIn('SEPMüller', df['origDeviceName'].tolist())
        self.assertEqual(df['duration'].sum(), 60)

    def test_new_columns_and_overlap_between_files(self):
        self._write('a.csv', 'globalCallID_callId,dateTimeOrigination,duration,pkid\n1,1700000000,10,p1\n')
        self._write('b.csv', 'globalCallID_callId,dateTimeOrigination,duration,pkid,huntPilotDN\n'
                             '1,1700000000,10,p1,\n2,1700000500,20,p2,5000\n')
        results = self.importer.import_path(self.tmp)
        self.assertEqual([r.rows_inserted for r in results], [1, 1])
        self.assertEqual(results[1].rows_duplicate, 1)
        df = self.importer.load_cdr()
        self.assertEqual(sorted(df['globalCallID_callId']), [1, 2])
        self.assertIn('huntPilotDN', df.columns)

    def test_unknown_header_is_rejected(self):
        path = self._write('other.csv', 'foo,bar\n1,2\n')
        result = self.importer.import_file(path)
        self.assertFalse(result.ok)

    def test_analyzer_store_matches_direct_csv(self):
        self.importer.import_path(SAMPLE_CDR)
        self.importer.import_path(SAMPLE_CMR)

        direct = CiscoCDRAnalyzer()
        direct.load_cdr(SAMPLE_CDR)
        direct.load_cmr(SAMPLE_CMR)
        direct.merge_data()

        stored = CiscoCDRAnalyzer()
        stored.load_from_store(self.db)
        stored.merge_data()

        self.assertEqual(direct.get_call_summary(), stored.get_call_summary())
        self.assertEqual(direct.get_quality_summary(), stored.get_quality_summary())


if __name__ == '__main__':
    unittest.main()
