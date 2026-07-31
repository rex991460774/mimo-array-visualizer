from __future__ import annotations

import json
import os
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest


# This must be selected before QApplication is created by any GUI import.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

QtWidgets = pytest.importorskip("PySide6.QtWidgets")
QtCore = pytest.importorskip("PySide6.QtCore")
QtGui = pytest.importorskip("PySide6.QtGui")
QtTest = pytest.importorskip("PySide6.QtTest")

from scripts.capture_ui_review import (  # noqa: E402
    close_gui_session,
    create_gui_session,
    locate_page_navigator,
    process_events,
    render_widget,
)
from virtual_array.qt_tk import AppleSwitch  # noqa: E402


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
    return [
        str(tab_source.tabText(index)).replace("&&", "&")
        for index in range(navigator.count)
    ]


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


@pytest.mark.parametrize(
    "width,height",
    [
        (1024, 650),
        (1100, 650),
        (1280, 720),
        (1366, 768),
        (1920, 1080),
    ],
)
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


def test_header_frequency_keeps_common_values_visible_at_compact_width(
    gui_session,
) -> None:
    controller = gui_session.controller
    window = gui_session.window
    original_language = controller.language
    original_frequency = controller.current_frequency_ghz()
    original_size = window.size()

    try:
        window.resize(1024, 650)
        for language in ("zh", "en", "ja"):
            controller.set_language(language)
            for frequency in (24.0, 77.0, 999.0):
                controller._set_frequency_ghz(frequency)
                controller._refresh_workspace_header()
                process_events(gui_session.app, cycles=3)

                value_label = controller.header_chip_value_labels[
                    "chip_frequency"
                ]._qt
                expected = f"{int(frequency)} GHz"
                assert value_label.text() == expected
                assert value_label.toolTip() == expected
                assert value_label.fontMetrics().horizontalAdvance(expected) <= (
                    value_label.width()
                )

            controller._set_frequency_ghz(12345.123456)
            controller._refresh_workspace_header()
            process_events(gui_session.app, cycles=3)
            value_label = controller.header_chip_value_labels["chip_frequency"]._qt
            assert value_label.text() != value_label.toolTip()
            assert value_label.toolTip() == "12345.123456 GHz"

            chip_row = value_label.parentWidget().parentWidget()
            assert controller.header_title_group._qt.geometry().right() < (
                chip_row.geometry().left()
            )
            assert window.size() == QtCore.QSize(1024, 650)
    finally:
        controller.set_language(original_language)
        controller._set_frequency_ghz(original_frequency)
        controller._refresh_workspace_header()
        window.resize(original_size)
        process_events(gui_session.app, cycles=4)


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
        "open_performance_report_dialog",
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
    assert "menu_export_report" in controller.native_actions
    report_action = controller.native_actions["menu_export_report"]
    assert isinstance(report_action, QtGui.QAction)
    assert report_action in controller.native_menus["menu_file"].actions()
    assert report_action.menu() is None
    assert "menu_export_angle_error_image" not in controller.native_actions
    assert isinstance(controller.native_manual_menu, QtWidgets.QMenu)
    assert len(controller.native_manual_chapter_actions) == 12
    assert controller.native_actions["menu_user_manual_open"].shortcut() == (
        QtGui.QKeySequence(QtGui.QKeySequence.StandardKey.HelpContents)
    )

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


