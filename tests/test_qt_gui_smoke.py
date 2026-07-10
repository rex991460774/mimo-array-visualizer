from __future__ import annotations

import json
import os
from pathlib import Path

import numpy as np
import pytest


# This must be selected before QApplication is created by any GUI import.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

QtWidgets = pytest.importorskip("PySide6.QtWidgets")
QtCore = pytest.importorskip("PySide6.QtCore")

from scripts.capture_ui_review import (  # noqa: E402
    close_gui_session,
    create_gui_session,
    locate_page_navigator,
    process_events,
    render_widget,
)


@pytest.fixture(scope="module")
def isolated_appdata(tmp_path_factory: pytest.TempPathFactory):
    path = tmp_path_factory.mktemp("qt-gui-appdata")
    previous = {
        name: os.environ.get(name) for name in ("APPDATA", "LOCALAPPDATA")
    }
    os.environ["APPDATA"] = str(path)
    os.environ["LOCALAPPDATA"] = str(path)
    try:
        yield path
    finally:
        for name, value in previous.items():
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value


@pytest.fixture(scope="module")
def gui_session(isolated_appdata: Path):
    del isolated_appdata
    session = create_gui_session()
    try:
        yield session
    finally:
        close_gui_session(session)


def _main_tab_labels(session) -> list[str]:
    navigator = locate_page_navigator(session)
    assert navigator is not None, "canonical GUI must expose its main page navigator"
    tab_source = navigator.tab_widget or navigator.tab_bar
    assert tab_source is not None, "main pages must expose visible tab labels"
    return [str(tab_source.tabText(index)) for index in range(navigator.count)]


def _visible_dialogs(session) -> list:
    return [
        widget
        for widget in session.app.topLevelWidgets()
        if isinstance(widget, QtWidgets.QDialog) and widget.isVisible()
    ]


def _open_modeless_dialog(session, invocation) -> object:
    baseline = {id(dialog) for dialog in _visible_dialogs(session)}
    invocation()
    process_events(session.app, cycles=6)
    opened = [
        dialog for dialog in _visible_dialogs(session) if id(dialog) not in baseline
    ]
    assert opened, "dialog action must create and show a QDialog"
    return opened[-1]


def _close_with_standard_button(session, dialog, standard_button) -> None:
    boxes = dialog.findChildren(QtWidgets.QDialogButtonBox)
    buttons = [box.button(standard_button) for box in boxes]
    buttons = [button for button in buttons if button is not None]
    assert buttons, f"dialog must expose {standard_button!r} through QDialogButtonBox"
    buttons[-1].click()
    process_events(session.app, cycles=5)
    assert all(candidate is not dialog for candidate in _visible_dialogs(session))


def _sample_element_pattern():
    from virtual_array.element_pattern import ElementPattern

    angles = np.linspace(-90.0, 90.0, 181)
    horizontal = -np.minimum((angles / 27.0) ** 2 * 3.0, 35.0)
    elevation = -np.minimum((angles / 34.0) ** 2 * 3.0, 35.0)
    return ElementPattern(
        name="Qt dialog smoke pattern",
        source_path="qt-dialog-smoke.csv",
        angle_column="Angle",
        horizontal_column="Az Gain",
        elevation_column="El Gain",
        angles_deg=angles,
        horizontal_gain_db=horizontal,
        elevation_gain_db=elevation,
    )


@pytest.mark.parametrize("width,height", [(1100, 650), (1366, 768)])
def test_canonical_gui_renders_at_target_sizes(
    gui_session, tmp_path: Path, width: int, height: int
) -> None:
    window = gui_session.window
    assert isinstance(window, QtWidgets.QWidget)

    window.resize(width, height)
    process_events(gui_session.app, cycles=6)

    assert window.isVisible()
    assert (window.width(), window.height()) == (width, height), (
        "the resizable workspace must preserve the requested logical size; "
        "layout minimums must not silently enlarge it"
    )
    screenshot = render_widget(window, tmp_path / f"main-{width}x{height}.png")
    assert screenshot.stat().st_size > 1_000


