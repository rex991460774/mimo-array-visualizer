from __future__ import annotations

import os
import re
from pathlib import Path

import pytest


os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

QtWidgets = pytest.importorskip("PySide6.QtWidgets")

from virtual_array.performance_report_dialog import PerformanceReportDialog  # noqa: E402


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
    widget.close()
    widget.deleteLater()


def test_dialog_defaults_are_complete_and_do_not_write_files(
    dialog: PerformanceReportDialog, tmp_path: Path
) -> None:
    assert dialog.objectName() == "performanceReportDialog"
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
    assert not dialog.az_hold_start.isEnabled()
    assert not dialog.el_hold_start.isEnabled()

    assert "141" in dialog.az_hold_frame_count.text()
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
        "azHoldFollowsFocus": QtWidgets.QCheckBox,
        "elHoldFollowsFocus": QtWidgets.QCheckBox,
        "reportErrorLimitDeg": QtWidgets.QDoubleSpinBox,
        "reportSpectrumFloorDb": QtWidgets.QDoubleSpinBox,
        "reportIncludeSpectrumDb": QtWidgets.QCheckBox,
        "reportIncludeSpectrumMagnitude": QtWidgets.QCheckBox,
        "reportIncludeRawData": QtWidgets.QCheckBox,
        "reportValidationError": QtWidgets.QLabel,
        "performanceReportButtonBox": QtWidgets.QDialogButtonBox,
    }
    for object_name, widget_type in expected_names_and_types.items():
        assert dialog.findChild(widget_type, object_name) is not None


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


def test_invalid_range_shows_inline_error_and_prevents_accept(
    dialog: PerformanceReportDialog,
) -> None:
    dialog.az_focus_start.setValue(30)
    dialog.az_focus_stop.setValue(20)

    assert dialog.validation_label.isVisibleTo(dialog)
    assert "起始角不能大于终止角" in dialog.validation_label.text()
    dialog.save_button.click()
    assert dialog.result() != QtWidgets.QDialog.DialogCode.Accepted

    dialog.az_focus_stop.setValue(40)
    assert not dialog.validation_label.isVisibleTo(dialog)
    dialog.save_button.click()
    assert dialog.result() == QtWidgets.QDialog.DialogCode.Accepted


def test_at_least_one_spectrum_vertical_scale_is_required(
    dialog: PerformanceReportDialog,
) -> None:
    dialog.include_spectrum_db_checkbox.setChecked(False)

    assert dialog.validation_label.isVisibleTo(dialog)
    assert "至少选择一种" in dialog.validation_label.text()
    assert "dB" in dialog.validation_label.text()
    assert "模值" in dialog.validation_label.text()
    assert not dialog.save_button.isEnabled()
    assert not dialog.spectrum_floor_spin.isEnabled()

    dialog.include_spectrum_magnitude_checkbox.setChecked(True)
    assert not dialog.validation_label.isVisibleTo(dialog)
    assert dialog.save_button.isEnabled()

    options = dialog.options()
    assert options.include_spectrum_db is False
    assert options.include_spectrum_magnitude is True

    dialog.include_spectrum_db_checkbox.setChecked(True)
    assert dialog.spectrum_floor_spin.isEnabled()


def test_axis_capability_disables_irrelevant_controls_and_report_action(
    qapp, tmp_path: Path
) -> None:
    del qapp
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

        options = azimuth_only.options()
        assert options.azimuth_focus.start_deg == -70
        assert options.azimuth_focus.stop_deg == 70
        assert options.elevation_focus.start_deg == -15
        assert options.elevation_focus.stop_deg == 15
        assert options.elevation_hold.start_deg == -15
        assert options.elevation_hold.stop_deg == 15
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
        assert not no_axis.azimuth_group.isEnabled()
        assert not no_axis.elevation_group.isEnabled()
        assert not no_axis.save_button.isEnabled()
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
    ),
    (
        ("zh", "性能报告", "输出报告", "取消", "模值"),
        ("en", "Performance Report", "Export report", "Cancel", "Magnitude"),
        ("ja", "性能レポート", "レポートを出力", "キャンセル", "振幅値"),
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
        assert widget.include_spectrum_db_checkbox.text() == "dB"
        assert widget.include_spectrum_magnitude_checkbox.text() == magnitude_text
        assert widget.options().language == language
    finally:
        widget.close()
        widget.deleteLater()


def test_browse_and_accept_normalise_pdf_suffix_without_creating_file(
    qapp, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    del qapp
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
        widget.browse_button.click()
        expected = selected_without_suffix.with_suffix(".pdf")
        assert Path(widget.output_path_edit.text()) == expected
        assert not expected.exists()

        widget.accept()
        assert widget.result() == QtWidgets.QDialog.DialogCode.Accepted
        options = widget.options()
        assert options.output_path == expected
        assert options.error_limit_deg == pytest.approx(1.0)
        assert options.spectrum_floor_db == pytest.approx(-40.0)
        assert options.include_spectrum_db is True
        assert options.include_spectrum_magnitude is False
        assert options.include_raw_data is True
        assert not expected.exists()
    finally:
        widget.close()
        widget.deleteLater()