def test_report_dialog_reuses_one_instance_for_sequential_report_and_png_exports(
    gui_session,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from virtual_array.performance_report import (
        generate_angle_error_image,
        generate_performance_report,
    )

    controller = gui_session.controller
    report_dir = tmp_path / "reports"
    report_dir.mkdir()
    report_path = report_dir / "custom-report.pdf"
    report_path.write_bytes(b"existing report placeholder")
    image_path = report_dir / "custom-report_angle_error.png"
    captured: list[dict[str, object]] = []
    overwrite_parents: list[QtWidgets.QWidget] = []
    busy_observations: list[bool] = []
    snapshot = object()

    monkeypatch.setattr(controller, "last_report_dir", report_dir)
    monkeypatch.setattr(controller, "last_report_error_limit_deg", 7.5)
    monkeypatch.setattr(
        controller,
        "current_metrics",
        SimpleNamespace(
            x_aperture=1.0,
            azimuth_resolution=1.0,
            y_aperture=0.0,
            elevation_resolution=None,
        ),
    )
    monkeypatch.setattr(controller, "_performance_report_snapshot", lambda: snapshot)

    def start_export(generator, frozen_snapshot, options, *, export_kind="report"):
        export_parent = controller._performance_export_parent
        assert export_parent is controller._performance_report_dialog
        busy_observations.append(
            not export_parent.save_button.isEnabled()
            and not export_parent.angle_image_button.isEnabled()
            and not export_parent.cancel_button.isEnabled()
        )
        captured.append(
            {
                "generator": generator,
                "snapshot": frozen_snapshot,
                "options": options,
                "export_kind": export_kind,
            }
        )
        # Stand in for thread.finished so this test can issue the next request.
        export_parent.set_export_busy(False)
        controller._performance_export_parent = None

    def confirm_overwrite(parent, *_args, **_kwargs):
        overwrite_parents.append(parent)
        return QtWidgets.QMessageBox.StandardButton.Yes

    monkeypatch.setattr(QtWidgets.QMessageBox, "question", confirm_overwrite)
    monkeypatch.setattr(
        gui_session.gui_module,
        "fit_dialog_to_parent",
        lambda *_args, **_kwargs: None,
    )
    monkeypatch.setattr(controller, "_start_performance_report_export", start_export)

    dialog = None
    try:
        controller.open_performance_report_dialog()
        process_events(gui_session.app, cycles=5)
        dialog = controller._performance_report_dialog
        assert isinstance(dialog, QtWidgets.QDialog)
        assert dialog.isVisible()
        assert dialog.error_limit_spin.value() == pytest.approx(7.5)

        # Invoking the menu again raises the existing form instead of resetting it.
        original_identity = id(dialog)
        controller.open_performance_report_dialog()
        process_events(gui_session.app, cycles=2)
        assert controller._performance_report_dialog is dialog
        assert id(controller._performance_report_dialog) == original_identity

        dialog.output_path_edit.setText(str(report_path))
        dialog.title_edit.setText("Keep these settings")
        dialog.error_limit_spin.setValue(7.5)
        dialog.az_focus_start.setValue(-43)
        dialog.az_focus_stop.setValue(52)

        dialog.save_button.click()
        process_events(gui_session.app, cycles=3)
        assert dialog.isVisible()
        assert dialog.save_button.isEnabled()

        dialog.angle_image_button.click()
        process_events(gui_session.app, cycles=3)

        assert dialog.isVisible()
        assert controller._performance_report_dialog is dialog
        assert [item["export_kind"] for item in captured] == [
            "report",
            "angle_image",
        ]
        assert [item["generator"] for item in captured] == [
            generate_performance_report,
            generate_angle_error_image,
        ]
        assert all(item["snapshot"] is snapshot for item in captured)
        assert busy_observations == [True, True]
        assert overwrite_parents == [dialog]

        report_options = captured[0]["options"]
        image_options = captured[1]["options"]
        assert report_options.output_path == report_path
        assert report_options.title == "Keep these settings"
        assert report_options.error_limit_deg == pytest.approx(7.5)
        assert report_options.azimuth_focus.start_deg == -43
        assert report_options.azimuth_focus.stop_deg == 52
        assert image_options.output_path == image_path
        assert image_options.output_path.parent == report_dir
        assert image_options.error_limit_deg == pytest.approx(7.5)
        assert dialog.title_edit.text() == "Keep these settings"
        assert (dialog.az_focus_start.value(), dialog.az_focus_stop.value()) == (
            -43,
            52,
        )
        assert controller.last_report_dir == report_dir
        assert controller.last_report_error_limit_deg == pytest.approx(7.5)
    finally:
        if dialog is not None:
            dialog.set_export_busy(False)
            dialog.reject()
            process_events(gui_session.app, cycles=4)
        controller._performance_export_parent = None
        gui_session.window.activateWindow()
        process_events(gui_session.app, cycles=3)


def test_carbon_workbench_theme_and_primary_interactions_are_explicit(gui_session) -> None:
    from PySide6 import QtGui

    from virtual_array.native_theme import (
        AppleTokens,
        TOKENS,
        WorkbenchTokens,
        application_stylesheet,
    )

    controller = gui_session.controller
    stylesheet = application_stylesheet()

    assert isinstance(TOKENS, WorkbenchTokens)
    assert AppleTokens is WorkbenchTokens  # backwards-compatible public alias
    assert TOKENS.canvas == "#f4f4f4"
    assert TOKENS.accent == "#0f62fe"
    assert TOKENS.primary_fill == "#0f62fe"
    assert TOKENS.radius <= 4
    assert TOKENS.card_radius <= 4
    assert "QPushButton:focus" in stylesheet
    assert "QScrollBar:vertical" in stylesheet
    assert "QTabBar::tab:selected" in stylesheet
    assert f"border: 1px solid {TOKENS.control_border}" in stylesheet

    def contrast_ratio(first: str, second: str) -> float:
        def luminance(value: str) -> float:
            color = QtGui.QColor(value)
            channels = []
            for channel in (color.redF(), color.greenF(), color.blueF()):
                channels.append(
                    channel / 12.92
                    if channel <= 0.04045
                    else ((channel + 0.055) / 1.055) ** 2.4
                )
            return 0.2126 * channels[0] + 0.7152 * channels[1] + 0.0722 * channels[2]

        lighter, darker = sorted((luminance(first), luminance(second)), reverse=True)
        return (lighter + 0.05) / (darker + 0.05)

    assert contrast_ratio(TOKENS.control_border, TOKENS.surface) >= 3.0
    assert contrast_ratio(TOKENS.primary_fill, "#ffffff") >= 4.5
    assert f"background: {TOKENS.primary_fill}" in stylesheet

    assert controller.auto_apply_button._qt.isDefault()
    assert controller.physical_action_buttons["physical_delete"]._qt.isCheckable()
    assert controller.az_chart.play_button._qt.isCheckable()
    assert controller.el_chart.play_button._qt.isCheckable()
    assert controller.dbf2d_az_button._qt.isCheckable()
    assert controller.dbf2d_el_button._qt.isCheckable()
    assert callable(controller.phys_canvas.grab_pointer)
    assert callable(controller.phys_canvas.release_pointer)

    cancelled_events = []
    callback_id = controller.phys_canvas.mpl_connect(
        "pointer_cancel_event", cancelled_events.append
    )
    controller.phys_canvas._captured_axis = controller.physical_ax
    try:
        controller.phys_canvas.eventFilter(
            controller.phys_canvas,
            QtCore.QEvent(QtCore.QEvent.Type.UngrabMouse),
        )
        assert len(cancelled_events) == 1
        assert cancelled_events[0].inaxes is controller.physical_ax
        assert controller.phys_canvas._captured_axis is None
    finally:
        controller.phys_canvas.mpl_disconnect(callback_id)

    original_delete_mode = controller.delete_mode
    try:
        controller.delete_mode = True
        controller._update_delete_button_state()
        delete_stylesheet = controller.physical_action_buttons[
            "physical_delete"
        ]._qt.styleSheet()
        assert TOKENS.danger_fill in delete_stylesheet
        assert TOKENS.danger in delete_stylesheet
    finally:
        controller.delete_mode = original_delete_mode
        controller._update_delete_button_state()


def test_callout_role_updates_do_not_grow_local_stylesheets(gui_session) -> None:
    from virtual_array.native_theme import mark_callout

    label = QtWidgets.QLabel("Quality")
    label.setStyleSheet("QLabel { color: black; }")
    lengths = []
    for _cycle in range(5):
        for role in ("neutral", "success", "warning", "danger"):
            mark_callout(label, role)
            lengths.append(len(label.styleSheet()))
    assert len(set(lengths[4:])) <= 4
    assert max(lengths) < 500
    label.deleteLater()
    process_events(gui_session.app, cycles=2)


def test_toolbar_selectors_and_evaluation_metrics_use_continuous_surfaces(
    gui_session,
) -> None:
    from virtual_array.gui import THEME

    controller = gui_session.controller
    process_events(gui_session.app, cycles=2)

    assert THEME["metric_bg"] == THEME["card_bg"]
    for radio in (
        controller.dbf_display_db_radio,
        controller.dbf_display_mag_radio,
    ):
        assert radio is not None
        stylesheet = radio._qt.styleSheet()
        assert f"background-color: {THEME['status_bar_bg']}" in stylesheet
        assert "background-color: transparent" not in stylesheet
        assert "border:" not in stylesheet
        assert radio.cget("style") == "Toolbar.TRadiobutton"
        assert (
            radio._qt.cursor().shape()
            == QtCore.Qt.CursorShape.PointingHandCursor
        )

    unselected_radio = next(
        radio._qt
        for radio in (
            controller.dbf_display_db_radio,
            controller.dbf_display_mag_radio,
        )
        if not radio._qt.isChecked()
    )
    option = QtWidgets.QStyleOptionButton()
    unselected_radio.initStyleOption(option)
    indicator = unselected_radio.style().subElementRect(
        QtWidgets.QStyle.SubElement.SE_RadioButtonIndicator,
        option,
        unselected_radio,
    )
    image = QtGui.QImage(
        unselected_radio.size(),
        QtGui.QImage.Format.Format_ARGB32_Premultiplied,
    )
    image.fill(QtGui.QColor(THEME["status_bar_bg"]))
    unselected_radio.render(image)
    visible_indicator_pixels = sum(
        1
        for y in range(indicator.top(), indicator.bottom() + 1)
        for x in range(indicator.left(), indicator.right() + 1)
        if image.pixelColor(x, y).lightness() < 235
    )
    assert visible_indicator_pixels >= 8

    metric_labels = (
        *controller.primary_name_labels.values(),
        *controller.primary_value_labels.values(),
        *controller.secondary_name_labels.values(),
        *controller.secondary_value_labels.values(),
    )
    assert metric_labels
    assert all(THEME["card_bg"] in label._qt.styleSheet() for label in metric_labels)


def test_escape_interrupts_captured_dbf_drags(gui_session) -> None:
    controller = gui_session.controller

    controller.dbf_drag_mode = "azimuth"
    assert controller.on_escape_key() == "break"
    assert controller.dbf_drag_mode is None

    controller.dbf2d_dragging = True
    assert controller.on_escape_key() == "break"
    assert controller.dbf2d_dragging is False


def test_workspace_tabs_support_keyboard_navigation(gui_session) -> None:
    controller = gui_session.controller
    tab_widget = controller.main_notebook._qt
    tab_bar = tab_widget.tabBar()
    original_index = tab_widget.currentIndex()

    try:
        tab_widget.setCurrentIndex(0)
        tab_bar.setFocus()
        QtTest.QTest.keyClick(
            tab_widget,
            QtCore.Qt.Key.Key_Tab,
            QtCore.Qt.KeyboardModifier.ControlModifier,
        )
        process_events(gui_session.app, cycles=4)
        assert tab_widget.currentIndex() == 1
        assert tab_bar.hasFocus()
    finally:
        tab_widget.setCurrentIndex(original_index)
        process_events(gui_session.app, cycles=3)


def test_performance_report_worker_runs_off_the_gui_thread(
    gui_session, monkeypatch: pytest.MonkeyPatch
) -> None:
    from virtual_array.performance_report_dialog import PerformanceReportDialog

    controller = gui_session.controller
    app = gui_session.app
    events: list[tuple[str, object, bool]] = []
    worker_thread_checks: list[bool] = []
    cancel_requests: list[bool] = []
    progress_canceled: list[bool] = []
    information_parents: list[QtWidgets.QWidget] = []
    application_exit_signals: list[str] = []
    on_about_to_quit = lambda: application_exit_signals.append("aboutToQuit")
    on_last_window_closed = lambda: application_exit_signals.append(
        "lastWindowClosed"
    )
    original_success = controller._on_performance_report_succeeded
    original_failure = controller._on_performance_report_failed
    original_progress = controller._on_performance_report_progress
    original_cancel = controller._cancel_performance_report_export

    app.aboutToQuit.connect(on_about_to_quit)
    app.lastWindowClosed.connect(on_last_window_closed)

    report_dialog = PerformanceReportDialog(
        gui_session.window,
        language="zh",
        initial_directory=Path.cwd(),
        azimuth_available=True,
        elevation_available=True,
    )
    report_dialog.open()
    process_events(app, cycles=4)

    def capture_information(parent, *_args, **_kwargs):
        information_parents.append(parent)
        return QtWidgets.QMessageBox.StandardButton.Ok

    monkeypatch.setattr(
        QtWidgets.QMessageBox,
        "information",
        capture_information,
    )

    def in_gui_thread() -> bool:
        # Do not cache QApplication.thread(): PySide can invalidate that wrapper
        # while short-lived QThread wrappers are deleted between exports.
        return QtCore.QThread.currentThread() is app.thread()

    def fake_generator(_snapshot, _options, progress_callback):
        worker_thread_checks.append(in_gui_thread())
        progress_callback(5, "start")
        progress_callback(100, "done")
        return SimpleNamespace(pdf_path=Path("report.pdf"), data_directory=None)

    def capture_progress(percent: int, message: str) -> None:
        events.append(
            (
                "progress",
                (percent, message),
                in_gui_thread(),
            )
        )
        original_progress(percent, message)

    def capture_success(artifacts) -> None:  # noqa: ANN001
        events.append(
            (
                "success",
                artifacts.pdf_path,
                in_gui_thread(),
            )
        )
        original_success(artifacts)

    controller._on_performance_report_progress = capture_progress
    controller._on_performance_report_succeeded = capture_success
    controller._on_performance_report_failed = lambda message: events.append(
        (
            "failure",
            message,
            in_gui_thread(),
        )
    )
    controller._cancel_performance_report_export = lambda: cancel_requests.append(
        in_gui_thread()
    )
    try:
        for _run_index in range(2):
            report_dialog.set_export_busy(True)
            controller._performance_export_parent = report_dialog
            assert not report_dialog.save_button.isEnabled()
            assert not report_dialog.angle_image_button.isEnabled()
            assert not report_dialog.cancel_button.isEnabled()

            controller._start_performance_report_export(
                fake_generator,
                object(),
                object(),
            )
            thread = controller._performance_report_thread
            worker = controller._performance_report_worker
            bridge = controller._performance_report_bridge
            progress = controller._performance_report_progress
            assert isinstance(thread, QtCore.QThread)
            assert worker is not None
            assert bridge is not None
            assert progress is not None
            assert bridge.thread() is app.thread()
            assert progress.parentWidget() is report_dialog
            assert (
                progress.windowModality()
                == QtCore.Qt.WindowModality.WindowModal
            )
            assert progress.minimumWidth() >= 480
            assert progress.minimumHeight() >= 160
            assert progress.property("workbenchRole") == "progress-dialog"
            progress_label = progress.findChild(QtWidgets.QLabel)
            assert progress_label is not None and progress_label.wordWrap()
            assert progress_label.objectName() == "performanceReportProgressLabel"
            assert progress_label.property("workbenchRole") == "progress-status"
            assert progress_label.alignment() & QtCore.Qt.AlignmentFlag.AlignCenter
            assert "0%" in progress_label.text()
            progress_bar = progress.findChild(
                QtWidgets.QProgressBar, "performanceReportProgressBar"
            )
            assert progress_bar is not None
            assert progress_bar.property("workbenchRole") == "report-progress"
            assert not progress_bar.isTextVisible()
            assert progress_bar.accessibleName()
            assert progress_bar.height() >= 12
            original_progress(65, "正在绘制逐帧 Hold: 方位")
            assert progress_bar.value() == 65
            assert progress_label.text() == "正在绘制逐帧 Hold: 方位  ·  65%"
            progress.canceled.connect(lambda: progress_canceled.append(True))

            loop = QtCore.QEventLoop()
            thread.finished.connect(loop.quit)
            watchdog = QtCore.QTimer()
            watchdog.setSingleShot(True)
            watchdog.timeout.connect(loop.quit)
            watchdog.start(3_000)
            loop.exec()
            finished_in_time = watchdog.isActive()
            watchdog.stop()
            process_events(app, cycles=8)
            assert finished_in_time, "report worker did not finish before timeout"
            assert controller._performance_report_thread is None
            assert controller._performance_report_worker is None
            assert controller._performance_report_bridge is None
            assert controller._performance_report_progress is None
            assert controller._performance_export_parent is None
            assert report_dialog.save_button.isEnabled()
            assert report_dialog.angle_image_button.isEnabled()
            assert report_dialog.cancel_button.isEnabled()
            assert report_dialog.isVisible()
            assert gui_session.window.isVisible()

        assert worker_thread_checks == [False, False]
        assert events == [
            ("progress", (5, "start"), True),
            ("progress", (100, "done"), True),
            ("success", Path("report.pdf"), True),
            ("progress", (5, "start"), True),
            ("progress", (100, "done"), True),
            ("success", Path("report.pdf"), True),
        ]
        assert cancel_requests == []
        assert progress_canceled == []
        assert information_parents == [report_dialog, report_dialog]
        assert application_exit_signals == []
    finally:
        app.aboutToQuit.disconnect(on_about_to_quit)
        app.lastWindowClosed.disconnect(on_last_window_closed)
        controller._on_performance_report_progress = original_progress
        controller._on_performance_report_succeeded = original_success
        controller._on_performance_report_failed = original_failure
        controller._cancel_performance_report_export = original_cancel
        progress = controller._performance_report_progress
        if progress is not None:
            progress.blockSignals(True)
            progress.close()
            controller._performance_report_progress = None
        controller._performance_export_parent = None
        report_dialog.set_export_busy(False)
        report_dialog.close()
        report_dialog.deleteLater()
        process_events(app, cycles=3)


def test_configuration_and_manual_dialogs_use_native_qt_controls(gui_session) -> None:
    controller = gui_session.controller
    dialog_specs = (
        (
            controller.open_dbf_dictionary_dialog,
            True,
            False,
            QtWidgets.QDialogButtonBox.StandardButton.Cancel,
        ),
        (
            controller.open_channel_patterns_dialog,
            True,
            False,
            QtWidgets.QDialogButtonBox.StandardButton.Close,
        ),
        (
            controller._show_user_manual_dialog,
            False,
            True,
            QtWidgets.QDialogButtonBox.StandardButton.Close,
        ),
    )

    for invocation, expects_table, expects_text_browser, close_button_kind in dialog_specs:
        dialog = _open_modeless_dialog(gui_session, invocation)
        closed = False
        try:
            assert dialog.windowTitle()
            assert dialog.property("workbenchRole") == "dialog-shell"
            assert dialog.width() <= gui_session.window.width()
            assert dialog.height() <= gui_session.window.height()
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
                if dialog.objectName() == "channelPatternsDialog":
                    source_panel = dialog.findChild(
                        QtWidgets.QWidget, "channelPatternSourcePanel"
                    )
                    table_panel = dialog.findChild(
                        QtWidgets.QWidget, "channelPatternTablePanel"
                    )
                    action_bar = dialog.findChild(
                        QtWidgets.QWidget, "channelPatternActionBar"
                    )
                    assert source_panel.property("workbenchRole") == "dialog-rail"
                    assert table_panel.property("workbenchRole") == "dialog-content"
                    assert action_bar.property("workbenchRole") == "dialog-footer"
                    for button in dialog.findChildren(QtWidgets.QAbstractButton):
                        if not button.isVisible() or not button.text():
                            continue
                        text_width = button.fontMetrics().horizontalAdvance(button.text())
                        assert text_width + 12 <= button.width(), button.text()
                elif dialog.objectName() == "dbfDictionaryDialog":
                    mode_panel = dialog.findChild(
                        QtWidgets.QWidget, "dbfModePanel"
                    )
                    custom_panel = dialog.findChild(
                        QtWidgets.QWidget, "dbfCustomImportPanel"
                    )
                    custom_scroll = dialog.findChild(
                        QtWidgets.QScrollArea, "dbfCustomImportScroll"
                    )
                    import_disclosure = dialog.findChild(
                        QtWidgets.QPushButton, "dbfImportDisclosure"
                    )
                    toolbar = dialog.findChild(QtWidgets.QWidget, "dbfPreviewToolbar")
                    az_button = dialog.findChild(
                        QtWidgets.QAbstractButton, "dbfPreviewAzButton"
                    )
                    el_button = dialog.findChild(
                        QtWidgets.QAbstractButton, "dbfPreviewElButton"
                    )
                    preview_table = dialog.findChild(
                        QtWidgets.QTableView, "dbfPreviewTable"
                    )
                    preview_panel = dialog.findChild(
                        QtWidgets.QWidget, "dbfPreviewPanel"
                    )
                    preview_header = dialog.findChild(
                        QtWidgets.QWidget, "dbfPreviewHeader"
                    )
                    action_bar = dialog.findChild(
                        QtWidgets.QWidget, "dbfDictionaryActionBar"
                    )
                    phase_reverse_toggle = dialog.findChild(
                        AppleSwitch, "dbfPhaseReverseToggle"
                    )
                    zero_calibrate_toggle = dialog.findChild(
                        AppleSwitch, "dbfZeroCalibrateToggle"
                    )
                    custom_mode = dialog.findChild(
                        QtWidgets.QRadioButton, "dbfMode_custom"
                    )
                    ideal_mode = dialog.findChild(
                        QtWidgets.QRadioButton, "dbfMode_ideal"
                    )
                    az_load_button = dialog.findChild(
                        QtWidgets.QPushButton, "dbfLoadAzButton"
                    )
                    az_clear_button = dialog.findChild(
                        QtWidgets.QPushButton, "dbfClearAzButton"
                    )
                    el_load_button = dialog.findChild(
                        QtWidgets.QPushButton, "dbfLoadElButton"
                    )
                    el_clear_button = dialog.findChild(
                        QtWidgets.QPushButton, "dbfClearElButton"
                    )
                    fit_columns_button = dialog.findChild(
                        QtWidgets.QPushButton, "dbfFitColumnsButton"
                    )
                    calibration_separator = dialog.findChild(
                        QtWidgets.QFrame, "dbfCalibrationSeparator"
                    )
                    button_box = button_boxes[0]
                    apply_button = button_box.button(
                        QtWidgets.QDialogButtonBox.StandardButton.Apply
                    )
                    assert all(
                        widget is not None
                        for widget in (
                            mode_panel,
                            custom_panel,
                            custom_scroll,
                            toolbar,
                            az_button,
                            el_button,
                            preview_table,
                            preview_panel,
                            preview_header,
                            action_bar,
                            phase_reverse_toggle,
                            zero_calibrate_toggle,
                            custom_mode,
                            ideal_mode,
                            az_load_button,
                            az_clear_button,
                            el_load_button,
                            el_clear_button,
                            fit_columns_button,
                            calibration_separator,
                            apply_button,
                        )
                    )
                    assert mode_panel.property("workbenchRole") == "dialog-rail"
                    assert custom_panel.property("workbenchRole") == "dialog-rail"
                    assert preview_panel.property("workbenchRole") == "dialog-content"
                    assert preview_header.property("workbenchRole") == "dialog-header"
                    assert action_bar.property("workbenchRole") == "dialog-footer"
                    for toggle in (phase_reverse_toggle, zero_calibrate_toggle):
                        assert isinstance(toggle, QtWidgets.QCheckBox)
                        assert not toggle.isTristate()
                    assert not custom_panel.isVisible()
                    assert not custom_scroll.isVisible()
                    assert import_disclosure is None
                    assert az_button.isChecked() and not el_button.isChecked()
                    custom_mode.click()
                    process_events(gui_session.app, cycles=3)
                    assert custom_panel.isVisible()
                    assert custom_scroll.isVisible()
                    assert not apply_button.isEnabled()
                    for button in (
                        az_load_button,
                        az_clear_button,
                        el_load_button,
                        el_clear_button,
                    ):
                        stylesheet = button.styleSheet()
                        assert f"#{button.objectName()} {{" in stylesheet
                        assert "border: 1px solid" in stylesheet
                    assert fit_columns_button.toolTip()
                    fit_columns_button.click()
                    process_events(gui_session.app, cycles=2)
                    header = preview_table.horizontalHeader()
                    for section in range(preview_table.model().columnCount()):
                        assert header.sectionResizeMode(section) == (
                            QtWidgets.QHeaderView.ResizeMode.Interactive
                        )
                    assert 68 <= preview_table.columnWidth(0) <= 86
                    for section in range(1, preview_table.model().columnCount()):
                        assert 64 <= preview_table.columnWidth(section) <= 96
                    dialog.resize(820, 540)
                    process_events(gui_session.app, cycles=4)
                    assert custom_scroll.horizontalScrollBar().maximum() == 0
                    assert custom_scroll.verticalScrollBar().maximum() > 0
                    assert custom_panel.height() >= custom_panel.minimumSizeHint().height()
                    assert calibration_separator.geometry().top() > max(
                        el_load_button.geometry().bottom(),
                        el_clear_button.geometry().bottom(),
                    )
                    dialog.resize(1240, 780)
                    process_events(gui_session.app, cycles=4)
                    assert custom_scroll.verticalScrollBar().maximum() == 0
                    ideal_mode.click()
                    process_events(gui_session.app, cycles=3)
                    assert not custom_panel.isVisible()
                    assert not custom_scroll.isVisible()
                    assert apply_button.isEnabled()
            if expects_text_browser:
                from virtual_array.user_manual import manual_chapters

                browsers = dialog.findChildren(QtWidgets.QTextBrowser)
                assert len(browsers) == 1
                assert browsers[0].toPlainText().strip()
                search = dialog.findChild(QtWidgets.QLineEdit, "manualSearch")
                assert search is not None
                assert search.placeholderText()
                assert search.isClearButtonEnabled()
                chapter_list = dialog.findChild(
                    QtWidgets.QListWidget, "manualChapterList"
                )
                assert chapter_list is not None
                assert chapter_list.count() == len(manual_chapters(controller.language))
                assert chapter_list.accessibleName()
                splitter = dialog.findChild(
                    QtWidgets.QSplitter, "manualContentSplitter"
                )
                assert splitter is not None
                assert "<h2" in browsers[0].toHtml().lower()
                header = dialog.findChild(QtWidgets.QWidget, "manualHeader")
                contents = dialog.findChild(
                    QtWidgets.QWidget, "manualContentsPanel"
                )
                assert header.property("workbenchRole") == "dialog-header"
                assert contents.property("workbenchRole") == "dialog-rail"
                assert browsers[0].property("workbenchRole") == "dialog-content"
                assert button_boxes[0].property("workbenchRole") == "dialog-footer"

            _close_with_standard_button(
                gui_session,
                dialog,
                close_button_kind,
            )
            closed = True
        finally:
            if not closed:
                try:
                    dialog.reject()
                except RuntimeError:
                    pass
                process_events(gui_session.app, cycles=3)


def test_manual_chapter_navigation_and_search(gui_session) -> None:
    controller = gui_session.controller
    original_language = controller.language
    controller.set_language("zh")
    dialog = _open_modeless_dialog(gui_session, controller._show_user_manual_dialog)
    closed = False
    try:
        chapter_list = dialog.findChild(QtWidgets.QListWidget, "manualChapterList")
        browser = dialog.findChild(QtWidgets.QTextBrowser, "manualBrowser")
        search = dialog.findChild(QtWidgets.QLineEdit, "manualSearch")
        result_count = dialog.findChild(QtWidgets.QLabel, "manualSearchResultCount")
        assert chapter_list is not None
        assert browser is not None
        assert search is not None
        assert result_count is not None
        assert chapter_list.count() == 12

        chapter_list.setCurrentRow(chapter_list.count() - 1)
        process_events(gui_session.app, cycles=3)
        assert chapter_list.currentItem().text() in browser.toPlainText()

        QtTest.QTest.keyClick(
            dialog,
            QtCore.Qt.Key.Key_F,
            QtCore.Qt.KeyboardModifier.ControlModifier,
        )
        process_events(gui_session.app, cycles=2)
        assert search.hasFocus()

        search.setText("Ctrl+Shift+Z")
        process_events(gui_session.app, cycles=3)
        visible_rows = [
            row
            for row in range(chapter_list.count())
            if not chapter_list.item(row).isHidden()
        ]
        assert visible_rows
        assert len(visible_rows) < chapter_list.count()
        assert result_count.text()

        QtTest.QTest.keyClick(search, QtCore.Qt.Key.Key_Return)
        process_events(gui_session.app, cycles=2)
        assert dialog.isVisible(), "Enter in manual search must not close the dialog"

        search.setText("__definitely_not_a_manual_term__")
        process_events(gui_session.app, cycles=2)
        assert chapter_list.currentRow() == -1
        assert "未找到" in browser.toPlainText()

        search.clear()
        process_events(gui_session.app, cycles=2)
        assert all(
            not chapter_list.item(row).isHidden()
            for row in range(chapter_list.count())
        )

        _close_with_standard_button(
            gui_session,
            dialog,
            QtWidgets.QDialogButtonBox.StandardButton.Close,
        )
        closed = True
    finally:
        controller.set_language(original_language)
        if not closed:
            try:
                dialog.reject()
            except RuntimeError:
                pass


def test_help_menu_chapter_action_opens_the_requested_section(gui_session) -> None:
    controller = gui_session.controller
    original_language = controller.language
    controller.set_language("zh")
    requested_key = "files_reports"
    action = controller.native_manual_chapter_actions[requested_key]
    dialog = _open_modeless_dialog(gui_session, action.trigger)
    closed = False
    try:
        chapter_list = dialog.findChild(QtWidgets.QListWidget, "manualChapterList")
        assert chapter_list is not None
        current = chapter_list.currentItem()
        assert current is not None
        assert current.data(QtCore.Qt.ItemDataRole.UserRole) == requested_key
        assert current.text() in dialog.findChild(
            QtWidgets.QTextBrowser, "manualBrowser"
        ).toPlainText()
        _close_with_standard_button(
            gui_session,
            dialog,
            QtWidgets.QDialogButtonBox.StandardButton.Close,
        )
        closed = True
    finally:
        controller.set_language(original_language)
        if not closed:
            try:
                dialog.reject()
            except RuntimeError:
                pass


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
            observation["size"] = (dialog.width(), dialog.height())
            observation["shell_role"] = dialog.property("workbenchRole")
            action_bar = dialog.findChild(
                QtWidgets.QWidget, "elementPatternActionBar"
            )
            observation["footer_role"] = (
                action_bar.property("workbenchRole") if action_bar is not None else None
            )
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
    assert observation.get("shell_role") == "dialog-shell"
    assert observation.get("footer_role") == "dialog-footer"
    assert observation.get("button_box_count", 0) >= 1
    assert observation.get("has_cancel") is True
    width, height = observation["size"]
    assert width <= gui_session.window.width()
    assert height <= gui_session.window.height()
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
        "en": ("Unavailable", "At boundary"),
        "ja": ("利用不可", "境界制限"),
    }
    expected_accessible = {
        "zh": ("工作区页面", "应用状态"),
        "en": ("Workspace pages", "Application status"),
        "ja": ("ワークスペースページ", "アプリケーション状態"),
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
            workspace_name, status_name = expected_accessible[language]
            assert controller.main_notebook._qt.tabBar().accessibleName() == workspace_name
            assert controller.native_status_bar.accessibleName() == status_name
            for overlay in (
                controller.az_chart.empty_overlay,
                controller.el_chart.empty_overlay,
                controller.dbf2d_empty_overlay,
            ):
                assert overlay is not None
                assert overlay.accessibleName()
            assert (
                controller.auto_apply_button._qt.accessibleName()
                == controller.auto_apply_button._qt.text()
            )
            assert (
                controller.az_chart.play_button._qt.accessibleName()
                == controller.az_chart.play_button._qt.text()
            )
            if language == "en":
                for label in (
                    controller.header_title_label._qt,
                    controller.header_subtitle_label._qt,
                ):
                    assert (
                        label.fontMetrics().horizontalAdvance(label.text())
                        <= label.width()
                    )
                assert controller.header_subtitle_label._qt.toolTip().startswith(
                    "Array layout"
                )
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
            assert overlay.action_button.isVisible()
            assert overlay.action_button.text()
            assert not chart.footer_widget._qt.isVisible()
            assert not chart.play_button._qt.isEnabled()

        navigator.select(2)
        process_events(gui_session.app, cycles=5)
        overlay_2d = controller.dbf2d_empty_overlay
        assert overlay_2d is not None and overlay_2d.isVisible()
        assert overlay_2d.title_label.text() == "当前阵列不具备完整 2D 测角能力"
        assert overlay_2d.body_label.text()
        assert overlay_2d.action_button.isVisible()
        assert not controller.dbf2d_controls_widget._qt.isVisible()
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