def test_canonical_gui_exposes_and_switches_three_main_pages(
    gui_session, tmp_path: Path
) -> None:
    navigator = locate_page_navigator(gui_session)
    assert navigator is not None, "canonical GUI must expose its main page navigator"
    assert navigator.count >= 3

    for index in range(3):
        navigator.select(index)
        process_events(gui_session.app, cycles=5)
        assert navigator.current_index == index
        screenshot = render_widget(gui_session.window, tmp_path / f"page-{index}.png")
        assert screenshot.stat().st_size > 1_000


def test_canonical_gui_keeps_key_workspace_and_dialog_controls(gui_session) -> None:
    controller = gui_session.controller
    window = gui_session.window

    # Plot attributes are stable across the compatibility and native Qt shells.
    assert getattr(controller, "phys_canvas", None) is not None
    assert getattr(controller, "virt_canvas", None) is not None
    assert getattr(controller, "az_chart", None) is not None
    assert getattr(controller, "el_chart", None) is not None

    assert len(window.findChildren(QtWidgets.QAbstractButton)) >= 3
    assert len(window.findChildren(QtWidgets.QLineEdit)) >= 2
    for method_name in (
        "open_dbf_dictionary_dialog",
        "open_channel_patterns_dialog",
        "_show_user_manual_dialog",
    ):
        assert callable(getattr(controller, method_name, None))


def test_native_shell_exposes_shortcuts_focus_and_splitter(gui_session) -> None:
    from PySide6 import QtCore, QtGui

    controller = gui_session.controller
    window = gui_session.window

    assert isinstance(controller.native_menu_bar, QtWidgets.QMenuBar)
    assert isinstance(controller.native_status_bar, QtWidgets.QStatusBar)
    assert isinstance(controller.workspace_splitter, QtWidgets.QSplitter)
    assert controller.workspace_splitter.handleWidth() >= 6

    for key in (
        "menu_import_layout",
        "menu_export_layout",
        "menu_undo",
        "menu_redo",
    ):
        action = controller.native_actions[key]
        assert isinstance(action, QtGui.QAction)
        assert not action.shortcut().isEmpty()

    assert controller.auto_apply_button._qt.property("fluentRole") == "primary"
    focusable = window.findChildren(QtWidgets.QLineEdit) + window.findChildren(
        QtWidgets.QAbstractButton
    )
    assert focusable
    assert all(
        widget.focusPolicy() != QtCore.Qt.FocusPolicy.NoFocus
        for widget in focusable
        if widget.isEnabled() and widget.isVisible()
    )
    assert controller.main_notebook._qt.tabBar().accessibleName()


def test_configuration_and_manual_dialogs_use_native_qt_controls(gui_session) -> None:
    controller = gui_session.controller
    dialog_specs = (
        (controller.open_dbf_dictionary_dialog, True, False),
        (controller.open_channel_patterns_dialog, True, False),
        (controller._show_user_manual_dialog, False, True),
    )

    for invocation, expects_table, expects_text_browser in dialog_specs:
        dialog = _open_modeless_dialog(gui_session, invocation)
        closed = False
        try:
            assert dialog.windowTitle()
            button_boxes = dialog.findChildren(QtWidgets.QDialogButtonBox)
            assert button_boxes, "custom dialogs must use QDialogButtonBox"
            if expects_table:
                tables = dialog.findChildren(QtWidgets.QTableView)
                assert tables, "DBF and channel dialogs must expose a native QTableView"
                assert all(
                    isinstance(table.model(), QtCore.QAbstractTableModel)
                    for table in tables
                )
                assert all(table.model().columnCount() > 0 for table in tables)
            if expects_text_browser:
                browsers = dialog.findChildren(QtWidgets.QTextBrowser)
                assert len(browsers) == 1
                assert browsers[0].toPlainText().strip()

            _close_with_standard_button(
                gui_session,
                dialog,
                QtWidgets.QDialogButtonBox.StandardButton.Close,
            )
            closed = True
        finally:
            if not closed:
                try:
                    dialog.reject()
                except RuntimeError:
                    pass
                process_events(gui_session.app, cycles=3)


