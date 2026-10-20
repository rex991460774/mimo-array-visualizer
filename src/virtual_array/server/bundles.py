"""Safe reading of uploaded project bundles (``.mimo.zip``).

The server has no authentication, so a bundle is untrusted input.  Members are
never decompressed blindly: declared sizes are checked first, each member is
read as a stream capped at its limit (headers can lie), and the member count
and total decompressed size are bounded.  This keeps a ~1 MB zip bomb from
expanding into gigabytes of memory.
"""

from __future__ import annotations

import io
import json
import zipfile
import zlib
from dataclasses import dataclass
from typing import Any

from ..assets import MAX_ASSET_BYTES, check_asset, is_asset_id

MAX_BUNDLE_MEMBERS = 256
MAX_PROJECT_JSON_BYTES = 4 * 1024 * 1024
MAX_BUNDLE_UNCOMPRESSED_BYTES = 5 * MAX_ASSET_BYTES


class BundleError(ValueError):
    pass


@dataclass(frozen=True)
class BundledAsset:
    old_id: str
    filename: str
    data: bytes


def read_bundle(content: bytes) -> tuple[Any, list[BundledAsset]]:
    """Return the bundle's project document and its asset files."""
    try:
        archive = zipfile.ZipFile(io.BytesIO(content))
    except (zipfile.BadZipFile, OSError) as exc:
        raise BundleError("Not a valid project bundle (.zip).") from exc
    with archive:
        infos = archive.infolist()
        if len(infos) > MAX_BUNDLE_MEMBERS:
            raise BundleError(f"Bundle has more than {MAX_BUNDLE_MEMBERS} files.")
        if sum(info.file_size for info in infos) > MAX_BUNDLE_UNCOMPRESSED_BYTES:
            raise BundleError("Bundle contents are too large.")
        try:
            project_info = archive.getinfo("project.json")
        except KeyError as exc:
            raise BundleError("Bundle has no project.json.") from exc

        budget = _Budget(MAX_BUNDLE_UNCOMPRESSED_BYTES)
        raw = _read_member(archive, project_info, MAX_PROJECT_JSON_BYTES, budget, "project.json")
        try:
            document = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise BundleError("project.json is not valid JSON.") from exc

        bundled: list[BundledAsset] = []
        for info in infos:
            parts = info.filename.split("/")
            if info.is_dir() or len(parts) != 3 or parts[0] != "assets" or not parts[2]:
                continue
            # Asset IDs are rewritten by text replacement in project.json, so
            # only genuine content IDs are safe to remap.
            if not is_asset_id(parts[1]):
                continue
            data = _read_member(archive, info, MAX_ASSET_BYTES, budget, parts[2])
            try:
                check_asset(parts[2], data)
            except ValueError as exc:
                raise BundleError(f"Bundled file {parts[2]}: {exc}") from exc
            bundled.append(BundledAsset(old_id=parts[1], filename=parts[2], data=data))
    return document, bundled


class _Budget:
    def __init__(self, remaining: int) -> None:
        self.remaining = remaining


def _read_member(
    archive: zipfile.ZipFile, info: zipfile.ZipInfo, limit: int, budget: _Budget, label: str
) -> bytes:
    if info.file_size > limit:
        raise BundleError(f"Bundled file {label} is too large.")
    cap = min(limit, budget.remaining)
    try:
        with archive.open(info) as handle:
            data = handle.read(cap + 1)
    except (zipfile.BadZipFile, RuntimeError, NotImplementedError, zlib.error, EOFError, OSError) as exc:
        raise BundleError(f"Bundled file {label} is damaged or unsupported.") from exc
    if len(data) > limit:
        raise BundleError(f"Bundled file {label} is too large.")
    if len(data) > budget.remaining:
        raise BundleError("Bundle contents are too large.")
    budget.remaining -= len(data)
    return data
