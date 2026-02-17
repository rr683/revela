"""
Storage module -- job metadata and file management.

Uses SQLite for job tracking (zero-config, swappable to Postgres later)
and local filesystem for uploaded files and reconstruction outputs.
"""

import json
import logging
import shutil
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    from ..engine.base import ReconstructionStatus  # as subpackage
except ImportError:
    # Direct import when backend/ is working directory.
    # Use importlib.util to load engine/base.py directly, bypassing
    # engine/__init__.py which has heavy GPU dependencies (torch).
    import importlib.util as _ilu
    _spec = _ilu.spec_from_file_location(
        "engine.base",
        str(Path(__file__).parent.parent / "engine" / "base.py"),
    )
    _mod = _ilu.module_from_spec(_spec)
    _spec.loader.exec_module(_mod)
    ReconstructionStatus = _mod.ReconstructionStatus

logger = logging.getLogger(__name__)

DB_SCHEMA = """
CREATE TABLE IF NOT EXISTS jobs (
    id TEXT PRIMARY KEY,
    status TEXT NOT NULL DEFAULT 'pending',
    method TEXT NOT NULL DEFAULT 'splatfacto',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    started_at TEXT,
    completed_at TEXT,
    error_message TEXT,
    input_video TEXT,
    input_image_dir TEXT,
    config_json TEXT,
    result_json TEXT,
    quality_json TEXT,
    num_frames INTEGER,
    duration_seconds REAL
);
"""


