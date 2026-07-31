from __future__ import annotations

import os
import re
from pathlib import Path

import pytest


os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

QtWidgets = pytest.importorskip("PySide6.QtWidgets")
QtCore = pytest.importorskip("PySide6.QtCore")
QtTest = pytest.importorskip("PySide6.QtTest")

from virtual_array.native_theme import application_stylesheet  # noqa: E402
from virtual_array.performance_report_dialog import PerformanceReportDialog  # noqa: E402
from virtual_array.qt_tk import AppleSwitch  # noqa: E402


@pytest.fixture(scope="module")
def qapp():
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    yield app


@pytest.fixture
def dialog(qapp, tmp_path: Path):
    del qapp
    widget = PerformanceReportDialog(
        None,
        language="zh",
        initial_directory=tmp_path,
        azimuth_available=True,
        elevation_available=True,
    )
    yield widget
    widget.set_export_busy(False)
    widget.close()
    widget.deleteLater()


def test_dialog_defaults_are_complete_and_do_not_write_files(
    dialog: PerformanceReportDialog, tmp_path: Path
) -> None:
    assert dialog.objectName() == "performanceReportDialog"
    assert dialog.property("workbenchRole") == "dialog-shell"
    output_path = Path(dialog.output_path_edit.text())
    assert output_path.parent == tmp_path
    assert re.fullmatch(
        r"mimo_performance_report_\d{8}_\d{6}\.pdf", output_path.name
    )
    assert not output_path.exists()

    assert dialog.title_edit.text() == "当前配置测角性能报告"
    assert (dialog.az_focus_start.value(), dialog.az_focus_stop.value()) == (-70, 70)
    assert (dialog.el_focus_start.value(), dialog.el_focus_stop.value()) == (-15, 15)
    assert (dialog.az_hold_start.value(), dialog.az_hold_stop.value()) == (-70, 70)
    assert (dialog.el_hold_start.value(), dialog.el_hold_stop.value()) == (-15, 15)
    assert dialog.az_hold_follows_focus.isChecked()
    assert dialog.el_hold_follows_focus.isChecked()
    assert dialog.az_hold_curve_step.value() == 1
    assert dialog.el_hold_curve_step.value() == 1
    assert not dialog.az_hold_start.isEnabled()
    assert not dialog.el_hold_start.isEnabled()

    assert "141" in dialog.az_hold_frame_count.text()
    assert "1°" in dialog.az_hold_frame_count.text()
    assert "31" in dialog.el_hold_frame_count.text()
    assert "0°" in dialog.findChild(
        QtWidgets.QLabel, "azOrthogonalPlaneNote"
    ).text()
    assert "0°" in dialog.findChild(
        QtWidgets.QLabel, "elOrthogonalPlaneNote"
    ).text()

    assert dialog.error_limit_spin.value() == pytest.approx(1.0)
    assert dialog.spectrum_floor_spin.value() == pytest.approx(-40.0)
    assert dialog.spectrum_floor_spin.isEnabled()
    assert dialog.include_spectrum_db_checkbox.isChecked()
    assert not dialog.include_spectrum_magnitude_checkbox.isChecked()
    assert dialog.include_raw_checkbox.isChecked()
    assert dialog.save_button.isEnabled()
    assert isinstance(dialog.angle_image_button, QtWidgets.QPushButton)
    assert dialog.angle_image_button.isEnabled()
    assert dialog.angle_image_button.property("fluentRole") != "quiet"
    spectrum_scale_label = dialog.findChild(
        QtWidgets.QLabel, "reportSpectrumScaleLabel"
    )
    assert spectrum_scale_label is not None
    assert "可多选" in spectrum_scale_label.text()
    assert "分别输出" in dialog.include_spectrum_db_checkbox.toolTip()
    assert dialog.export_kind == "report"

    with pytest.raises(AttributeError):
        setattr(dialog, "export_kind", "angle_image")


