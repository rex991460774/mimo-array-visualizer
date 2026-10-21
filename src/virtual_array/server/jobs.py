"""Background jobs for long-running exports (PDF reports, angle-error images)."""

from __future__ import annotations

import logging
import re
import shutil
import threading
import time
import uuid
import zipfile
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

LOGGER = logging.getLogger(__name__)
JOB_RETENTION_SECONDS = 24 * 3600
# Finished exports kept for download, newest first; older ones are deleted even
# before the retention period ends so a busy server cannot fill its disk.
MAX_RETAINED_JOBS = 100
MAX_JOB_STORAGE_BYTES = 1 << 30
# Queued + running exports; further requests get 429 instead of piling up.
MAX_PENDING_JOBS = 8
_ACTIVE_STATUSES = frozenset({"queued", "running"})
_JOB_ID_RE = re.compile(r"^[0-9a-f]{32}$")


class JobCancelledError(Exception):
    pass


class JobNotFoundError(KeyError):
    pass


class JobQueueFullError(RuntimeError):
    pass


@dataclass
class Job:
    id: str
    kind: str
    directory: Path
    status: str = "queued"  # queued | running | succeeded | failed | cancelled
    progress: int = 0
    message: str = ""
    error: str | None = None
    download_name: str | None = None
    download_path: Path | None = None
    created_at: float = field(default_factory=time.time)
    cancel_requested: bool = False

    def payload(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "kind": self.kind,
            "status": self.status,
            "progress": self.progress,
            "message": self.message,
            "error": self.error,
            "download_name": self.download_name,
        }


# A job body receives (output directory, progress callback) and returns the
# file to offer for download.
JobBody = Callable[[Path, Callable[[int, str], None]], Path]


class JobManager:
    def __init__(
        self,
        root: str | Path,
        max_workers: int = 2,
        max_pending: int = MAX_PENDING_JOBS,
        max_retained: int = MAX_RETAINED_JOBS,
        max_storage_bytes: int = MAX_JOB_STORAGE_BYTES,
    ) -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.max_pending = max_pending
        self.max_retained = max_retained
        self.max_storage_bytes = max_storage_bytes
        self._jobs: dict[str, Job] = {}
        self._lock = threading.Lock()
        self._executor = ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="export")
        self.cleanup()

    def submit(self, kind: str, body: JobBody) -> Job:
        job_id = uuid.uuid4().hex
        job = Job(id=job_id, kind=kind, directory=self.root / job_id)
        with self._lock:
            pending = sum(1 for other in self._jobs.values() if other.status in _ACTIVE_STATUSES)
            if pending >= self.max_pending:
                raise JobQueueFullError(f"{pending} exports are already queued or running.")
            self._jobs[job_id] = job
        try:
            job.directory.mkdir(parents=True, exist_ok=True)
        except OSError:
            with self._lock:
                self._jobs.pop(job_id, None)
            raise
        self._executor.submit(self._run, job, body)
        return job

    def get(self, job_id: str) -> Job:
        if not _JOB_ID_RE.fullmatch(job_id or ""):
            raise JobNotFoundError(job_id)
        with self._lock:
            job = self._jobs.get(job_id)
        if job is None:
            raise JobNotFoundError(job_id)
        return job

    def cancel(self, job_id: str) -> Job:
        job = self.get(job_id)
        if job.status in {"queued", "running"}:
            job.cancel_requested = True
        return job

    def cleanup(self) -> None:
        """Delete finished exports past the retention time, count or size budget.

        Directories left by earlier server runs count as finished.  The newest
        finished export is always kept so it can still be downloaded.
        """
        cutoff = time.time() - JOB_RETENTION_SECONDS
        with self._lock:
            active = {job_id for job_id, job in self._jobs.items() if job.status in _ACTIVE_STATUSES}
        finished: list[tuple[float, int, Path]] = []
        for directory in self.root.iterdir():
            if not directory.is_dir() or directory.name in active:
                continue
            try:
                finished.append((directory.stat().st_mtime, _tree_size(directory), directory))
            except OSError:
                continue
        finished.sort(key=lambda entry: entry[0], reverse=True)
        kept = 0
        total = 0
        removed: set[str] = set()
        for mtime, size, directory in finished:
            within_budget = kept < self.max_retained and (kept == 0 or total + size <= self.max_storage_bytes)
            if mtime >= cutoff and within_budget:
                kept += 1
                total += size
                continue
            shutil.rmtree(directory, ignore_errors=True)
            removed.add(directory.name)
        with self._lock:
            for job_id, job in list(self._jobs.items()):
                if job.status in _ACTIVE_STATUSES:
                    continue
                if job_id in removed or job.created_at < cutoff:
                    self._jobs.pop(job_id, None)

    def shutdown(self) -> None:
        self._executor.shutdown(wait=False, cancel_futures=True)

    def _run(self, job: Job, body: JobBody) -> None:
        if job.cancel_requested:
            job.status = "cancelled"
            return
        job.status = "running"

        def progress(percent: int, message: str) -> None:
            if job.cancel_requested:
                raise JobCancelledError()
            job.progress = max(job.progress, min(100, int(percent)))
            job.message = message

        try:
            result = body(job.directory, progress)
        except JobCancelledError:
            job.status = "cancelled"
            shutil.rmtree(job.directory, ignore_errors=True)
            return
        except Exception as exc:  # noqa: BLE001 - reported to the client
            LOGGER.exception("Export job %s failed", job.id)
            job.status = "failed"
            job.error = str(exc) or exc.__class__.__name__
            self.cleanup()
            return
        job.download_path = result
        job.download_name = result.name
        job.progress = 100
        job.status = "succeeded"
        self.cleanup()


def _tree_size(directory: Path) -> int:
    return sum(path.stat().st_size for path in directory.rglob("*") if path.is_file())


def zip_directory(files: list[Path], base: Path, target: Path) -> Path:
    with zipfile.ZipFile(target, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in files:
            archive.write(path, arcname=str(path.relative_to(base)))
    return target
