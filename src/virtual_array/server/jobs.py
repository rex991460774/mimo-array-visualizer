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
_JOB_ID_RE = re.compile(r"^[0-9a-f]{32}$")


class JobCancelledError(Exception):
    pass


class JobNotFoundError(KeyError):
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
    def __init__(self, root: str | Path, max_workers: int = 2) -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self._jobs: dict[str, Job] = {}
        self._lock = threading.Lock()
        self._executor = ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="export")
        self.cleanup()

    def submit(self, kind: str, body: JobBody) -> Job:
        job_id = uuid.uuid4().hex
        job = Job(id=job_id, kind=kind, directory=self.root / job_id)
        job.directory.mkdir(parents=True, exist_ok=True)
        with self._lock:
            self._jobs[job_id] = job
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
        cutoff = time.time() - JOB_RETENTION_SECONDS
        with self._lock:
            for job_id in [key for key, job in self._jobs.items() if job.created_at < cutoff]:
                self._jobs.pop(job_id, None)
        for directory in self.root.iterdir():
            if directory.is_dir() and directory.stat().st_mtime < cutoff:
                shutil.rmtree(directory, ignore_errors=True)

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
            return
        job.download_path = result
        job.download_name = result.name
        job.progress = 100
        job.status = "succeeded"
        self.cleanup()


def zip_directory(files: list[Path], base: Path, target: Path) -> Path:
    with zipfile.ZipFile(target, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in files:
            archive.write(path, arcname=str(path.relative_to(base)))
    return target