def test_range_spin_boxes_and_important_object_names_are_stable(
    dialog: PerformanceReportDialog,
) -> None:
    expected_spin_names = (
        "azFocusStart",
        "azFocusStop",
        "azHoldStart",
        "azHoldStop",
        "elFocusStart",
        "elFocusStop",
        "elHoldStart",
        "elHoldStop",
    )
    for object_name in expected_spin_names:
        spin = dialog.findChild(QtWidgets.QSpinBox, object_name)
        assert spin is not None
        assert (spin.minimum(), spin.maximum(), spin.singleStep()) == (-90, 90, 1)

    expected_names_and_types = {
        "reportOutputPath": QtWidgets.QLineEdit,
        "reportTitle": QtWidgets.QLineEdit,
        "reportBrowseButton": QtWidgets.QPushButton,
        "azHoldFollowsFocus": AppleSwitch,
        "elHoldFollowsFocus": AppleSwitch,
        "azHoldCurveStep": QtWidgets.QSpinBox,
        "elHoldCurveStep": QtWidgets.QSpinBox,
        "reportErrorLimitDeg": QtWidgets.QDoubleSpinBox,
        "reportSpectrumFloorDb": QtWidgets.QDoubleSpinBox,
        "reportIncludeSpectrumDb": AppleSwitch,
        "reportIncludeSpectrumMagnitude": AppleSwitch,
        "reportIncludeRawData": AppleSwitch,
        "reportValidationError": QtWidgets.QLabel,
        "performanceReportButtonBox": QtWidgets.QDialogButtonBox,
    }
    for object_name, widget_type in expected_names_and_types.items():
        assert dialog.findChild(widget_type, object_name) is not None

    switch_names = (
        "azHoldFollowsFocus",
        "elHoldFollowsFocus",
        "reportIncludeSpectrumDb",
        "reportIncludeSpectrumMagnitude",
        "reportIncludeRawData",
    )
    for object_name in switch_names:
        switch = dialog.findChild(AppleSwitch, object_name)
        assert isinstance(switch, QtWidgets.QCheckBox)
        assert not switch.isTristate()

    expected_roles = {
        "performanceReportRail": "dialog-rail",
        "performanceReportRailContent": "dialog-rail",
        "performanceReportContent": "dialog-content",
        "reportOutputGroup": "dialog-rail",
        "reportAxisTabs": "dialog-content",
        "reportPerformanceSettingsGroup": "dialog-rail",
        "azimuthReportGroup": "dialog-section",
        "elevationReportGroup": "dialog-section",
        "performanceReportButtonBox": "dialog-footer",
    }
    for object_name, role in expected_roles.items():
        widget = dialog.findChild(QtWidgets.QWidget, object_name)
        assert widget is not None
        assert widget.property("workbenchRole") == role

    for object_name in ("azHoldCurveStep", "elHoldCurveStep"):
        spin = dialog.findChild(QtWidgets.QSpinBox, object_name)
        assert spin is not None
        assert (spin.minimum(), spin.maximum(), spin.singleStep()) == (1, 180, 1)


