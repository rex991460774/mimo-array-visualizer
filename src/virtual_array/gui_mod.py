"""Compatibility alias for the canonical :mod:`virtual_array.gui` module.

The former experimental entrypoint is intentionally kept importable while all
implementation and launch paths live in ``virtual_array.gui``.
"""

from __future__ import annotations

from . import gui as _implementation


for _name in dir(_implementation):
    if not _name.startswith("__"):
        globals()[_name] = getattr(_implementation, _name)
if __name__ == "__main__":
    main()
