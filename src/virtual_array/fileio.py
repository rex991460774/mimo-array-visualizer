"""Small file-writing helpers shared by the server-side stores."""

from __future__ import annotations

import contextlib
from pathlib import Path


def atomic_write_bytes(path: Path, data: bytes) -> None:
    """Write via a temporary file and rename, so readers never see a partial file.

    If writing fails (disk full, read-only directory) the temporary file is
    removed instead of being left behind next to the real data.
    """
    temporary = path.with_name(f".{path.name}.tmp")
    try:
        temporary.write_bytes(data)
        temporary.replace(path)
    except BaseException:
        with contextlib.suppress(OSError):
            temporary.unlink()
        raise


def atomic_write_text(path: Path, text: str) -> None:
    atomic_write_bytes(path, text.encode("utf-8"))
