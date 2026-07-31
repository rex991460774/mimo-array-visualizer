from __future__ import annotations

import os

import pytest


os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

QtCore = pytest.importorskip("PySide6.QtCore")
QtWidgets = pytest.importorskip("PySide6.QtWidgets")

from virtual_array.qt_tk import Label, Toplevel, _ensure_app  # noqa: E402


@pytest.fixture(scope="module")
def app():
    return _ensure_app()


class _FirstShowProbe(QtCore.QObject):
    def __init__(self, dialog: QtWidgets.QDialog) -> None:
        super().__init__(dialog)
        self.dialog = dialog
        self.snapshots: list[tuple[str, str, int, QtCore.QSize]] = []

    def eventFilter(self, watched, event):  # noqa: N802
        dialog = getattr(self, "dialog", None)
        if watched is dialog and event.type() == QtCore.QEvent.Type.Show:
            self.snapshots.append(
                (
                    dialog.objectName(),
                    dialog.windowTitle(),
                    len(dialog.findChildren(QtWidgets.QLabel)),
                    dialog.size(),
                )
            )
        return super().eventFilter(watched, event)


def test_toplevel_first_visible_frame_is_built_and_sized(app) -> None:
    top = Toplevel()
    probe = _FirstShowProbe(top._qt)
    top._qt.installEventFilter(probe)

    assert not top._qt.isVisible()
    top._qt.setObjectName("readyDialog")
    top.title("Ready")
    Label(top, text="Complete content").pack()
    top.geometry("720x520+20+30")

    assert not top._qt.isVisible()
    app.processEvents()

    assert top._qt.isVisible()
    assert probe.snapshots == [
        ("readyDialog", "Ready", 1, QtCore.QSize(720, 520))
    ]

    top.destroy()
    app.processEvents()


def test_destroyed_toplevel_is_not_reshown_by_deferred_timer(app) -> None:
    top = Toplevel()
    top.destroy()

    app.processEvents()

    assert not top._qt.isVisible()
