"""
Web interface for CSV import

Upload page, REST endpoints and report generation on top of CSVImporter.

Endpoints:
    GET  /                      Upload page with store statistics and import history
    POST /api/import            Multipart upload (field "files", repeatable)
                                Optional form fields: record_type (auto|cdr|cmr), force (true|false)
    GET  /api/stats             Store statistics and recent imports (JSON)
    POST /api/report            Generate HTML report from the store (form/JSON field: days)
    GET  /reports/<id>/<file>   Generated report files
"""

import logging
import os
import re
import shutil
import tempfile
import threading
from datetime import datetime
from typing import Optional

import matplotlib
matplotlib.use('Agg')  # No GUI backend in a web server

from flask import Flask, abort, jsonify, render_template, request, send_from_directory, url_for
from werkzeug.exceptions import RequestEntityTooLarge
from werkzeug.utils import secure_filename

from ..core.analyzer import CiscoCDRAnalyzer
from ..core.csv_importer import CSVImporter

logger = logging.getLogger(__name__)

DEFAULT_MAX_UPLOAD_MB = 200
REPORT_ID_PATTERN = re.compile(r'^\d{8}-\d{6}(-\d+)?$')


def _parse_bool(value) -> bool:
    return str(value).lower() in ('1', 'true', 'yes', 'on')


def create_app(
    db_path: str = os.path.join('data', 'cdr_store.db'),
    reports_dir: str = os.path.join('output', 'web_reports'),
    max_upload_mb: int = DEFAULT_MAX_UPLOAD_MB
) -> Flask:
    """
    Create the Flask application

    :param db_path: SQLite store used for imports and reports
    :param reports_dir: Directory where generated reports are written
    :param max_upload_mb: Maximum total upload size per request
    """
    app = Flask(__name__)
    app.config['MAX_CONTENT_LENGTH'] = max_upload_mb * 1024 * 1024
    app.config['DB_PATH'] = db_path
    app.config['REPORTS_DIR'] = os.path.abspath(reports_dir)

    importer = CSVImporter(db_path)
    report_lock = threading.Lock()

    def _history(limit: int = 20):
        history = importer.import_history(limit=limit)
        return history.to_dict(orient='records')

    # ==================== PAGES ====================

    @app.get('/')
    def index():
        return render_template(
            'index.html',
            stats=importer.stats(),
            history=_history(),
            max_upload_mb=max_upload_mb
        )

    # ==================== API ====================

    @app.post('/api/import')
    def api_import():
        files = [f for f in request.files.getlist('files') if f and f.filename]
        if not files:
            return jsonify({'error': 'No files uploaded (form field "files")'}), 400

        record_type = (request.form.get('record_type') or 'auto').lower()
        if record_type not in ('auto', 'cdr', 'cmr'):
            return jsonify({'error': 'record_type must be auto, cdr or cmr'}), 400
        force = _parse_bool(request.form.get('force', 'false'))

        results = []
        upload_dir = tempfile.mkdtemp(prefix='cdr_upload_')
        try:
            for i, upload in enumerate(files):
                # Keep the original name for the import log, but never use it as a path as-is
                name = secure_filename(upload.filename) or f'upload_{i}.csv'
                file_dir = os.path.join(upload_dir, str(i))
                os.makedirs(file_dir)
                path = os.path.join(file_dir, name)
                upload.save(path)

                result = importer.import_file(
                    path,
                    record_type=None if record_type == 'auto' else record_type,
                    force=force
                )
                results.append({
                    'file': upload.filename,
                    'record_type': result.record_type,
                    'rows_read': result.rows_read,
                    'rows_inserted': result.rows_inserted,
                    'rows_duplicate': result.rows_duplicate,
                    'skipped': result.skipped,
                    'ok': result.ok,
                    'error': result.error,
                    'warnings': result.warnings,
                })
        finally:
            shutil.rmtree(upload_dir, ignore_errors=True)

        status = 200 if all(r['ok'] for r in results) else 207
        return jsonify({'results': results, 'stats': importer.stats()}), status

    @app.get('/api/stats')
    def api_stats():
        limit = min(request.args.get('limit', 20, type=int), 500)
        return jsonify({'stats': importer.stats(), 'history': _history(limit)})

    @app.post('/api/report')
    def api_report():
        payload = request.get_json(silent=True) or request.form
        days_raw = payload.get('days')
        days: Optional[int] = None
        if days_raw not in (None, '', 'all'):
            try:
                days = int(days_raw)
                if days <= 0:
                    raise ValueError
            except (TypeError, ValueError):
                return jsonify({'error': 'days must be a positive integer'}), 400

        if not report_lock.acquire(blocking=False):
            return jsonify({'error': 'A report is already being generated, try again shortly'}), 409
        try:
            analyzer = CiscoCDRAnalyzer()
            try:
                analyzer.load_from_store(db_path, days=days)
            except ValueError as e:
                return jsonify({'error': str(e)}), 404
            analyzer.merge_data()

            from ..visualization.reports import ReportGenerator

            report_id = datetime.now().strftime('%Y%m%d-%H%M%S')
            out_dir = os.path.join(app.config['REPORTS_DIR'], report_id)
            suffix = 1
            while os.path.exists(out_dir):
                suffix += 1
                out_dir = os.path.join(app.config['REPORTS_DIR'], f'{report_id}-{suffix}')
            report_id = os.path.basename(out_dir)

            period = f'last {days} days' if days else 'all data'
            report_path = ReportGenerator(analyzer).generate_report(
                output_dir=out_dir,
                title=f'CDR Analysis Report ({period})',
                include_charts=True,
                include_quality=analyzer.cmr_df is not None,
                include_security=True,
                format='html'
            )
            return jsonify({
                'report_url': url_for('report_file', report_id=report_id,
                                      filename=os.path.basename(report_path)),
                'records': len(analyzer.cdr_df),
            })
        except Exception as e:
            logger.exception('Report generation failed')
            return jsonify({'error': f'Report generation failed: {e}'}), 500
        finally:
            report_lock.release()

    @app.get('/reports/<report_id>/<path:filename>')
    def report_file(report_id: str, filename: str):
        if not REPORT_ID_PATTERN.match(report_id):
            abort(404)
        return send_from_directory(os.path.join(app.config['REPORTS_DIR'], report_id), filename)

    @app.errorhandler(RequestEntityTooLarge)
    def too_large(_):
        return jsonify({'error': f'Upload exceeds {max_upload_mb} MB'}), 413

    return app


def run_server(
    host: str = '127.0.0.1',
    port: int = 8080,
    db_path: str = os.path.join('data', 'cdr_store.db'),
    reports_dir: str = os.path.join('output', 'web_reports'),
    max_upload_mb: int = DEFAULT_MAX_UPLOAD_MB
):
    """Start the web interface (Flask built-in server, threaded)"""
    app = create_app(db_path=db_path, reports_dir=reports_dir, max_upload_mb=max_upload_mb)
    print(f"🌐 CDR import page: http://{'localhost' if host in ('127.0.0.1', '0.0.0.0') else host}:{port}")
    print(f"   Store: {db_path}")
    app.run(host=host, port=port, threaded=True)