def test_element_pattern_confirmation_dialog_can_be_cancelled_modally(
    gui_session,
) -> None:
    controller = gui_session.controller
    baseline = {id(dialog) for dialog in _visible_dialogs(gui_session)}
    observation: dict[str, object] = {}
    attempts = 0
    watchdog = QtCore.QTimer()
    watchdog.setSingleShot(True)

    def abort_modal_wait() -> None:
        observation.setdefault(
            "error", TimeoutError("element-pattern confirmation did not close")
        )
        active = gui_session.app.activeModalWidget()
        if isinstance(active, QtWidgets.QDialog):
            active.reject()

    watchdog.timeout.connect(abort_modal_wait)

    def cancel_confirmation() -> None:
        nonlocal attempts
        attempts += 1
        opened = [
            dialog
            for dialog in _visible_dialogs(gui_session)
            if id(dialog) not in baseline
        ]
        if not opened and attempts < 100:
            QtCore.QTimer.singleShot(10, cancel_confirmation)
            return
        if not opened:
            observation["error"] = AssertionError(
                "element-pattern confirmation did not show a modal QDialog"
            )
            return

        dialog = opened[-1]
        try:
            observation["modal"] = dialog.isModal()
            boxes = dialog.findChildren(QtWidgets.QDialogButtonBox)
            observation["button_box_count"] = len(boxes)
            cancel_buttons = [
                box.button(QtWidgets.QDialogButtonBox.StandardButton.Cancel)
                for box in boxes
            ]
            cancel_buttons = [button for button in cancel_buttons if button is not None]
            observation["has_cancel"] = bool(cancel_buttons)
            if cancel_buttons:
                cancel_buttons[-1].click()
            else:
                dialog.reject()
        except BaseException as exc:
            observation["error"] = exc
            dialog.reject()

    QtCore.QTimer.singleShot(0, cancel_confirmation)
    watchdog.start(3_000)
    try:
        result = controller._confirm_element_pattern_import(_sample_element_pattern())
    finally:
        watchdog.stop()
    process_events(gui_session.app, cycles=4)

    error = observation.get("error")
    if isinstance(error, BaseException):
        raise error
    assert result is None
    assert observation.get("modal") is True
    assert observation.get("button_box_count", 0) >= 1
    assert observation.get("has_cancel") is True
    assert not [
        dialog
        for dialog in _visible_dialogs(gui_session)
        if id(dialog) not in baseline
    ]


def test_main_page_labels_are_localized_in_all_supported_languages(gui_session) -> None:
    controller = gui_session.controller
    expected = {
        "zh": ["物理与虚拟阵列", "1D DBF", "2D DBF"],
        "en": ["Physical & Virtual", "1D DBF", "2D DBF"],
        "ja": ["物理・仮想アレイ", "1D DBF", "2D DBF"],
    }
    expected_dynamic = {
        "zh": ("不可用", "边界受限"),
        "en": ("Unavailable", "Boundary limited"),
        "ja": ("利用不可", "境界制限"),
    }
    original_language = controller.language

    try:
        for language, labels in expected.items():
            controller.set_language(language)
            process_events(gui_session.app, cycles=5)
            assert controller.language == language
            assert _main_tab_labels(gui_session)[:3] == labels
            margin, cut_reason = expected_dynamic[language]
            assert controller.secondary_value_labels["row_az_margin"]._qt.text() == margin
            assert controller.secondary_value_labels["row_az_cut"]._qt.text() == cut_reason
    finally:
        controller.set_language(original_language)
        process_events(gui_session.app, cycles=5)


