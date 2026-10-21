from __future__ import annotations

import os
import sys
import threading
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from virtual_array.project import default_project
from virtual_array.server import cli, create_app
from virtual_array.server.jobs import JOB_RETENTION_SECONDS, JobManager, JobQueueFullError


def wait(manager: JobManager, job_id: str, timeout: float = 10.0) -> str:
    deadline = time.time() + timeout
    while time.time() < deadline:
        status = manager.get(job_id).status
        if status not in {"queued", "running"}:
            return status
        time.sleep(0.01)
    raise AssertionError(f"job {job_id} did not finish")


def writer(size: int):
    def body(directory: Path, progress) -> Path:  # noqa: ANN001
        target = directory / "out.bin"
        target.write_bytes(b"x" * size)
        return target

    return body


def test_finished_jobs_are_capped_by_count(tmp_path) -> None:
    manager = JobManager(tmp_path, max_workers=1, max_retained=3)
    ids = []
    for _ in range(6):
        job = manager.submit("t", writer(10))
        assert wait(manager, job.id) == "succeeded"
        ids.append(job.id)
        time.sleep(0.02)  # distinct directory mtimes
    remaining = sorted(path.name for path in tmp_path.iterdir())
    assert remaining == sorted(ids[-3:])
    manager.get(ids[-1])
    with pytest.raises(KeyError):
        manager.get(ids[0])
    manager.shutdown()


def test_finished_jobs_are_capped_by_size_but_newest_is_kept(tmp_path) -> None:
    manager = JobManager(tmp_path, max_workers=1, max_storage_bytes=250)
    ids = []
    for _ in range(4):
        job = manager.submit("t", writer(100))
        assert wait(manager, job.id) == "succeeded"
        ids.append(job.id)
        time.sleep(0.02)
    assert sorted(path.name for path in tmp_path.iterdir()) == sorted(ids[-2:])

    big = manager.submit("t", writer(1000))
    assert wait(manager, big.id) == "succeeded"
    assert [path.name for path in tmp_path.iterdir()] == [big.id]
    assert manager.get(big.id).download_path.is_file()
    manager.shutdown()


def test_orphaned_and_expired_directories_are_removed_at_startup(tmp_path) -> None:
    old = tmp_path / ("a" * 32)
    old.mkdir()
    (old / "report.pdf").write_bytes(b"pdf")
    expired = time.time() - JOB_RETENTION_SECONDS - 60
    os.utime(old, (expired, expired))
    for index in range(5):
        (tmp_path / f"{index:032x}").mkdir()
    manager = JobManager(tmp_path, max_retained=2)
    assert not old.exists()
    assert len(list(tmp_path.iterdir())) == 2
    manager.shutdown()


def test_pending_queue_is_bounded(tmp_path) -> None:
    release = threading.Event()

    def blocked(directory: Path, progress) -> Path:  # noqa: ANN001
        release.wait(10)
        return writer(1)(directory, progress)

    manager = JobManager(tmp_path, max_workers=1, max_pending=2)
    first = manager.submit("t", blocked)
    manager.submit("t", blocked)
    with pytest.raises(JobQueueFullError):
        manager.submit("t", blocked)
    assert len(list(tmp_path.iterdir())) == 2
    release.set()
    assert wait(manager, first.id) == "succeeded"
    manager.submit("t", writer(1))
    manager.shutdown()


def test_full_export_queue_returns_429(tmp_path) -> None:
    app = create_app(data_dir=tmp_path / "data", static_dir=tmp_path / "web")
    jobs = app.state.jobs
    jobs.max_pending = 0
    client = TestClient(app)
    project = default_project().model_dump(mode="json")
    response = client.post("/api/angle-error-image", json={"project": project, "error_limit_deg": 1.0, "language": "en"})
    assert response.status_code == 429
    assert response.headers["retry-after"] == "30"
    assert "busy" in response.json()["detail"]


def test_cli_reexecs_once_with_malloc_arena_limit(monkeypatch) -> None:
    calls = []
    monkeypatch.setattr(sys, "platform", "linux")
    monkeypatch.setattr(sys, "orig_argv", ["python3", "/venv/bin/mimo-array-server", "--port", "9000"], raising=False)
    monkeypatch.delenv(cli.MALLOC_ARENA_ENV, raising=False)
    monkeypatch.setattr(os, "execv", lambda path, args: calls.append((path, args)))
    cli.ensure_malloc_arena_limit()
    assert calls == [(sys.executable, [sys.executable, "/venv/bin/mimo-array-server", "--port", "9000"])]
    assert os.environ[cli.MALLOC_ARENA_ENV] == "2"

    cli.ensure_malloc_arena_limit()  # already set: no second exec
    assert len(calls) == 1


def test_cli_respects_existing_value_and_other_platforms(monkeypatch) -> None:
    monkeypatch.setattr(os, "execv", lambda *_: pytest.fail("unexpected exec"))
    monkeypatch.setattr(sys, "platform", "linux")
    monkeypatch.setenv(cli.MALLOC_ARENA_ENV, "8")
    cli.ensure_malloc_arena_limit()
    assert os.environ[cli.MALLOC_ARENA_ENV] == "8"

    monkeypatch.delenv(cli.MALLOC_ARENA_ENV)
    monkeypatch.setattr(sys, "platform", "win32")
    cli.ensure_malloc_arena_limit()
    assert cli.MALLOC_ARENA_ENV not in os.environ
