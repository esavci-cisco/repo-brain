"""SQLite metadata database for tracking indexed files."""

from __future__ import annotations

import hashlib
import logging
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

from repo_brain.config import RepoConfig

logger = logging.getLogger(__name__)


class MetadataDB:
    """SQLite database for file metadata and index tracking."""

    def __init__(self, config: RepoConfig) -> None:
        self.config = config
        config.data_dir.mkdir(parents=True, exist_ok=True)
        self._db_path = config.metadata_db_path
        self._conn = sqlite3.connect(str(self._db_path))
        self._conn.row_factory = sqlite3.Row
        self._init_schema()

    def _init_schema(self) -> None:
        """Create tables if they don't exist."""
        self._conn.executescript("""
            CREATE TABLE IF NOT EXISTS indexed_files (
                file_path TEXT PRIMARY KEY,
                content_hash TEXT NOT NULL,
                language TEXT NOT NULL,
                service TEXT DEFAULT '',
                chunk_count INTEGER DEFAULT 0,
                line_count INTEGER DEFAULT 0,
                last_indexed TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS index_runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                started_at TEXT NOT NULL,
                completed_at TEXT,
                files_scanned INTEGER DEFAULT 0,
                files_indexed INTEGER DEFAULT 0,
                files_skipped INTEGER DEFAULT 0,
                chunks_created INTEGER DEFAULT 0,
                status TEXT DEFAULT 'running'
            );

            CREATE TABLE IF NOT EXISTS incidents (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                cause TEXT DEFAULT '',
                resolution TEXT DEFAULT '',
                modules TEXT DEFAULT '',
                lessons TEXT DEFAULT '',
                created_at TEXT NOT NULL,
                tags TEXT DEFAULT ''
            );
        """)
        self._conn.commit()

    def get_file_hash(self, file_path: str) -> str | None:
        """Get the stored content hash for a file."""
        row = self._conn.execute(
            "SELECT content_hash FROM indexed_files WHERE file_path = ?",
            (file_path,),
        ).fetchone()
        return row["content_hash"] if row else None

    def update_file(
        self,
        file_path: str,
        content_hash: str,
        language: str,
        service: str,
        chunk_count: int,
        line_count: int,
    ) -> None:
        """Insert or update a file's index record."""
        now = datetime.now(UTC).isoformat()
        self._conn.execute(
            """
            INSERT INTO indexed_files
                (file_path, content_hash, language, service,
                 chunk_count, line_count, last_indexed)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(file_path) DO UPDATE SET
                content_hash = excluded.content_hash,
                language = excluded.language,
                service = excluded.service,
                chunk_count = excluded.chunk_count,
                line_count = excluded.line_count,
                last_indexed = excluded.last_indexed
            """,
            (file_path, content_hash, language, service, chunk_count, line_count, now),
        )
        self._conn.commit()

    def remove_file(self, file_path: str) -> None:
        """Remove a file from the index."""
        self._conn.execute("DELETE FROM indexed_files WHERE file_path = ?", (file_path,))
        self._conn.commit()

    def get_all_indexed_files(self) -> dict[str, str]:
        """Get all indexed files as {file_path: content_hash}."""
        rows = self._conn.execute("SELECT file_path, content_hash FROM indexed_files").fetchall()
        return {row["file_path"]: row["content_hash"] for row in rows}

    def start_index_run(self) -> int:
        """Record the start of an index run. Returns the run ID."""
        now = datetime.now(UTC).isoformat()
        cursor = self._conn.execute(
            "INSERT INTO index_runs (started_at, status) VALUES (?, 'running')",
            (now,),
        )
        self._conn.commit()
        return cursor.lastrowid  # type: ignore[return-value]

    def complete_index_run(
        self,
        run_id: int,
        files_scanned: int,
        files_indexed: int,
        files_skipped: int,
        chunks_created: int,
    ) -> None:
        """Record the completion of an index run."""
        now = datetime.now(UTC).isoformat()
        self._conn.execute(
            """
            UPDATE index_runs SET
                completed_at = ?,
                files_scanned = ?,
                files_indexed = ?,
                files_skipped = ?,
                chunks_created = ?,
                status = 'completed'
            WHERE id = ?
            """,
            (now, files_scanned, files_indexed, files_skipped, chunks_created, run_id),
        )
        self._conn.commit()

    def get_last_run(self) -> dict | None:
        """Get the most recent index run."""
        row = self._conn.execute("SELECT * FROM index_runs ORDER BY id DESC LIMIT 1").fetchone()
        return dict(row) if row else None

    def get_stats(self) -> dict:
        """Get index statistics."""
        file_count = self._conn.execute("SELECT COUNT(*) as c FROM indexed_files").fetchone()["c"]
        chunk_sum = self._conn.execute(
            "SELECT COALESCE(SUM(chunk_count), 0) as c FROM indexed_files"
        ).fetchone()["c"]
        last_run = self.get_last_run()

        # Service breakdown
        services = self._conn.execute(
            "SELECT service, COUNT(*) as c FROM indexed_files "
            "WHERE service != '' GROUP BY service ORDER BY c DESC"
        ).fetchall()

        # Language breakdown
        languages = self._conn.execute(
            "SELECT language, COUNT(*) as c FROM indexed_files GROUP BY language ORDER BY c DESC"
        ).fetchall()

        return {
            "total_files": file_count,
            "total_chunks": chunk_sum,
            "last_run": dict(last_run) if last_run else None,
            "services": {row["service"]: row["c"] for row in services},
            "languages": {row["language"]: row["c"] for row in languages},
        }

    def close(self) -> None:
        """Close the database connection."""
        self._conn.close()


def compute_file_hash(file_path: Path) -> str:
    """Compute SHA-256 hash of a file's contents."""
    content = file_path.read_bytes()
    return hashlib.sha256(content).hexdigest()[:16]
