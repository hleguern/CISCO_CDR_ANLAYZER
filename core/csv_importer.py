"""
CSV import module for Cisco CDR/CMR files

Imports CUCM CDR and CMR CSV exports into a local SQLite store so data
accumulates across imports and can be analyzed without re-reading every file.

Features:
    - Auto-detection of record type (CDR vs CMR) from the header
    - Skips the CUCM data type row (INTEGER,VARCHAR,...) when present
    - Separator and encoding detection (utf-8, utf-8-sig, cp1252, latin-1)
    - Deduplication on pkid (or a row hash when pkid is missing)
    - Import log: files already imported (same content hash) are skipped
"""

import csv
import glob
import hashlib
import io
import logging
import os
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, List, Optional, Union

import pandas as pd

logger = logging.getLogger(__name__)


ENCODINGS = ['utf-8', 'utf-8-sig', 'cp1252', 'latin-1']

# Header columns that identify each record type
CDR_MARKERS = {'dateTimeOrigination', 'finalCalledPartyNumber', 'duration'}
CMR_MARKERS = {'origvarVQMetrics', 'orignumberPacketsSent', 'origjitter', 'varVQMetrics', 'numberPacketsSent'}

# Values found in the optional second row of CUCM exports
TYPE_ROW_VALUES = {'INTEGER', 'VARCHAR', 'UNIQUEIDENTIFIER', 'TEXT', 'BIGINT', 'SMALLINT', 'CHAR', 'BOOLEAN'}

TABLES = {'cdr': 'cdr_records', 'cmr': 'cmr_records'}