@pytest.mark.parametrize("language", ("zh", "en", "ja"))
@pytest.mark.parametrize("dialog_size", ((920, 600), (820, 540)))
def test_compact_layout_balances_configuration_rail_and_axis_panel(
    qapp, tmp_path: Path, language: str, dialog_size: tuple[int, int]
) -> None:
    compact_dialog = PerformanceReportDialog(
        None,
        language=language,
        initial_directory=tmp_path,
        azimuth_available=True,
        elevation_available=True,
    )
    compact_dialog.setStyleSheet(application_stylesheet())
    compact_dialog.resize(*dialog_size)
    compact_dialog.show()
    qapp.processEvents()

    try:
        rail = compact_dialog.findChild(
            QtWidgets.QScrollArea, "performanceReportRail"
        )
        rail_content = compact_dialog.findChild(
            QtWidgets.QWidget, "performanceReportRailContent"
        )
        content = compact_dialog.findChild(
            QtWidgets.QWidget, "performanceReportContent"
        )
        output_group = compact_dialog.findChild(
            QtWidgets.QGroupBox, "reportOutputGroup"
        )
        settings_group = compact_dialog.findChild(
            QtWidgets.QGroupBox, "reportPerformanceSettingsGroup"
        )

        assert rail is not None
        assert rail_content is not None
        assert content is not None
        assert output_group is not None
        assert settings_group is not None
        assert compact_dialog.size() == QtCore.QSize(*dialog_size)
        assert rail.geometry().right() < content.geometry().left()
        assert output_group.parentWidget() is rail_content
        assert settings_group.parentWidget() is rail_content
        assert settings_group.geometry().top() > output_group.geometry().bottom()
        assert compact_dialog.title_edit.isVisibleTo(compact_dialog)
        assert compact_dialog.title_edit.width() >= 120
        assert output_group.contentsRect().contains(
            compact_dialog.title_edit.geometry()
        )
        QtTest.QTest.mouseClick(
            compact_dialog.title_edit,
            QtCore.Qt.MouseButton.LeftButton,
        )
        assert compact_dialog.title_edit.hasFocus()
        QtTest.QTest.keyClick(
            compact_dialog.title_edit,
            QtCore.Qt.Key.Key_A,
            QtCore.Qt.KeyboardModifier.ControlModifier,
        )
        QtTest.QTest.keyClicks(compact_dialog.title_edit, "Editable report title")
        assert compact_dialog.title_edit.text() == "Editable report title"
        assert rail.horizontalScrollBar().maximum() == 0
        assert compact_dialog.azimuth_page.horizontalScrollBar().maximum() == 0
        assert compact_dialog.button_box.geometry().bottom() <= compact_dialog.rect().bottom()
    finally:
        compact_dialog.close()
        compact_dialog.deleteLater()
        qapp.processEvents()


@pytest.mark.parametrize("language", ("zh", "en", "ja"))
def test_themed_angle_rows_keep_clear_vertical_separation(
    qapp, tmp_path: Path, language: str
) -> None:
    themed_dialog = PerformanceReportDialog(
        None,
        language=language,
        initial_directory=tmp_path,
        azimuth_available=True,
        elevation_available=True,
    )
    themed_dialog.setStyleSheet(application_stylesheet())
    themed_dialog.resize(780, 700)
    themed_dialog.show()
    qapp.processEvents()

    try:
        for tab_index, (axis, group, page) in enumerate(
            (
                ("az", themed_dialog.azimuth_group, themed_dialog.azimuth_page),
                ("el", themed_dialog.elevation_group, themed_dialog.elevation_page),
            )
        ):
            themed_dialog.axis_tabs.setCurrentIndex(tab_index)
            qapp.processEvents()
            grid = group.layout()
            assert isinstance(grid, QtWidgets.QGridLayout)
            assert grid.verticalSpacing() == 8
            assert group.height() >= group.minimumSizeHint().height()
            assert page.horizontalScrollBar().maximum() == 0

            focus = getattr(themed_dialog, f"{axis}_focus_start")
            hold = getattr(themed_dialog, f"{axis}_hold_start")
            gap = hold.geometry().top() - (focus.geometry().bottom() + 1)
            assert gap >= 6
            assert focus.height() >= 37
            assert hold.height() >= 37
    finally:
        themed_dialog.close()
        themed_dialog.deleteLater()
        qapp.processEvents()


def test_hold_range_follows_focus_until_user_requests_independent_range(
    dialog: PerformanceReportDialog,
) -> None:
    dialog.az_focus_start.setValue(-32)
    dialog.az_focus_stop.setValue(48)
    assert (dialog.az_hold_start.value(), dialog.az_hold_stop.value()) == (-32, 48)
    assert "81" in dialog.az_hold_frame_count.text()

    dialog.az_hold_follows_focus.setChecked(False)
    assert dialog.az_hold_start.isEnabled()
    assert dialog.az_hold_stop.isEnabled()
    dialog.az_hold_start.setValue(-10)
    dialog.az_hold_stop.setValue(12)
    dialog.az_focus_start.setValue(-25)
    assert (dialog.az_hold_start.value(), dialog.az_hold_stop.value()) == (-10, 12)
    assert "23" in dialog.az_hold_frame_count.text()

    dialog.az_hold_follows_focus.setChecked(True)
    assert not dialog.az_hold_start.isEnabled()
    assert (dialog.az_hold_start.value(), dialog.az_hold_stop.value()) == (-25, 48)


