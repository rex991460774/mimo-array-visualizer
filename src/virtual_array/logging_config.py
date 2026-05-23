from __future__ import annotations

import logging
import os
import sys
import tempfile
from logging.handlers import RotatingFileHandler
from pathlib import Path
from types import TracebackType


APP_DIR_NAME = "antenna-array"
LOG_FILE_NAME = "antenna-array.log"
LOG_DIR_ENV = "ANTENNA_ARRAY_LOG_DIR"
_HANDLER_MARKER = "_antenna_array_file_handler"
_EXCEPTHOOK_MARKER = "_antenna_array_excepthook"


def default_log_dir() -> Path:
    override = os.environ.get(LOG_DIR_ENV)
    if override:
        return Path(override).expanduser()

    appdata = os.environ.get("APPDATA")
    if appdata:
        return Path(appdata) / APP_DIR_NAME / "logs"

    local_appdata = os.environ.get("LOCALAPPDATA")
    if local_appdata:
        return Path(local_appdata) / APP_DIR_NAME / "logs"

    return Path.home() / f".{APP_DIR_NAME}" / "logs"


def configure_logging(
    log_dir: str | Path | None = None,
    level: int = logging.INFO,
) -> Path:
    target_dir = Path(log_dir).expanduser() if log_dir is not None else default_log_dir()
    log_path = _writable_log_path(target_dir)
    root_logger = logging.getLogger()
    root_logger.setLevel(level)

    existing_handler = _existing_file_handler()
    if existing_handler is not None:
        existing_path = Path(existing_handler.baseFilename)
        if existing_path == log_path:
            return existing_path
        root_logger.removeHandler(existing_handler)
        existing_handler.close()

    handler = RotatingFileHandler(
        log_path,
        maxBytes=1_000_000,
        backupCount=5,
        encoding="utf-8",
    )
    setattr(handler, _HANDLER_MARKER, True)
    handler.setLevel(level)
    handler.setFormatter(
        logging.Formatter(
            fmt="%(asctime)s %(levelname)s [%(name)s] %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
    )
    root_logger.addHandler(handler)
    logging.captureWarnings(True)
    logging.getLogger(__name__).info("Logging initialized at %s", log_path)
    return log_path


def install_excepthook() -> None:
    current_hook = sys.excepthook
    if getattr(current_hook, _EXCEPTHOOK_MARKER, False):
        return

    def log_uncaught_exception(
        exc_type: type[BaseException],
        exc_value: BaseException,
        exc_traceback: TracebackType | None,
    ) -> None:
        if issubclass(exc_type, KeyboardInterrupt):
            current_hook(exc_type, exc_value, exc_traceback)
            return

        logging.getLogger(__name__).critical(
            "Uncaught exception",
            exc_info=(exc_type, exc_value, exc_traceback),
        )
        current_hook(exc_type, exc_value, exc_traceback)

    setattr(log_uncaught_exception, _EXCEPTHOOK_MARKER, True)
    sys.excepthook = log_uncaught_exception


def current_log_path() -> Path | None:
    handler = _existing_file_handler()
    return Path(handler.baseFilename) if handler is not None else None


def _existing_file_handler() -> RotatingFileHandler | None:
    for handler in logging.getLogger().handlers:
        if getattr(handler, _HANDLER_MARKER, False):
            return handler
    return None


def _writable_log_path(log_dir: Path) -> Path:
    try:
        log_dir.mkdir(parents=True, exist_ok=True)
        return log_dir / LOG_FILE_NAME
    except OSError:
        fallback_dir = Path(tempfile.gettempdir()) / APP_DIR_NAME / "logs"
        fallback_dir.mkdir(parents=True, exist_ok=True)
        return fallback_dir / LOG_FILE_NAME