@dataclass
class ImportResult:
    """Result of importing a single file"""
    file: str
    record_type: Optional[str] = None
    rows_read: int = 0
    rows_inserted: int = 0
    rows_duplicate: int = 0
    skipped: bool = False
    error: Optional[str] = None
    warnings: List[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return self.error is None

    def __str__(self) -> str:
        name = os.path.basename(self.file)
        if self.error:
            return f"{name}: ERROR - {self.error}"
        if self.skipped:
            return f"{name}: skipped (already imported)"
        return (f"{name}: {self.record_type.upper()} - {self.rows_read} read, "
                f"{self.rows_inserted} new, {self.rows_duplicate} duplicates")


class CSVImporter:
    """Import CDR/CMR CSV files into a SQLite store"""

    def __init__(self, db_path: Union[str, Path] = 'data/cdr_store.db'):
        self.db_path = str(db_path)
        db_dir = os.path.dirname(self.db_path)
        if db_dir:
            os.makedirs(db_dir, exist_ok=True)
        self._init_db()

    # ==================== DATABASE ====================

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.db_path)

    def _init_db(self):
        with self._connect() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS import_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    file_name TEXT NOT NULL,
                    file_hash TEXT NOT NULL,
                    record_type TEXT NOT NULL,
                    rows_read INTEGER,
                    rows_inserted INTEGER,
                    rows_duplicate INTEGER,
                    imported_at TEXT NOT NULL
                )
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_import_hash ON import_log(file_hash)")
            for table in TABLES.values():
                conn.execute(f"""
                    CREATE TABLE IF NOT EXISTS {table} (
                        record_key TEXT PRIMARY KEY,
                        import_id INTEGER
                    )
                """)

    def _table_columns(self, conn: sqlite3.Connection, table: str) -> List[str]:
        return [row[1] for row in conn.execute(f'PRAGMA table_info("{table}")')]

    def _ensure_columns(self, conn: sqlite3.Connection, table: str, columns: List[str]):
        """Add any new CSV columns to the table (exports differ between CUCM versions)"""
        existing = set(self._table_columns(conn, table))
        for col in columns:
            if col not in existing:
                conn.execute(f'ALTER TABLE "{table}" ADD COLUMN "{col}" TEXT')
        if 'globalCallID_callId' in existing.union(columns):
            conn.execute(
                f'CREATE INDEX IF NOT EXISTS idx_{table}_callid ON "{table}"(globalCallID_callId)'
            )

    # ==================== FILE PARSING ====================

    @staticmethod
    def _file_hash(filepath: str) -> str:
        h = hashlib.sha256()
        with open(filepath, 'rb') as f:
            for chunk in iter(lambda: f.read(1 << 20), b''):
                h.update(chunk)
        return h.hexdigest()

    @staticmethod
    def _decode(filepath: str) -> str:
        with open(filepath, 'rb') as f:
            raw = f.read()
        for enc in ENCODINGS:
            try:
                return raw.decode(enc)
            except UnicodeDecodeError:
                continue
        raise ValueError("Unable to decode file with supported encodings")

    @staticmethod
    def _detect_separator(text: str) -> str:
        first_line = text.split('\n', 1)[0]
        try:
            return csv.Sniffer().sniff(first_line, delimiters=',;\t|').delimiter
        except csv.Error:
            return ','

    @staticmethod
    def detect_record_type(columns: List[str]) -> Optional[str]:
        """Return 'cdr', 'cmr' or None based on header columns"""
        cols = set(columns)
        if cols & CMR_MARKERS:
            return 'cmr'
        if cols & CDR_MARKERS:
            return 'cdr'
        return None

    def parse_file(self, filepath: str) -> pd.DataFrame:
        """Read a CDR/CMR CSV into a DataFrame of strings"""
        text = self._decode(filepath).lstrip('﻿')
        sep = self._detect_separator(text)
        df = pd.read_csv(io.StringIO(text), sep=sep, dtype=str, keep_default_na=False,
                         skipinitialspace=True)
        df.columns = [c.strip().strip('"') for c in df.columns]

        # Drop CUCM type row (second line of some exports)
        if len(df) and set(v.strip().upper().split('(')[0] for v in df.iloc[0] if v.strip()) <= TYPE_ROW_VALUES:
            df = df.iloc[1:].reset_index(drop=True)

        # Drop fully empty rows
        df = df[(df != '').any(axis=1)].reset_index(drop=True)
        return df

    @staticmethod
    def _record_keys(df: pd.DataFrame) -> pd.Series:
        """pkid when available, otherwise a hash of the full row"""
        row_hash = pd.util.hash_pandas_object(df, index=False).astype(str)
        if 'pkid' in df.columns:
            pkid = df['pkid'].str.strip()
            return pkid.where(pkid != '', 'h:' + row_hash)
        return 'h:' + row_hash

    # ==================== IMPORT ====================

    def import_file(
        self,
        filepath: Union[str, Path],
        record_type: Optional[str] = None,
        force: bool = False
    ) -> ImportResult:
        """
        Import a single CSV file

        :param filepath: Path to the CSV file
        :param record_type: 'cdr' or 'cmr'; auto-detected when None
        :param force: Re-import even if this exact file was imported before
        :return: ImportResult
        """
        filepath = str(filepath)
        result = ImportResult(file=filepath)

        try:
            if not os.path.isfile(filepath):
                raise FileNotFoundError(f"File not found: {filepath}")

            file_hash = self._file_hash(filepath)
            with self._connect() as conn:
                if not force and conn.execute(
                    "SELECT 1 FROM import_log WHERE file_hash = ?", (file_hash,)
                ).fetchone():
                    result.skipped = True
                    return result

            df = self.parse_file(filepath)
            detected = self.detect_record_type(list(df.columns))
            record_type = (record_type or detected or '').lower()
            if record_type not in TABLES:
                raise ValueError("Cannot determine record type (CDR/CMR) from header")
            if detected and detected != record_type:
                result.warnings.append(f"Header looks like {detected.upper()}, importing as {record_type.upper()}")

            result.record_type = record_type
            result.rows_read = len(df)
            if df.empty:
                result.warnings.append("File contains no records")

            table = TABLES[record_type]
            columns = [c for c in df.columns if c and c not in ('record_key', 'import_id')]
            df = df[columns]
            keys = self._record_keys(df)

            with self._connect() as conn:
                self._ensure_columns(conn, table, columns)
                cur = conn.execute(
                    "INSERT INTO import_log (file_name, file_hash, record_type, rows_read, "
                    "rows_inserted, rows_duplicate, imported_at) VALUES (?, ?, ?, ?, 0, 0, ?)",
                    (os.path.basename(filepath), file_hash, record_type, len(df),
                     datetime.now().isoformat(timespec='seconds'))
                )
                import_id = cur.lastrowid

                col_sql = ', '.join(f'"{c}"' for c in ['record_key', 'import_id'] + columns)
                placeholders = ', '.join(['?'] * (len(columns) + 2))
                rows = [
                    (key, import_id, *values)
                    for key, values in zip(keys, df.itertuples(index=False, name=None))
                ]
                before = conn.total_changes
                conn.executemany(
                    f'INSERT OR IGNORE INTO "{table}" ({col_sql}) VALUES ({placeholders})', rows
                )
                result.rows_inserted = conn.total_changes - before
                result.rows_duplicate = len(rows) - result.rows_inserted

                conn.execute(
                    "UPDATE import_log SET rows_inserted = ?, rows_duplicate = ? WHERE id = ?",
                    (result.rows_inserted, result.rows_duplicate, import_id)
                )

            logger.info(str(result))

        except Exception as e:
            result.error = str(e)
            logger.error(f"Import failed for {filepath}: {e}")

        return result

    def import_path(
        self,
        path: Union[str, Path],
        record_type: Optional[str] = None,
        force: bool = False
    ) -> List[ImportResult]:
        """
        Import a file, a directory (all *.csv / *.txt) or a glob pattern

        :return: List of ImportResult, one per file
        """
        path = str(path)
        if '*' in path or '?' in path:
            files = sorted(glob.glob(path))
        elif os.path.isdir(path):
            files = sorted(
                f for ext in ('*.csv', '*.txt', 'cdr_*', 'cmr_*')
                for f in glob.glob(os.path.join(path, ext))
            )
            files = sorted(set(files))
        else:
            files = [path]

        if not files:
            return [ImportResult(file=path, error="No files found")]

        return [self.import_file(f, record_type=record_type, force=force) for f in files]

    # ==================== READ BACK ====================

    @staticmethod
    def _restore_types(df: pd.DataFrame) -> pd.DataFrame:
        """Convert columns to numeric where every non-empty value is numeric (matches CSV loading)"""
        df = df.replace('', pd.NA)
        for col in df.columns:
            series = df[col].dropna()
            if series.empty:
                df[col] = pd.to_numeric(df[col], errors='coerce')
                continue
            converted = pd.to_numeric(series, errors='coerce')
            if converted.notna().all():
                df[col] = pd.to_numeric(df[col], errors='coerce')
        return df

    def _read_table(self, record_type: str, where: str = '', params: tuple = ()) -> pd.DataFrame:
        table = TABLES[record_type]
        with self._connect() as conn:
            columns = [c for c in self._table_columns(conn, table) if c not in ('record_key', 'import_id')]
            if not columns:
                return pd.DataFrame()
            col_sql = ', '.join(f'"{c}"' for c in columns)
            df = pd.read_sql_query(f'SELECT {col_sql} FROM "{table}" {where}', conn, params=params)
        return self._restore_types(df)

    def load_cdr(
        self,
        days: Optional[int] = None,
        start: Optional[datetime] = None,
        end: Optional[datetime] = None
    ) -> pd.DataFrame:
        """
        Read CDR records from the store

        :param days: Only records from the last N days
        :param start: Only records originated at/after this time
        :param end: Only records originated before this time
        """
        if days is not None:
            start = datetime.now() - timedelta(days=days)
        clauses, params = [], []
        if start is not None:
            clauses.append('CAST("dateTimeOrigination" AS INTEGER) >= ?')
            params.append(int(start.timestamp()))
        if end is not None:
            clauses.append('CAST("dateTimeOrigination" AS INTEGER) < ?')
            params.append(int(end.timestamp()))
        if clauses:
            with self._connect() as conn:
                if 'dateTimeOrigination' not in self._table_columns(conn, TABLES['cdr']):
                    return pd.DataFrame()
        where = ('WHERE ' + ' AND '.join(clauses)) if clauses else ''
        return self._read_table('cdr', where, tuple(params))

    def load_cmr(self, cdr_df: Optional[pd.DataFrame] = None) -> pd.DataFrame:
        """
        Read CMR records from the store

        :param cdr_df: When given, only CMRs whose callId matches these CDRs are returned
        """
        df = self._read_table('cmr')
        if cdr_df is not None and not df.empty and 'globalCallID_callId' in df.columns \
                and 'globalCallID_callId' in cdr_df.columns:
            df = df[df['globalCallID_callId'].isin(cdr_df['globalCallID_callId'])]
        return df.reset_index(drop=True)

    def stats(self) -> Dict[str, object]:
        """Record counts, imports and date range of the store"""
        with self._connect() as conn:
            info: Dict[str, object] = {'db_path': self.db_path}
            for rtype, table in TABLES.items():
                info[f'{rtype}_records'] = conn.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0]
            info['imports'] = conn.execute('SELECT COUNT(*) FROM import_log').fetchone()[0]
            if 'dateTimeOrigination' in self._table_columns(conn, TABLES['cdr']):
                lo, hi = conn.execute(
                    'SELECT MIN(CAST("dateTimeOrigination" AS INTEGER)), '
                    'MAX(CAST("dateTimeOrigination" AS INTEGER)) FROM cdr_records '
                    'WHERE "dateTimeOrigination" != \'\''
                ).fetchone()
                info['first_call'] = datetime.fromtimestamp(lo, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%S") if lo else None
                info['last_call'] = datetime.fromtimestamp(hi, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%S") if hi else None
        return info

    def import_history(self, limit: int = 50) -> pd.DataFrame:
        with self._connect() as conn:
            return pd.read_sql_query(
                'SELECT * FROM import_log ORDER BY id DESC LIMIT ?', conn, params=(limit,)
            )