def test_hold_curve_interval_updates_plotted_curve_preview_and_options(
    dialog: PerformanceReportDialog,
) -> None:
    dialog.az_focus_start.setValue(-10)
    dialog.az_focus_stop.setValue(12)
    dialog.az_hold_curve_step.setValue(5)

    assert "范围内 23 帧" in dialog.az_hold_frame_count.text()
    assert "每 5°（5 帧）" in dialog.az_hold_frame_count.text()
    assert "共 6 条" in dialog.az_hold_frame_count.text()
    assert "起止角均保留" in dialog.az_hold_frame_count.text()

    dialog.el_hold_curve_step.setValue(4)
    options = dialog.options()
    assert options.azimuth_hold_stride_frames == 5
    assert options.elevation_hold_stride_frames == 4


def test_invalid_range_shows_inline_error_and_prevents_accept(
    dialog: PerformanceReportDialog, qapp,
) -> None:
    requests: list[str] = []
    dialog.export_requested.connect(requests.append)
    dialog.open()
    qapp.processEvents()

    dialog.az_focus_start.setValue(30)
    dialog.az_focus_stop.setValue(20)

    assert dialog.validation_label.isVisibleTo(dialog)
    assert "起始角不能大于终止角" in dialog.validation_label.text()
    dialog.save_button.click()
    assert requests == []
    assert dialog.isVisible()
    assert dialog.result() != QtWidgets.QDialog.DialogCode.Accepted

    dialog.az_focus_stop.setValue(40)
    assert not dialog.validation_label.isVisibleTo(dialog)
    dialog.save_button.click()
    qapp.processEvents()
    assert requests == ["report"]
    assert dialog.isVisible()
    assert dialog.result() != QtWidgets.QDialog.DialogCode.Accepted


def test_at_least_one_spectrum_vertical_scale_is_required(
    dialog: PerformanceReportDialog,
) -> None:
    dialog.include_spectrum_db_checkbox.setChecked(False)

    assert dialog.validation_label.isVisibleTo(dialog)
    assert "至少选择一种" in dialog.validation_label.text()
    assert "dB" in dialog.validation_label.text()
    assert "模值" in dialog.validation_label.text()
    assert not dialog.save_button.isEnabled()
    assert dialog.angle_image_button.isEnabled()
    assert not dialog.spectrum_floor_spin.isEnabled()

    dialog.include_spectrum_magnitude_checkbox.setChecked(True)
    assert not dialog.validation_label.isVisibleTo(dialog)
    assert dialog.save_button.isEnabled()

    options = dialog.options()
    assert options.include_spectrum_db is False
    assert options.include_spectrum_magnitude is True

    dialog.include_spectrum_db_checkbox.setChecked(True)
    assert dialog.spectrum_floor_spin.isEnabled()
    options = dialog.options()
    assert options.include_spectrum_db is True
    assert options.include_spectrum_magnitude is True


