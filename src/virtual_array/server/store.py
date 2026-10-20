"""File-backed project library shared by everyone using one server."""

from __future__ import annotations

import json
import re
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ..project import Project

_PROJECT_ID_RE = re.compile(r"^[0-9a-f]{32}$")


class ProjectNotFoundError(KeyError):
    pass


class ProjectStore:
    def __init__(self, root: str | Path) -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()

    def list(self) -> list[dict[str, Any]]:
        entries = []
        for path in self.root.glob("*.json"):
            try:
                record = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            entries.append(_summary(record))
        entries.sort(key=lambda item: item["updated_at"], reverse=True)
        return entries

    def get(self, project_id: str) -> dict[str, Any]:
        path = self._path(project_id)
        if not path.is_file():
            raise ProjectNotFoundError(project_id)
        return json.loads(path.read_text(encoding="utf-8"))

    def create(self, project: Project) -> dict[str, Any]:
        project_id = uuid.uuid4().hex
        now = _now()
        record = {
            "id": project_id,
            "created_at": now,
            "updated_at": now,
            "project": project.model_dump(mode="json"),
        }
        self._write(project_id, record)
        return record

    def update(self, project_id: str, project: Project) -> dict[str, Any]:
        with self._lock:
            record = self.get(project_id)
            record["project"] = project.model_dump(mode="json")
            record["updated_at"] = _now()
            self._write(project_id, record, locked=True)
        return record

    def delete(self, project_id: str) -> None:
        path = self._path(project_id)
        if not path.is_file():
            raise ProjectNotFoundError(project_id)
        path.unlink()

    def _path(self, project_id: str) -> Path:
        if not _PROJECT_ID_RE.fullmatch(project_id or ""):
            raise ProjectNotFoundError(project_id)
        return self.root / f"{project_id}.json"

    def _write(self, project_id: str, record: dict[str, Any], locked: bool = False) -> None:
        path = self._path(project_id)
        temporary = path.with_suffix(".json.tmp")
        text = json.dumps(record, ensure_ascii=False, indent=2)
        if locked:
            temporary.write_text(text, encoding="utf-8")
            temporary.replace(path)
            return
        with self._lock:
            temporary.write_text(text, encoding="utf-8")
            temporary.replace(path)


def _summary(record: dict[str, Any]) -> dict[str, Any]:
    project = record.get("project", {})
    layout = project.get("layout", {})
    return {
        "id": record.get("id"),
        "name": project.get("name", ""),
        "created_at": record.get("created_at", ""),
        "updated_at": record.get("updated_at", ""),
        "tx_count": len(layout.get("tx", [])),
        "rx_count": len(layout.get("rx", [])),
        "frequency_ghz": project.get("frequency_ghz"),
    }


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")
