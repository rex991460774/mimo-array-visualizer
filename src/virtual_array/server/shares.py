"""Immutable configuration snapshots behind short share links (``/s/<id>``).

A share is a frozen copy of a project: later edits by the sender do not change
what the link opens, and the recipient works on their own copy.  The ID is
derived from the content, so sharing the same configuration twice yields the
same link instead of piling up duplicates.
"""

from __future__ import annotations

import hashlib
import json
import re
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ..project import Project

SHARE_ID_LENGTH = 12
_ALPHABET = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz"
_SHARE_ID_RE = re.compile(rf"^[0-9A-Za-z]{{{SHARE_ID_LENGTH}}}$")


class ShareNotFoundError(KeyError):
    pass


def share_id_for(document: dict[str, Any]) -> str:
    """Short base62 ID (~71 bits) from the SHA-256 of the canonical JSON."""
    canonical = json.dumps(document, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    number = int.from_bytes(hashlib.sha256(canonical.encode("utf-8")).digest(), "big")
    chars = []
    for _ in range(SHARE_ID_LENGTH):
        number, remainder = divmod(number, len(_ALPHABET))
        chars.append(_ALPHABET[remainder])
    return "".join(chars)


class ShareStore:
    def __init__(self, root: str | Path) -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()

    def create(self, project: Project) -> dict[str, Any]:
        document = project.model_dump(mode="json")
        share_id = share_id_for(document)
        path = self._path(share_id)
        with self._lock:
            if path.is_file():
                return json.loads(path.read_text(encoding="utf-8"))
            record = {"id": share_id, "created_at": _now(), "project": document}
            temporary = path.with_suffix(".json.tmp")
            temporary.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
            temporary.replace(path)
        return record

    def get(self, share_id: str) -> dict[str, Any]:
        path = self._path(share_id)
        if not path.is_file():
            raise ShareNotFoundError(share_id)
        return json.loads(path.read_text(encoding="utf-8"))

    def _path(self, share_id: str) -> Path:
        if not _SHARE_ID_RE.fullmatch(share_id or ""):
            raise ShareNotFoundError(share_id)
        return self.root / f"{share_id}.json"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")