def test_initial_1t1r_uses_neutral_capability_empty_states(gui_session) -> None:
    controller = gui_session.controller
    navigator = locate_page_navigator(gui_session)
    assert navigator is not None
    original_index = navigator.current_index

    kinds = [element.kind for element in controller.elements]
    assert kinds.count("tx") == 1
    assert kinds.count("rx") == 1
    metrics = controller.current_metrics
    assert metrics is not None
    assert metrics.x_aperture == 0.0
    assert metrics.y_aperture == 0.0
    assert metrics.azimuth_resolution is None
    assert metrics.elevation_resolution is None

    try:
        navigator.select(1)
        process_events(gui_session.app, cycles=5)
        expected_1d_titles = (
            "当前阵列没有方位孔径",
            "当前阵列没有俯仰孔径",
        )
        for chart, expected_title in zip(
            (controller.az_chart, controller.el_chart),
            expected_1d_titles,
        ):
            overlay = chart.empty_overlay
            assert overlay is not None and overlay.isVisible()
            assert overlay.title_label.text() == expected_title
            assert overlay.body_label.text()
            assert not chart.play_button._qt.isEnabled()

        navigator.select(2)
        process_events(gui_session.app, cycles=5)
        overlay_2d = controller.dbf2d_empty_overlay
        assert overlay_2d is not None and overlay_2d.isVisible()
        assert overlay_2d.title_label.text() == "当前阵列不具备完整 2D 测角能力"
        assert overlay_2d.body_label.text()
        assert controller.dbf2d_hover_db.size == 0
        assert not controller.dbf2d_az_button._qt.isEnabled()
        assert not controller.dbf2d_el_button._qt.isEnabled()
    finally:
        navigator.select(original_index)
        process_events(gui_session.app, cycles=3)


def test_v1_state_round_trips_active_tab_and_splitter_sizes(
    isolated_appdata: Path,
) -> None:
    from virtual_array.app_state import state_path

    target = state_path()
    assert target.parent.parent.resolve() == isolated_appdata.resolve()
    previous_state = target.read_bytes() if target.exists() else None
    sessions = []

    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        # A pre-feature v1 state omits both optional window fields.  It must
        # still load with the default page and a usable splitter.
        target.write_text(
            json.dumps(
                {
                    "version": 1,
                    "language": "zh",
                    "window": {"state": "normal"},
                }
            ),
            encoding="utf-8",
        )
        first = create_gui_session((1366, 768))
        sessions.append(first)
        first_navigator = locate_page_navigator(first)
        assert first_navigator is not None
        assert first_navigator.current_index == 0
        default_sizes = first.controller.workspace_splitter.sizes()
        assert len(default_sizes) == 2 and all(size > 0 for size in default_sizes)

        first_navigator.select(2)
        first.controller.workspace_splitter.setSizes([900, 320])
        process_events(first.app, cycles=6)
        saved_sizes = [
            int(size) for size in first.controller.workspace_splitter.sizes()
        ]
        first.controller._save_local_state()

        persisted = json.loads(target.read_text(encoding="utf-8"))
        assert persisted["version"] == 1
        assert persisted["window"]["active_tab"] == 2
        assert persisted["window"]["splitter_sizes"] == saved_sizes

        # Geometry restoration is deliberately excluded from this assertion:
        # an offscreen platform may expose a smaller synthetic screen and clamp
        # it.  Keep the same logical test width so Qt can apply the two saved
        # pane sizes without unrelated screen-geometry scaling.
        persisted["window"].pop("geometry", None)
        target.write_text(json.dumps(persisted), encoding="utf-8")
        close_gui_session(first)
        sessions.pop()
        restored = create_gui_session((1366, 768))
        sessions.append(restored)
        process_events(restored.app, cycles=8)
        restored_navigator = locate_page_navigator(restored)
        assert restored_navigator is not None
        assert restored_navigator.current_index == 2
        assert restored.controller.workspace_splitter.sizes() == saved_sizes
    finally:
        for session in reversed(sessions):
            close_gui_session(session)
        if previous_state is None:
            target.unlink(missing_ok=True)
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(previous_state)
