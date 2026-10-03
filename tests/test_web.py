"""
Tests for the web upload interface

Run from the folder containing cisco_cdr_analyzer:
    python -m unittest discover -s cisco_cdr_analyzer/tests -t .
"""

import io
import os
import shutil
import tempfile
import unittest
from pathlib import Path

from cisco_cdr_analyzer.web import create_app

PACKAGE_DIR = Path(__file__).resolve().parent.parent
SAMPLE_CDR = PACKAGE_DIR / 'cdr.csv'
SAMPLE_CMR = PACKAGE_DIR / 'cmr.csv'


class WebAppTest(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.app = create_app(
            db_path=os.path.join(self.tmp, 'store.db'),
            reports_dir=os.path.join(self.tmp, 'reports'),
            max_upload_mb=1
        )
        self.client = self.app.test_client()

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _upload(self, *paths, **form):
        data = dict(form)
        data['files'] = [(open(p, 'rb'), os.path.basename(p)) for p in paths]
        try:
            return self.client.post('/api/import', data=data, content_type='multipart/form-data')
        finally:
            for f, _ in data['files']:
                f.close()

    def test_index_page(self):
        res = self.client.get('/')
        self.assertEqual(res.status_code, 200)
        self.assertIn(b'CDR / CMR Import', res.data)

    def test_upload_cdr_and_cmr(self):
        res = self._upload(SAMPLE_CDR, SAMPLE_CMR)
        self.assertEqual(res.status_code, 200)
        body = res.get_json()
        self.assertEqual([r['record_type'] for r in body['results']], ['cdr', 'cmr'])
        self.assertEqual(body['stats']['cdr_records'], 3)
        self.assertEqual(body['stats']['cmr_records'], 5)

        history = self.client.get('/api/stats').get_json()['history']
        self.assertEqual({h['file_name'] for h in history}, {'cdr.csv', 'cmr.csv'})

    def test_reupload_is_skipped_unless_forced(self):
        self._upload(SAMPLE_CDR)
        skipped = self._upload(SAMPLE_CDR).get_json()['results'][0]
        self.assertTrue(skipped['skipped'])
        forced = self._upload(SAMPLE_CDR, force='true').get_json()['results'][0]
        self.assertEqual(forced['rows_duplicate'], 3)

    def test_invalid_file_returns_partial_status(self):
        res = self.client.post('/api/import', data={
            'files': [(io.BytesIO(b'foo,bar\n1,2\n'), 'bad.csv')]
        }, content_type='multipart/form-data')
        self.assertEqual(res.status_code, 207)
        self.assertFalse(res.get_json()['results'][0]['ok'])

    def test_missing_files_and_too_large(self):
        self.assertEqual(self.client.post('/api/import', data={}).status_code, 400)
        res = self.client.post('/api/import', data={
            'files': [(io.BytesIO(b'x' * (2 * 1024 * 1024)), 'big.csv')]
        }, content_type='multipart/form-data')
        self.assertEqual(res.status_code, 413)

    def test_report_from_store(self):
        self.assertEqual(self.client.post('/api/report', json={}).status_code, 404)
        self._upload(SAMPLE_CDR, SAMPLE_CMR)
        res = self.client.post('/api/report', json={'days': ''})
        self.assertEqual(res.status_code, 200, res.get_json())
        report = self.client.get(res.get_json()['report_url'])
        self.assertEqual(report.status_code, 200)
        report.close()
        self.assertEqual(self.client.post('/api/report', json={'days': 'abc'}).status_code, 400)

    def test_report_path_traversal_rejected(self):
        self.assertEqual(self.client.get('/reports/..%2F..%2Fstore.db/x').status_code, 404)


if __name__ == '__main__':
    unittest.main()