class JobStore:
    """
    Manages job metadata in SQLite.

    Thread-safe via sqlite3's built-in locking. For multi-process
    (Celery workers), uses WAL mode for concurrent reads.
    """

    def __init__(self, db_path: Path):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self):
        with self._conn() as conn:
            conn.executescript(DB_SCHEMA)
            conn.execute("PRAGMA journal_mode=WAL")

    @contextmanager
    def _conn(self):
        conn = sqlite3.connect(str(self.db_path), timeout=30)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def create_job(
        self,
        job_id: str,
        method: str = "splatfacto",
        input_video: Optional[str] = None,
        input_image_dir: Optional[str] = None,
        config: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        now = datetime.utcnow().isoformat()
        with self._conn() as conn:
            conn.execute(
                """INSERT INTO jobs
                   (id, status, method, created_at, updated_at,
                    input_video, input_image_dir, config_json)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    job_id,
                    ReconstructionStatus.PENDING.value,
                    method,
                    now,
                    now,
                    input_video,
                    input_image_dir,
                    json.dumps(config) if config else None,
                ),
            )
        return self.get_job(job_id)

    def get_job(self, job_id: str) -> Optional[Dict[str, Any]]:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT * FROM jobs WHERE id = ?", (job_id,)
            ).fetchone()
        if row is None:
            return None
        return self._row_to_dict(row)

    def list_jobs(
        self,
        status: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        with self._conn() as conn:
            if status:
                rows = conn.execute(
                    "SELECT * FROM jobs WHERE status = ? ORDER BY created_at DESC LIMIT ? OFFSET ?",
                    (status, limit, offset),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM jobs ORDER BY created_at DESC LIMIT ? OFFSET ?",
                    (limit, offset),
                ).fetchall()
        return [self._row_to_dict(r) for r in rows]

    def update_status(
        self,
        job_id: str,
        status: str,
        error_message: Optional[str] = None,
    ):
        now = datetime.utcnow().isoformat()
        with self._conn() as conn:
            if status == ReconstructionStatus.COMPLETED.value:
                conn.execute(
                    "UPDATE jobs SET status=?, updated_at=?, completed_at=? WHERE id=?",
                    (status, now, now, job_id),
                )
            elif status == ReconstructionStatus.FAILED.value:
                conn.execute(
                    "UPDATE jobs SET status=?, updated_at=?, completed_at=?, error_message=? WHERE id=?",
                    (status, now, now, error_message, job_id),
                )
            elif status in (
                ReconstructionStatus.PREPROCESSING.value,
                ReconstructionStatus.POSE_ESTIMATION.value,
                ReconstructionStatus.TRAINING.value,
            ):
                fields = "status=?, updated_at=?"
                params = [status, now]
                if not self._get_field(conn, job_id, "started_at"):
                    fields += ", started_at=?"
                    params.append(now)
                params.append(job_id)
                conn.execute(f"UPDATE jobs SET {fields} WHERE id=?", params)
            else:
                conn.execute(
                    "UPDATE jobs SET status=?, updated_at=? WHERE id=?",
                    (status, now, job_id),
                )

    def save_result(
        self,
        job_id: str,
        result: Dict[str, Any],
        quality: Optional[Dict[str, Any]] = None,
        num_frames: Optional[int] = None,
        duration_seconds: Optional[float] = None,
    ):
        now = datetime.utcnow().isoformat()
        with self._conn() as conn:
            conn.execute(
                """UPDATE jobs SET result_json=?, quality_json=?,
                   num_frames=?, duration_seconds=?, updated_at=?
                   WHERE id=?""",
                (
                    json.dumps(result),
                    json.dumps(quality) if quality else None,
                    num_frames,
                    duration_seconds,
                    now,
                    job_id,
                ),
            )

    def delete_job(self, job_id: str) -> bool:
        with self._conn() as conn:
            cursor = conn.execute("DELETE FROM jobs WHERE id = ?", (job_id,))
            return cursor.rowcount > 0

    def _get_field(self, conn, job_id: str, field: str):
        row = conn.execute(
            f"SELECT {field} FROM jobs WHERE id = ?", (job_id,)
        ).fetchone()
        return row[0] if row else None

    @staticmethod
    def _row_to_dict(row: sqlite3.Row) -> Dict[str, Any]:
        d = dict(row)
        for key in ("config_json", "result_json", "quality_json"):
            if d.get(key):
                d[key] = json.loads(d[key])
        return d


class FileStore:
    """
    Manages uploaded files and reconstruction outputs on local filesystem.

    Directory layout:
        uploads/<job_id>/        -- uploaded video/images
        cache/<job_id>/          -- intermediate processing files
        outputs/<job_id>/        -- final reconstruction outputs
    """

    def __init__(self, base_dir: Path):
        self.base_dir = Path(base_dir)
        self.uploads_dir = self.base_dir / "uploads"
        self.cache_dir = self.base_dir / "cache"
        self.outputs_dir = self.base_dir / "outputs"

        for d in (self.uploads_dir, self.cache_dir, self.outputs_dir):
            d.mkdir(parents=True, exist_ok=True)

    def get_upload_dir(self, job_id: str) -> Path:
        d = self.uploads_dir / job_id
        d.mkdir(parents=True, exist_ok=True)
        return d

    def get_cache_dir(self, job_id: str) -> Path:
        d = self.cache_dir / job_id
        d.mkdir(parents=True, exist_ok=True)
        return d

    def get_output_dir(self, job_id: str) -> Path:
        d = self.outputs_dir / job_id
        d.mkdir(parents=True, exist_ok=True)
        return d

    def save_upload(self, job_id: str, filename: str, content: bytes) -> Path:
        """Save an uploaded file and return the path."""
        upload_dir = self.get_upload_dir(job_id)
        dest = upload_dir / filename
        dest.write_bytes(content)
        logger.info(f"Saved upload: {dest} ({len(content)} bytes)")
        return dest

    def list_outputs(self, job_id: str) -> List[Dict[str, Any]]:
        """List output files for a job."""
        output_dir = self.get_output_dir(job_id)
        if not output_dir.exists():
            return []
        files = []
        for p in sorted(output_dir.rglob("*")):
            if p.is_file():
                files.append({
                    "name": p.name,
                    "path": str(p.relative_to(self.base_dir)),
                    "size_bytes": p.stat().st_size,
                    "suffix": p.suffix,
                })
        return files

    def get_output_path(self, job_id: str, filename: str) -> Optional[Path]:
        """Get full path for an output file, or None if not found."""
        output_dir = self.get_output_dir(job_id)
        for p in output_dir.rglob(filename):
            if p.is_file():
                return p
        return None

    def cleanup_job(self, job_id: str, keep_outputs: bool = True):
        """Remove intermediate files for a job."""
        cache = self.cache_dir / job_id
        if cache.exists():
            shutil.rmtree(cache)
            logger.info(f"Cleaned cache for job {job_id}")

        uploads = self.uploads_dir / job_id
        if uploads.exists():
            shutil.rmtree(uploads)
            logger.info(f"Cleaned uploads for job {job_id}")

        if not keep_outputs:
            outputs = self.outputs_dir / job_id
            if outputs.exists():
                shutil.rmtree(outputs)
                logger.info(f"Cleaned outputs for job {job_id}")

    def delete_job_files(self, job_id: str):
        """Remove all files for a job."""
        self.cleanup_job(job_id, keep_outputs=False)