def test_axis_capability_disables_irrelevant_controls_and_report_action(
    qapp, tmp_path: Path
) -> None:
    azimuth_only = PerformanceReportDialog(
        None,
        language="en",
        initial_directory=tmp_path,
        azimuth_available=True,
        elevation_available=False,
    )
    try:
        assert azimuth_only.azimuth_group.isEnabled()
        assert not azimuth_only.elevation_group.isEnabled()
        assert azimuth_only.save_button.isEnabled()
        assert azimuth_only.angle_image_button.isEnabled()

        options = azimuth_only.options()
        assert options.azimuth_focus.start_deg == -70
        assert options.azimuth_focus.stop_deg == 70
        assert options.elevation_focus.start_deg == -15
        assert options.elevation_focus.stop_deg == 15
        assert options.elevation_hold.start_deg == -15
        assert options.elevation_hold.stop_deg == 15
        assert options.azimuth_hold_stride_frames == 1
        assert options.elevation_hold_stride_frames == 1
    finally:
        azimuth_only.close()
        azimuth_only.deleteLater()

    no_axis = PerformanceReportDialog(
        None,
        language="ja",
        initial_directory=tmp_path,
        azimuth_available=False,
        elevation_available=False,
    )
    try:
        no_axis.setStyleSheet(application_stylesheet())
        no_axis.resize(920, 600)
        no_axis.show()
        qapp.processEvents()

        assert not no_axis.azimuth_group.isEnabled()
        assert not no_axis.elevation_group.isEnabled()
        assert not no_axis.save_button.isEnabled()
        assert not no_axis.angle_image_button.isEnabled()
        rail = no_axis.findChild(QtWidgets.QScrollArea, "performanceReportRail")
        assert rail.horizontalScrollBar().maximum() == 0
        assert rail.verticalScrollBar().maximum() == 0
        assert no_axis.validation_label.parentWidget() is no_axis
        assert no_axis.validation_label.geometry().bottom() < (
            no_axis.button_box.geometry().top()
        )
    finally:
        no_axis.close()
        no_axis.deleteLater()


@pytest.mark.parametrize(
    (
        "language",
        "title_fragment",
        "save_text",
        "cancel_text",
        "magnitude_text",
        "hold_count_fragment",
    ),
    (
        ("zh", "性能报告", "输出报告", "取消", "模值", "范围内 141 帧"),
        (
            "en",
            "Performance Report",
            "Export report",
            "Cancel",
            "Magnitude",
            "141 frames in range",
        ),
        (
            "ja",
            "性能レポート",
            "レポートを出力",
            "キャンセル",
            "振幅値",
            "範囲内 141 フレーム",
        ),
    ),
)
def test_all_supported_languages_are_applied(
    qapp,
    tmp_path: Path,
    language: str,
    title_fragment: str,
    save_text: str,
    cancel_text: str,
    magnitude_text: str,
    hold_count_fragment: str,
) -> None:
    del qapp
    widget = PerformanceReportDialog(
        None,
        language=language,
        initial_directory=tmp_path,
        azimuth_available=True,
        elevation_available=True,
    )
    try:
        assert title_fragment in widget.windowTitle()
        assert widget.save_button.text() == save_text
        assert widget.cancel_button.text() == cancel_text
        assert "PNG" in widget.angle_image_button.text()
        assert widget.include_spectrum_db_checkbox.text() == "dB"
        assert widget.include_spectrum_magnitude_checkbox.text() == magnitude_text
        assert hold_count_fragment in widget.az_hold_frame_count.text()
        assert widget.options().language == language
    finally:
        widget.close()
        widget.deleteLater()


