from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def test_case4_build_array_import_does_not_import_pyplot() -> None:
    project_root = Path(__file__).resolve().parents[1]
    code = (
        "import sys;"
        "sys.path.insert(0, 'src');"
        "from virtual_array.examples.case4_5tx7rx_sel import build_array;"
        "build_array();"
        "raise SystemExit(1 if 'matplotlib.pyplot' in sys.modules else 0)"
    )

    result = subprocess.run(
        [sys.executable, "-c", code],
        cwd=project_root,
        check=False,
    )

    assert result.returncode == 0
