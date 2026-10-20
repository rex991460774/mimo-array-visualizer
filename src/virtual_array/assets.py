"""Content-addressed store for imported data files.

Uploaded files are kept verbatim under ``<root>/<sha256>/<original name>`` so
the existing file loaders (which rely on the file suffix to choose CSV/TSV/XLSX
parsing) work unchanged, and so a report can name the original file.  The
SHA-256 digest is the asset ID referenced from project documents; the same
file uploaded twice resolves to the same asset.
"""

from __future__ import annotations

import hashlib
import json
import re
import threading
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

ALLOWED_SUFFIXES = {".csv", ".tsv", ".txt", ".xlsx", ".xlsm"}
MAX_ASSET_BYTES = 32 * 1024 * 1024
_ASSET_ID_RE = re.compile(r"^[0-9a-f]{64}$")


def is_asset_id(value: str) -> bool:
    """Whether ``value`` has the shape of a content ID (SHA-256 hex)."""
    return bool(_ASSET_ID_RE.fullmatch(value or ""))
_META_NAME = "meta.json"


@dataclass(frozen=True)
class AssetInfo:
    id: str
    filename: str
    size: int
    uploaded_at: str


class AssetNotFoundError(KeyError):
    pass


def check_asset(filename: str, content: bytes) -> str:
    """Validate an upload without storing it; returns the sanitized file name."""
    safe_name = sanitize_filename(filename)
    suffix = Path(safe_name).suffix.lower()
    if suffix not in ALLOWED_SUFFIXES:
        allowed = ", ".join(sorted(ALLOWED_SUFFIXES))
        raise ValueError(f"Unsupported file type {suffix or '(none)'}; use {allowed}.")
    if not content:
        raise ValueError("The uploaded file is empty.")
    if len(content) > MAX_ASSET_BYTES:
        raise ValueError(f"The uploaded file exceeds {MAX_ASSET_BYTES // (1024 * 1024)} MB.")
    return safe_name


class AssetStore:
    def __init__(self, root: str | Path) -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()

    def add(self, filename: str, content: bytes) -> AssetInfo:
        safe_name = check_asset(filename, content)
        asset_id = hashlib.sha256(content).hexdigest()
        directory = self.root / asset_id
        with self._lock:
            existing = self._read_meta(directory)
            if existing is not None:
                return existing
            directory.mkdir(parents=True, exist_ok=True)
            temporary = directory / f".{safe_name}.tmp"
            temporary.write_bytes(content)
            temporary.replace(directory / safe_name)
            info = AssetInfo(
                id=asset_id,
                filename=safe_name,
                size=len(content),
                uploaded_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
            )
            (directory / _META_NAME).write_text(
                json.dumps(asdict(info), ensure_ascii=False), encoding="utf-8"
            )
            return info

    def info(self, asset_id: str) -> AssetInfo:
        info = self._read_meta(self._directory(asset_id))
        if info is None:
            raise AssetNotFoundError(asset_id)
        return info

    def path(self, asset_id: str) -> Path:
        info = self.info(asset_id)
        return self._directory(asset_id) / info.filename

    def read_bytes(self, asset_id: str) -> bytes:
        return self.path(asset_id).read_bytes()

    def exists(self, asset_id: str) -> bool:
        try:
            self.info(asset_id)
        except AssetNotFoundError:
            return False
        return True

    def _directory(self, asset_id: str) -> Path:
        if not _ASSET_ID_RE.fullmatch(asset_id or ""):
            raise AssetNotFoundError(asset_id)
        return self.root / asset_id

    @staticmethod
    def _read_meta(directory: Path) -> AssetInfo | None:
        meta_path = directory / _META_NAME
        if not meta_path.is_file():
            return None
        data = json.loads(meta_path.read_text(encoding="utf-8"))
        return AssetInfo(**data)


def sanitize_filename(filename: str) -> str:
    name = Path(str(filename or "")).name.strip()
    name = re.sub(r"[\x00-\x1f/\\:*?\"<>|]", "_", name)
    name = name.lstrip(".")
    if not name:
        name = "upload.csv"
    if len(name) > 160:
        stem, suffix = Path(name).stem, Path(name).suffix
        name = stem[: 160 - len(suffix)] + suffix
    return name
