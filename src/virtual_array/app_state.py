from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any


APP_DIR_NAME = "antenna-array"
STATE_FILE_NAME = "state.json"


def default_app_dir() -> Path:
    appdata = os.environ.get("APPDATA")
    if appdata:
        return Path(appdata) / APP_DIR_NAME

    local_appdata = os.environ.get("LOCALAPPDATA")
    if local_appdata:
        return Path(local_appdata) / APP_DIR_NAME

    return Path.home() / f".{APP_DIR_NAME}"


def state_path() -> Path:
    return default_app_dir() / STATE_FILE_NAME


def load_state(path: str | Path | None = None) -> dict[str, Any]:
    target = Path(path) if path is not None else state_path()
    if not target.exists():
        return {}
    with target.open("r", encoding="utf-8") as file:
        data = json.load(file)
    return data if isinstance(data, dict) else {}


def save_state(state: dict[str, Any], path: str | Path | None = None) -> Path:
    target = Path(path) if path is not None else state_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = target.with_suffix(target.suffix + ".tmp")
    with tmp_path.open("w", encoding="utf-8") as file:
        json.dump(state, file, ensure_ascii=False, indent=2)
        file.write("\n")
    tmp_path.replace(target)
    return target
