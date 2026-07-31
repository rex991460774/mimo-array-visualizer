from __future__ import annotations

import os

import pytest


os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

QtCore = pytest.importorskip("PySide6.QtCore")
QtGui = pytest.importorskip("PySide6.QtGui")
QtWidgets = pytest.importorskip("PySide6.QtWidgets")
QtTest = pytest.importorskip("PySide6.QtTest")

from virtual_array.native_theme import apply_native_theme  # noqa: E402
from virtual_array.qt_tk import AppleSwitch, ttk  # noqa: E402


HAND = QtCore.Qt.CursorShape.PointingHandCursor
ARROW = QtCore.Qt.CursorShape.ArrowCursor


@pytest.fixture(scope="module")
def qapp():
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    apply_native_theme(app)
    yield app


def _show(qapp, widget: QtWidgets.QWidget) -> None:
    widget.show()
    qapp.processEvents()


def test_buttons_switches_and_slider_track_enabled_state(qapp) -> None:
    parent = QtWidgets.QWidget()
    layout = QtWidgets.QVBoxLayout(parent)
    controls = (
        QtWidgets.QPushButton("Push", parent),
        QtWidgets.QToolButton(parent),
        QtWidgets.QRadioButton("Radio", parent),
        AppleSwitch("Switch", parent),
        QtWidgets.QComboBox(parent),
        QtWidgets.QSlider(QtCore.Qt.Orientation.Horizontal, parent),
    )
    for control in controls:
        layout.addWidget(control)
    _show(qapp, parent)

    try:
        for control in controls:
            assert control.cursor().shape() == HAND
            control.setEnabled(False)
            qapp.processEvents()
            assert control.cursor().shape() == ARROW
            control.setEnabled(True)
            qapp.processEvents()
            assert control.cursor().shape() == HAND
    finally:
        parent.close()
        parent.deleteLater()
        qapp.processEvents()


def test_text_scroll_and_custom_cursor_surfaces_are_not_overridden(qapp) -> None:
    parent = QtWidgets.QWidget()
    layout = QtWidgets.QVBoxLayout(parent)
    line_edit = QtWidgets.QLineEdit(parent)
    text_edit = QtWidgets.QTextEdit(parent)
    scroll_bar = QtWidgets.QScrollBar(parent)
    custom_surface = QtWidgets.QWidget(parent)
    custom_surface.setProperty("preserveCursor", True)
    custom_surface.setCursor(QtGui.QCursor(QtCore.Qt.CursorShape.CrossCursor))
    for widget in (line_edit, text_edit, scroll_bar, custom_surface):
        layout.addWidget(widget)
    _show(qapp, parent)

    try:
        assert line_edit.cursor().shape() != HAND
        assert text_edit.viewport().cursor().shape() != HAND
        assert scroll_bar.cursor().shape() != HAND
        assert custom_surface.cursor().shape() == QtCore.Qt.CursorShape.CrossCursor
    finally:
        parent.close()
        parent.deleteLater()
        qapp.processEvents()


def test_tabs_and_menus_only_point_at_enabled_actions(qapp) -> None:
    tabs = QtWidgets.QTabBar()
    tabs.resize(320, 40)
    tabs.addTab("Enabled")
    tabs.addTab("Disabled")
    tabs.setTabEnabled(1, False)
    _show(qapp, tabs)

    menu = QtWidgets.QMenu()

    try:
        QtTest.QTest.mouseMove(tabs, tabs.tabRect(0).center())
        qapp.processEvents()
        assert tabs.cursor().shape() == HAND
        QtTest.QTest.mouseMove(tabs, tabs.tabRect(1).center())
        qapp.processEvents()
        assert tabs.cursor().shape() == ARROW
        QtTest.QTest.mouseMove(tabs, QtCore.QPoint(tabs.width() - 2, tabs.height() - 2))
        qapp.processEvents()
        assert tabs.cursor().shape() == ARROW

        enabled_action = menu.addAction("Enabled")
        separator = menu.addSeparator()
        disabled_action = menu.addAction("Disabled")
        disabled_action.setEnabled(False)
        _show(qapp, menu)
        for action, expected in (
            (enabled_action, HAND),
            (disabled_action, ARROW),
            (separator, ARROW),
        ):
            QtTest.QTest.mouseMove(menu, menu.actionGeometry(action).center())
            qapp.processEvents()
            assert menu.cursor().shape() == expected
    finally:
        menu.close()
        tabs.close()
        menu.deleteLater()
        tabs.deleteLater()
        qapp.processEvents()


def test_marked_read_only_items_point_only_over_valid_rows(qapp) -> None:
    view = QtWidgets.QListWidget()
    view.resize(260, 160)
    view.setProperty("pointingHandItems", True)
    view.addItem("Selectable")
    editable = QtWidgets.QListWidgetItem("Editable")
    editable.setFlags(editable.flags() | QtCore.Qt.ItemFlag.ItemIsEditable)
    view.addItem(editable)
    _show(qapp, view)

    try:
        QtTest.QTest.mouseMove(view.viewport(), view.visualItemRect(view.item(0)).center())
        qapp.processEvents()
        assert view.viewport().cursor().shape() == HAND
        QtTest.QTest.mouseMove(view.viewport(), view.visualItemRect(view.item(1)).center())
        qapp.processEvents()
        assert view.viewport().cursor().shape() == ARROW
        QtTest.QTest.mouseMove(
            view.viewport(),
            QtCore.QPoint(view.viewport().width() - 2, view.viewport().height() - 2),
        )
        qapp.processEvents()
        assert view.viewport().cursor().shape() == ARROW
    finally:
        view.close()
        view.deleteLater()
        qapp.processEvents()


def test_cursor_policy_installation_is_idempotent(qapp) -> None:
    policy = qapp._workbench_interactive_cursor_policy
    apply_native_theme(qapp)
    assert qapp._workbench_interactive_cursor_policy is policy


def test_compatibility_widget_rebuilds_object_scoped_qss_after_rename(qapp) -> None:
    style_name = "ObjectNameSyncTest.TButton"
    ttk.Style().configure(
        style_name,
        background="#ffffff",
        foreground="#161616",
        bordercolor="#8d8d8d",
        relief="solid",
        padding=(8, 6),
    )
    parent = QtWidgets.QWidget()
    button = ttk.Button(parent, text="Load", style=style_name)
    original_name = button._qt.objectName()
    assert f"#{original_name} {{" in button._qt.styleSheet()

    button._qt.setObjectName("renamedDialogButton")
    qapp.processEvents()

    stylesheet = button._qt.styleSheet()
    assert "#renamedDialogButton {" in stylesheet
    assert f"#{original_name} {{" not in stylesheet
    assert "border: 1px solid #8d8d8d" in stylesheet
    parent.deleteLater()
    qapp.processEvents()
