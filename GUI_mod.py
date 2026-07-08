from __future__ import annotations

import sys
import subprocess
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent
SRC_DIR = PROJECT_ROOT / "src"
VENV_PYTHON = PROJECT_ROOT / ".venv" / "Scripts" / "python.exe"
VENV_PYTHONW = PROJECT_ROOT / ".venv" / "Scripts" / "pythonw.exe"


def _workspace_python_executables() -> set[Path]:
    executables = {VENV_PYTHON.resolve()}
    if VENV_PYTHONW.exists():
        executables.add(VENV_PYTHONW.resolve())
    return executables


def _relaunch_with_workspace_python() -> None:
    launcher = VENV_PYTHONW if sys.platform == "win32" and VENV_PYTHONW.exists() else VENV_PYTHON
    command = [str(launcher), str(Path(__file__).resolve()), *sys.argv[1:]]
    if sys.platform == "win32" and launcher == VENV_PYTHONW:
        subprocess.Popen(
            command,
            cwd=str(PROJECT_ROOT),
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            close_fds=True,
        )
        raise SystemExit(0)
    raise SystemExit(subprocess.call(command, cwd=str(PROJECT_ROOT)))

if (
    not getattr(sys, "frozen", False)
    and VENV_PYTHON.exists()
    and Path(sys.executable).resolve() not in _workspace_python_executables()
):
    _relaunch_with_workspace_python()

if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

if sys.platform == "win32":
    try:
        import ctypes

        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass

from virtual_array.logging_config import configure_logging, install_excepthook  # noqa: E402


configure_logging()
install_excepthook()

from virtual_array.gui_mod import main  # noqa: E402


if __name__ == "__main__":
    main()
