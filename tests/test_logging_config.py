from __future__ import annotations

import logging
import sys

from virtual_array.logging_config import (
    LOG_FILE_NAME,
    configure_logging,
    current_log_path,
    default_log_dir,
    install_excepthook,
)


def test_default_log_dir_uses_appdata(monkeypatch) -> None:
    monkeypatch.setenv("APPDATA", r"C:\Users\tester\AppData\Roaming")
    monkeypatch.delenv("ANTENNA_ARRAY_LOG_DIR", raising=False)

    assert str(default_log_dir()).endswith(r"antenna-array\logs")


def test_env_override_controls_log_dir(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("ANTENNA_ARRAY_LOG_DIR", str(tmp_path))

    assert default_log_dir() == tmp_path


def test_configure_logging_writes_to_rotating_file(tmp_path) -> None:
    log_path = configure_logging(tmp_path)

    logging.getLogger("virtual_array.test").error("diagnostic test message")
    for handler in logging.getLogger().handlers:
        handler.flush()

    assert log_path == tmp_path / LOG_FILE_NAME
    assert current_log_path() == log_path
    assert "diagnostic test message" in log_path.read_text(encoding="utf-8")


def test_configure_logging_replaces_project_file_handler(tmp_path) -> None:
    first_path = configure_logging(tmp_path / "first")
    second_path = configure_logging(tmp_path / "second")

    assert first_path != second_path
    assert current_log_path() == second_path


def test_install_excepthook_is_idempotent() -> None:
    previous_hook = sys.excepthook
    try:
        install_excepthook()
        installed_hook = sys.excepthook
        install_excepthook()

        assert sys.excepthook is installed_hook
    finally:
        sys.excepthook = previous_hook