def test_browse_and_report_request_normalise_pdf_suffix_without_closing(
    qapp, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    selected_without_suffix = tmp_path / "custom-report"
    monkeypatch.setattr(
        QtWidgets.QFileDialog,
        "getSaveFileName",
        staticmethod(lambda *_args, **_kwargs: (str(selected_without_suffix), "")),
    )
    widget = PerformanceReportDialog(
        None,
        language="zh",
        initial_directory=tmp_path,
        azimuth_available=True,
        elevation_available=True,
    )
    try:
        requests: list[str] = []
        widget.export_requested.connect(requests.append)
        widget.open()
        qapp.processEvents()

        widget.browse_button.click()
        expected = selected_without_suffix.with_suffix(".pdf")
        assert Path(widget.output_path_edit.text()) == expected
        assert not expected.exists()

        widget.save_button.click()
        qapp.processEvents()
        assert requests == ["report"]
        assert widget.isVisible()
        assert widget.result() != QtWidgets.QDialog.DialogCode.Accepted
        options = widget.options()
        assert options.output_path == expected
        assert options.error_limit_deg == pytest.approx(1.0)
        assert options.spectrum_floor_db == pytest.approx(-40.0)
        assert options.include_spectrum_db is True
        assert options.include_spectrum_magnitude is False
        assert options.include_raw_data is True
        assert options.azimuth_hold_stride_frames == 1
        assert options.elevation_hold_stride_frames == 1
        assert not expected.exists()
    finally:
        widget.close()
        widget.deleteLater()


def test_report_then_angle_image_requests_keep_same_dialog_and_configuration(
    qapp,
    tmp_path: Path,
) -> None:
    report_path = tmp_path / "delivery" / "custom-report.pdf"
    expected_image_path = report_path.with_name("custom-report_angle_error.png")
    widget = PerformanceReportDialog(
        None,
        language="en",
        initial_directory=tmp_path,
        azimuth_available=True,
        elevation_available=False,
    )
    try:
        requests: list[str] = []
        widget.export_requested.connect(requests.append)
        widget.open()
        qapp.processEvents()

        original_identity = id(widget)
        widget.output_path_edit.setText(str(report_path))
        widget.title_edit.setText("Sequential export settings")
        widget.error_limit_spin.setValue(7.5)
        widget.az_focus_start.setValue(-44)
        widget.az_focus_stop.setValue(51)
        widget.az_hold_curve_step.setValue(5)

        assert widget.save_button.isEnabled()
        assert widget.angle_image_button.isEnabled()

        widget.save_button.click()
        qapp.processEvents()
        report_options = widget.options()

        assert requests == ["report"]
        assert id(widget) == original_identity
        assert widget.isVisible()
        assert widget.result() != QtWidgets.QDialog.DialogCode.Accepted
        assert report_options.output_path == report_path
        assert report_options.title == "Sequential export settings"
        assert report_options.error_limit_deg == pytest.approx(7.5)
        assert report_options.azimuth_focus.start_deg == -44
        assert report_options.azimuth_focus.stop_deg == 51
        assert report_options.azimuth_hold_stride_frames == 5

        # Model one completed worker cycle before requesting the second export.
        widget.set_export_busy(True)
        widget.set_export_busy(False)
        widget.angle_image_button.click()
        qapp.processEvents()

        assert requests == ["report", "angle_image"]
        assert id(widget) == original_identity
        assert widget.isVisible()
        assert widget.result() != QtWidgets.QDialog.DialogCode.Accepted
        assert widget.export_kind == "angle_image"
        options = widget.angle_error_image_options()
        assert options.output_path == expected_image_path
        assert options.output_path.parent == report_path.parent
        assert options.error_limit_deg == pytest.approx(7.5)
        assert options.language == "en"
        assert widget.options() == report_options
        assert not report_path.exists()
        assert not expected_image_path.exists()
    finally:
        widget.close()
        widget.deleteLater()


def test_busy_state_blocks_export_and_close_then_restores_valid_actions(
    dialog: PerformanceReportDialog, qapp,
) -> None:
    requests: list[str] = []
    dialog.export_requested.connect(requests.append)
    dialog.open()
    qapp.processEvents()

    # The report is invalid without a spectrum scale, while standalone PNG
    # export remains valid.  Restoration must preserve that distinction.
    dialog.include_spectrum_db_checkbox.setChecked(False)
    dialog.include_spectrum_magnitude_checkbox.setChecked(False)
    assert not dialog.save_button.isEnabled()
    assert dialog.angle_image_button.isEnabled()

    dialog.set_export_busy(True)
    assert not dialog.save_button.isEnabled()
    assert not dialog.angle_image_button.isEnabled()
    assert not dialog.cancel_button.isEnabled()

    dialog.save_button.click()
    dialog.angle_image_button.click()
    dialog.reject()
    assert dialog.close() is False
    QtTest.QTest.keyClick(dialog, QtCore.Qt.Key.Key_Escape)
    qapp.processEvents()

    assert requests == []
    assert dialog.isVisible()

    dialog.set_export_busy(False)
    assert not dialog.save_button.isEnabled()
    assert dialog.angle_image_button.isEnabled()
    assert dialog.cancel_button.isEnabled()

    dialog.cancel_button.click()
    qapp.processEvents()
    assert not dialog.isVisible()
