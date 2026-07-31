from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

from PySide6 import QtCore, QtWidgets

from .native_theme import TOKENS, mark_primary, mark_workbench_role
from .performance_report import MAX_HOLD_STRIDE_FRAMES, hold_curve_frame_count
from .qt_tk import AppleSwitch

if TYPE_CHECKING:
    from .performance_report import AngleErrorImageOptions, PerformanceReportOptions


_SUPPORTED_LANGUAGES = {"zh", "en", "ja"}

_TEXT = {
    "dialog_title": {
        "zh": "输出当前配置性能报告",
        "en": "Export Current Configuration Performance Report",
        "ja": "現在構成の性能レポートを出力",
    },
    "output_group": {"zh": "报告文件", "en": "Report file", "ja": "レポートファイル"},
    "output_path": {"zh": "PDF 路径", "en": "PDF path", "ja": "PDF パス"},
    "browse": {"zh": "浏览…", "en": "Browse…", "ja": "参照…"},
    "pdf_filter": {
        "zh": "PDF 报告 (*.pdf);;所有文件 (*)",
        "en": "PDF report (*.pdf);;All files (*)",
        "ja": "PDF レポート (*.pdf);;すべてのファイル (*)",
    },
    "browse_title": {
        "zh": "选择性能报告保存位置",
        "en": "Choose performance report location",
        "ja": "性能レポートの保存先を選択",
    },
    "report_title": {"zh": "报告标题", "en": "Report title", "ja": "レポートタイトル"},
    "default_report_title": {
        "zh": "当前配置测角性能报告",
        "en": "Current Configuration Angle Performance Report",
        "ja": "現在構成の測角性能レポート",
    },
    "axis_group": {
        "zh": "{axis}测角范围{availability}",
        "en": "{axis} angle ranges{availability}",
        "ja": "{axis}測角範囲{availability}",
    },
    "unavailable_suffix": {
        "zh": "（当前配置不可用）",
        "en": " (unavailable for this configuration)",
        "ja": "（現在の構成では利用不可）",
    },
    "azimuth": {"zh": "方位", "en": "Azimuth", "ja": "方位"},
    "elevation": {"zh": "俯仰", "en": "Elevation", "ja": "仰角"},
    "focus_range": {
        "zh": "性能关注真角范围",
        "en": "Performance focus",
        "ja": "性能評価する真角度範囲",
    },
    "hold_range": {
        "zh": "角谱 Hold 真角范围",
        "en": "Spectrum Hold frames",
        "ja": "角度スペクトル Hold 真角度範囲",
    },
    "to": {"zh": "至", "en": "to", "ja": "～"},
    "follow_focus": {
        "zh": "Hold 跟随关注范围",
        "en": "Match focus range",
        "ja": "評価範囲に連動",
    },
    "hold_curve_stride": {
        "zh": "Hold 曲线间隔",
        "en": "Curve interval",
        "ja": "Hold 曲線間隔",
    },
    "hold_curve_stride_tooltip": {
        "zh": "当前真实角网格为 1°/帧。1° 表示全部帧；大于 1° 时按间隔绘制，并始终保留范围起止帧。",
        "en": "The current true-angle grid is 1 deg per frame. Use 1 deg for every frame; larger intervals retain both range endpoints.",
        "ja": "現在の真角度グリッドは1°/フレームです。1°は全フレームを描画し、それ以上では範囲両端を保持します。",
    },
    "frame_count": {
        "zh": "范围内 {range_count} 帧；每 {step}°（{step} 帧）绘制 1 条，共 {curve_count} 条；起止角均保留。",
        "en": "{range_count} frames in range; plot every {step} deg ({step} frames): {curve_count} curves; endpoints retained.",
        "ja": "範囲内 {range_count} フレーム；{step}°（{step} フレーム）ごとに描画し、計 {curve_count} 本；両端を保持。",
    },
    "azimuth_plane_note": {
        "zh": "方位 1D DBF 角谱使用主平面切面：俯仰真实角固定为 0°。",
        "en": "Azimuth 1D DBF uses the principal-plane cut with true elevation fixed at 0 deg.",
        "ja": "方位 1D DBF は主平面カットを使用し、真の仰角を 0° に固定します。",
    },
    "elevation_plane_note": {
        "zh": "俯仰 1D DBF 角谱使用主平面切面：方位真实角固定为 0°。",
        "en": "Elevation 1D DBF uses the principal-plane cut with true azimuth fixed at 0 deg.",
        "ja": "仰角 1D DBF は主平面カットを使用し、真の方位角を 0° に固定します。",
    },
    "settings_group": {
        "zh": "性能判据与数据",
        "en": "Criteria and data",
        "ja": "性能判定基準とデータ",
    },
    "error_limit": {
        "zh": "测角误差门限",
        "en": "Angle-error limit",
        "ja": "測角誤差しきい値",
    },
    "spectrum_floor": {
        "zh": "dB 图显示下限",
        "en": "dB display floor",
        "ja": "dB 角度スペクトル表示下限",
    },
    "spectrum_vertical_scale": {
        "zh": "角谱输出（可多选）",
        "en": "Spectrum pages (select one or both)",
        "ja": "角度スペクトル出力（複数選択可）",
    },
    "spectrum_scale_tooltip": {
        "zh": "可同时开启：报告将分别输出 dB 角谱页和归一化模值角谱页。",
        "en": "Both may be enabled; the report then adds separate dB and normalized-magnitude spectrum pages.",
        "ja": "両方を有効にすると、dB角度スペクトルと正規化振幅スペクトルを別ページで出力します。",
    },
    "spectrum_db": {
        "zh": "dB",
        "en": "dB",
        "ja": "dB",
    },
    "spectrum_magnitude": {
        "zh": "模值",
        "en": "Magnitude",
        "ja": "振幅値",
    },
    "include_raw": {
        "zh": "导出 CSV/JSON 数据",
        "en": "CSV/JSON data",
        "ja": "CSV/JSON データ",
    },
    "criteria_note": {
        "zh": "关注范围用于性能统计；Hold 范围与曲线间隔控制叠加图密度。Max-Hold 包络及 CSV/JSON 数据仍使用范围内全部帧。",
        "en": "The focus range drives performance metrics; the Hold range and curve interval control overlay density. Max-hold and CSV/JSON data still use every in-range frame.",
        "ja": "評価範囲は性能統計に使用し、Hold範囲と曲線間隔は重ね合わせ密度を制御します。Max-HoldとCSV/JSONは範囲内全フレームを使用します。",
    },
    "save_angle_image": {
        "zh": "仅输出测角误差 PNG",
        "en": "Export Angle-error PNG Only",
        "ja": "測角誤差 PNG のみ出力",
    },
    "save_angle_image_tooltip": {
        "zh": "使用当前误差门限，保存到 PDF 路径所在目录，文件名追加 _angle_error。",
        "en": "Use the current error limit and save beside the PDF path with _angle_error appended.",
        "ja": "現在の誤差しきい値を使用し、PDF パスと同じフォルダーへ _angle_error を付けて保存します。",
    },
    "validation_path": {
        "zh": "请选择 PDF 报告的输出路径。",
        "en": "Choose an output path for the PDF report.",
        "ja": "PDF レポートの出力先を選択してください。",
    },
    "validation_range": {
        "zh": "{axis}的{kind}起始角不能大于终止角。",
        "en": "The {axis} {kind} start angle must not exceed its stop angle.",
        "ja": "{axis}の{kind}開始角度は終了角度以下にしてください。",
    },
    "focus_kind": {"zh": "关注范围", "en": "focus range", "ja": "評価範囲"},
    "hold_kind": {"zh": "Hold 范围", "en": "Hold range", "ja": "Hold 範囲"},
    "validation_no_axis": {
        "zh": "当前配置不具备方位或俯仰测角能力，无法生成性能报告。",
        "en": "This configuration has no azimuth or elevation angle capability.",
        "ja": "現在の構成には方位・仰角の測角能力がないため、レポートを生成できません。",
    },
    "validation_spectrum_scale": {
        "zh": "角谱纵坐标至少选择一种：dB 或模值。",
        "en": "Select at least one spectrum vertical scale: dB or magnitude.",
        "ja": "角度スペクトルの縦軸を少なくとも 1 つ選択してください：dB または振幅値。",
    },
    "save": {"zh": "输出报告", "en": "Export report", "ja": "レポートを出力"},
    "cancel": {"zh": "取消", "en": "Cancel", "ja": "キャンセル"},
}


def _text(key: str, language: str, **values: Any) -> str:
    translations = _TEXT[key]
    template = translations.get(language, translations["zh"])
    return template.format(**values)


class PerformanceReportDialog(QtWidgets.QDialog):
    """Collect performance-report settings without performing any file I/O."""

    export_requested = QtCore.Signal(str)

    def __init__(
        self,
        parent: QtWidgets.QWidget | None,
        *,
        language: str,
        initial_directory: Path,
        azimuth_available: bool,
        elevation_available: bool,
        initial_error_limit_deg: float = 1.0,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("performanceReportDialog")
        mark_workbench_role(self, "dialog-shell")

        self.language = language if language in _SUPPORTED_LANGUAGES else "zh"
        self._azimuth_available = bool(azimuth_available)
        self._elevation_available = bool(elevation_available)
        self._initial_directory = Path(initial_directory).expanduser()
        try:
            parsed_error_limit = float(initial_error_limit_deg)
        except (TypeError, ValueError):
            parsed_error_limit = 1.0
        if not 0.1 <= parsed_error_limit <= 30.0:
            parsed_error_limit = 1.0
        self._initial_error_limit_deg = parsed_error_limit
        self._selected_export_kind = "report"
        self._export_busy = False

        self.setWindowTitle(_text("dialog_title", self.language))
        self.setModal(True)
        self.setMinimumWidth(820)

        self._build_ui()
        self._connect_signals()
        self._sync_hold_range("az")
        self._sync_hold_range("el")
        self._update_frame_count("az")
        self._update_frame_count("el")
        self._refresh_validation()

    def _build_ui(self) -> None:
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 12)
        layout.setSpacing(10)

        workspace = QtWidgets.QWidget(self)
        workspace.setObjectName("performanceReportWorkspace")
        workspace_layout = QtWidgets.QGridLayout(workspace)
        workspace_layout.setContentsMargins(0, 0, 0, 0)
        workspace_layout.setHorizontalSpacing(16)
        workspace_layout.setVerticalSpacing(0)
        workspace_layout.setColumnStretch(1, 1)

        rail = QtWidgets.QScrollArea(workspace)
        rail.setObjectName("performanceReportRail")
        mark_workbench_role(rail, "dialog-rail")
        rail.setFrameShape(QtWidgets.QFrame.Shape.NoFrame)
        rail.setWidgetResizable(True)
        rail.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        rail.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        rail.viewport().setAutoFillBackground(False)
        rail_width = 340
        rail.setMinimumWidth(rail_width)
        rail.setMaximumWidth(360)

        rail_content = QtWidgets.QWidget(rail)
        rail_content.setObjectName("performanceReportRailContent")
        mark_workbench_role(rail_content, "dialog-rail")
        rail_layout = QtWidgets.QVBoxLayout(rail_content)
        rail_layout.setContentsMargins(0, 0, 0, 0)
        rail_layout.setSpacing(8)
        rail.setWidget(rail_content)

        content_panel = QtWidgets.QWidget(workspace)
        content_panel.setObjectName("performanceReportContent")
        mark_workbench_role(content_panel, "dialog-content")
        content_layout = QtWidgets.QVBoxLayout(content_panel)
        content_layout.setContentsMargins(12, 10, 12, 10)
        content_layout.setSpacing(10)

        workspace_layout.addWidget(rail, 0, 0)
        workspace_layout.addWidget(content_panel, 0, 1)
        layout.addWidget(workspace, 1)

        output_group = QtWidgets.QGroupBox(
            _text("output_group", self.language), rail_content
        )
        output_group.setObjectName("reportOutputGroup")
        mark_workbench_role(output_group, "dialog-rail")
        output_layout = QtWidgets.QFormLayout(output_group)
        output_layout.setFieldGrowthPolicy(
            QtWidgets.QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow
        )
        output_layout.setHorizontalSpacing(12)
        output_layout.setVerticalSpacing(6)
        output_layout.setRowWrapPolicy(QtWidgets.QFormLayout.RowWrapPolicy.WrapLongRows)

        output_row = QtWidgets.QWidget(output_group)
        output_row_layout = QtWidgets.QHBoxLayout(output_row)
        output_row_layout.setContentsMargins(0, 0, 0, 0)
        output_row_layout.setSpacing(8)
        self.output_path_edit = QtWidgets.QLineEdit(
            str(self._initial_directory / self._default_filename()), output_row
        )
        self.output_path_edit.setObjectName("reportOutputPath")
        self.output_path_edit.setClearButtonEnabled(True)
        self.output_path_edit.setCursorPosition(0)
        self.browse_button = QtWidgets.QPushButton(_text("browse", self.language), output_row)
        self.browse_button.setObjectName("reportBrowseButton")
        output_row_layout.addWidget(self.output_path_edit, 1)
        output_row_layout.addWidget(self.browse_button)
        # Let the row shrink to its safe minimum before QFormLayout decides to
        # wrap it. This preserves the compact side-by-side form at 340 px while
        # long paths remain horizontally scrollable inside the line edit.
        output_row.setSizePolicy(
            QtWidgets.QSizePolicy.Policy.Ignored,
            QtWidgets.QSizePolicy.Policy.Preferred,
        )

        path_label = QtWidgets.QLabel(_text("output_path", self.language), output_group)
        path_label.setBuddy(self.output_path_edit)
        output_layout.addRow(path_label, output_row)

        self.title_edit = QtWidgets.QLineEdit(
            _text("default_report_title", self.language), output_group
        )
        self.title_edit.setObjectName("reportTitle")
        self.title_edit.setMaxLength(100)
        self.title_edit.setCursorPosition(0)
        self.title_edit.setSizePolicy(
            QtWidgets.QSizePolicy.Policy.Expanding,
            QtWidgets.QSizePolicy.Policy.Fixed,
        )
        self.title_edit.setMinimumWidth(120)
        title_label = QtWidgets.QLabel(_text("report_title", self.language), output_group)
        title_label.setBuddy(self.title_edit)
        output_layout.addRow(title_label, self.title_edit)
        rail_layout.addWidget(output_group)

        self.azimuth_group = self._build_axis_group(
            axis="az",
            available=self._azimuth_available,
            default_start=-70,
            default_stop=70,
        )
        self.elevation_group = self._build_axis_group(
            axis="el",
            available=self._elevation_available,
            default_start=-15,
            default_stop=15,
        )
        self.axis_tabs = QtWidgets.QTabWidget(content_panel)
        self.axis_tabs.setObjectName("reportAxisTabs")
        mark_workbench_role(self.axis_tabs, "dialog-content")
        self.axis_tabs.setSizePolicy(
            QtWidgets.QSizePolicy.Policy.Expanding,
            QtWidgets.QSizePolicy.Policy.Expanding,
        )
        self.axis_tabs.setStyleSheet(
            "QTabWidget#reportAxisTabs::pane { border: 0; background: transparent; }"
        )
        self.azimuth_page = self._axis_scroll_page("az", self.azimuth_group)
        self.elevation_page = self._axis_scroll_page("el", self.elevation_group)
        azimuth_index = self.axis_tabs.addTab(
            self.azimuth_page, _text("azimuth", self.language)
        )
        elevation_index = self.axis_tabs.addTab(
            self.elevation_page, _text("elevation", self.language)
        )
        self.axis_tabs.setTabEnabled(azimuth_index, self._azimuth_available)
        self.axis_tabs.setTabEnabled(elevation_index, self._elevation_available)
        if not self._azimuth_available and self._elevation_available:
            self.axis_tabs.setCurrentIndex(elevation_index)
        content_layout.addWidget(self.axis_tabs, 1)

        settings_group = QtWidgets.QGroupBox(
            _text("settings_group", self.language), rail_content
        )
        settings_group.setObjectName("reportPerformanceSettingsGroup")
        mark_workbench_role(settings_group, "dialog-rail")
        settings_layout = QtWidgets.QFormLayout(settings_group)
        settings_layout.setHorizontalSpacing(12)
        settings_layout.setVerticalSpacing(6)
        settings_layout.setFieldGrowthPolicy(
            QtWidgets.QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow
        )
        settings_layout.setRowWrapPolicy(
            QtWidgets.QFormLayout.RowWrapPolicy.WrapAllRows
        )

        self.error_limit_spin = QtWidgets.QDoubleSpinBox(settings_group)
        self.error_limit_spin.setObjectName("reportErrorLimitDeg")
        self.error_limit_spin.setRange(0.1, 30.0)
        self.error_limit_spin.setDecimals(1)
        self.error_limit_spin.setSingleStep(0.1)
        self.error_limit_spin.setSuffix("°")
        self.error_limit_spin.setValue(self._initial_error_limit_deg)
        self.error_limit_spin.setMaximumWidth(132)
        settings_layout.addRow(_text("error_limit", self.language), self.error_limit_spin)

        self.spectrum_floor_spin = QtWidgets.QDoubleSpinBox(settings_group)
        self.spectrum_floor_spin.setObjectName("reportSpectrumFloorDb")
        self.spectrum_floor_spin.setRange(-120.0, -10.0)
        self.spectrum_floor_spin.setDecimals(1)
        self.spectrum_floor_spin.setSingleStep(5.0)
        self.spectrum_floor_spin.setSuffix(" dB")
        self.spectrum_floor_spin.setValue(-40.0)
        self.spectrum_floor_spin.setMaximumWidth(132)
        settings_layout.addRow(_text("spectrum_floor", self.language), self.spectrum_floor_spin)

        spectrum_scale_row = QtWidgets.QWidget(settings_group)
        spectrum_scale_layout = QtWidgets.QHBoxLayout(spectrum_scale_row)
        spectrum_scale_layout.setContentsMargins(0, 0, 0, 0)
        spectrum_scale_layout.setSpacing(16)
        self.include_spectrum_db_checkbox = AppleSwitch(
            _text("spectrum_db", self.language), spectrum_scale_row
        )
        self.include_spectrum_db_checkbox.setObjectName("reportIncludeSpectrumDb")
        self.include_spectrum_db_checkbox.setChecked(True)
        self.include_spectrum_magnitude_checkbox = AppleSwitch(
            _text("spectrum_magnitude", self.language), spectrum_scale_row
        )
        self.include_spectrum_magnitude_checkbox.setObjectName(
            "reportIncludeSpectrumMagnitude"
        )
        self.include_spectrum_magnitude_checkbox.setChecked(False)
        spectrum_scale_tooltip = _text("spectrum_scale_tooltip", self.language)
        self.include_spectrum_db_checkbox.setToolTip(spectrum_scale_tooltip)
        self.include_spectrum_magnitude_checkbox.setToolTip(spectrum_scale_tooltip)
        spectrum_scale_row.setToolTip(spectrum_scale_tooltip)
        spectrum_scale_layout.addWidget(self.include_spectrum_db_checkbox)
        spectrum_scale_layout.addWidget(self.include_spectrum_magnitude_checkbox)
        spectrum_scale_layout.addStretch(1)
        spectrum_scale_label = QtWidgets.QLabel(
            _text("spectrum_vertical_scale", self.language), settings_group
        )
        spectrum_scale_label.setObjectName("reportSpectrumScaleLabel")
        spectrum_scale_label.setWordWrap(True)
        spectrum_scale_label.setToolTip(spectrum_scale_tooltip)
        settings_layout.addRow(spectrum_scale_label, spectrum_scale_row)

        self.include_raw_checkbox = AppleSwitch(
            _text("include_raw", self.language), settings_group
        )
        self.include_raw_checkbox.setObjectName("reportIncludeRawData")
        self.include_raw_checkbox.setChecked(True)
        settings_layout.addRow(self.include_raw_checkbox)

        criteria_note = QtWidgets.QLabel(_text("criteria_note", self.language), settings_group)
        criteria_note.setObjectName("reportCriteriaNote")
        criteria_note.setWordWrap(True)
        criteria_note.setMinimumWidth(0)
        criteria_note.setSizePolicy(
            QtWidgets.QSizePolicy.Policy.Ignored,
            QtWidgets.QSizePolicy.Policy.Preferred,
        )
        criteria_note.setProperty("fluentRole", "caption")
        settings_layout.addRow(criteria_note)
        rail_layout.addWidget(settings_group)

        # Validation is a dialog-wide state, so keep it outside the scroll rail.
        # This prevents long localized messages from being half-clipped at the
        # bottom of compact windows while leaving the configuration rail usable.
        self.validation_label = QtWidgets.QLabel(self)
        self.validation_label.setObjectName("reportValidationError")
        self.validation_label.setWordWrap(True)
        self.validation_label.setStyleSheet(f"color: {TOKENS.danger};")
        rail_layout.addStretch(1)

        self.button_box = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.StandardButton.Save
            | QtWidgets.QDialogButtonBox.StandardButton.Cancel,
            parent=self,
        )
        self.button_box.setObjectName("performanceReportButtonBox")
        mark_workbench_role(self.button_box, "dialog-footer")
        self.save_button = self.button_box.button(
            QtWidgets.QDialogButtonBox.StandardButton.Save
        )
        self.cancel_button = self.button_box.button(
            QtWidgets.QDialogButtonBox.StandardButton.Cancel
        )
        self.angle_image_button = self.button_box.addButton(
            _text("save_angle_image", self.language),
            QtWidgets.QDialogButtonBox.ButtonRole.ActionRole,
        )
        self.save_button.setObjectName("reportSaveButton")
        self.cancel_button.setObjectName("reportCancelButton")
        self.angle_image_button.setObjectName("reportAngleErrorImageButton")
        self.save_button.setText(_text("save", self.language))
        self.cancel_button.setText(_text("cancel", self.language))
        self.angle_image_button.setToolTip(
            _text("save_angle_image_tooltip", self.language)
        )
        mark_primary(self.save_button)
        axis_available = self._azimuth_available or self._elevation_available
        self.save_button.setEnabled(axis_available)
        self.angle_image_button.setEnabled(axis_available)
        layout.addWidget(self.validation_label)
        layout.addWidget(self.button_box)

    def _build_axis_group(
        self,
        *,
        axis: str,
        available: bool,
        default_start: int,
        default_stop: int,
    ) -> QtWidgets.QGroupBox:
        long_name = _text("azimuth" if axis == "az" else "elevation", self.language)
        availability = "" if available else _text("unavailable_suffix", self.language)
        group = QtWidgets.QGroupBox(
            _text(
                "axis_group",
                self.language,
                axis=long_name,
                availability=availability,
            ),
            self,
        )
        group.setObjectName(
            "azimuthReportGroup" if axis == "az" else "elevationReportGroup"
        )
        mark_workbench_role(group, "dialog-section")
        grid = QtWidgets.QGridLayout(group)
        grid.setSizeConstraint(QtWidgets.QLayout.SizeConstraint.SetMinimumSize)
        grid.setHorizontalSpacing(10)
        grid.setVerticalSpacing(8)
        grid.setColumnStretch(3, 1)
        grid.setRowStretch(7, 1)

        focus_start = self._angle_spin(f"{axis}FocusStart", default_start, group)
        focus_stop = self._angle_spin(f"{axis}FocusStop", default_stop, group)
        hold_start = self._angle_spin(f"{axis}HoldStart", default_start, group)
        hold_stop = self._angle_spin(f"{axis}HoldStop", default_stop, group)

        focus_label = QtWidgets.QLabel(_text("focus_range", self.language), group)
        focus_label.setBuddy(focus_start)
        hold_label = QtWidgets.QLabel(_text("hold_range", self.language), group)
        hold_label.setBuddy(hold_start)
        grid.addWidget(focus_label, 0, 0, 1, 4)
        grid.addWidget(focus_start, 1, 0)
        grid.addWidget(QtWidgets.QLabel(_text("to", self.language), group), 1, 1)
        grid.addWidget(focus_stop, 1, 2)
        grid.addWidget(hold_label, 2, 0, 1, 4)
        grid.addWidget(hold_start, 3, 0)
        grid.addWidget(QtWidgets.QLabel(_text("to", self.language), group), 3, 1)
        grid.addWidget(hold_stop, 3, 2)

        hold_controls = QtWidgets.QWidget(group)
        hold_controls.setObjectName(f"{axis}HoldControls")
        hold_controls_layout = QtWidgets.QVBoxLayout(hold_controls)
        hold_controls_layout.setContentsMargins(0, 0, 0, 0)
        hold_controls_layout.setSpacing(8)

        follow = AppleSwitch(
            _text("follow_focus", self.language), hold_controls
        )
        follow.setObjectName(f"{axis}HoldFollowsFocus")
        follow.setChecked(True)

        curve_stride_row = QtWidgets.QWidget(hold_controls)
        curve_stride_row_layout = QtWidgets.QHBoxLayout(curve_stride_row)
        curve_stride_row_layout.setContentsMargins(0, 0, 0, 0)
        curve_stride_row_layout.setSpacing(10)

        curve_stride = QtWidgets.QSpinBox(curve_stride_row)
        curve_stride.setObjectName(f"{axis}HoldCurveStep")
        curve_stride.setRange(1, MAX_HOLD_STRIDE_FRAMES)
        curve_stride.setSingleStep(1)
        curve_stride.setSuffix("°")
        curve_stride.setValue(1)
        curve_stride.setAlignment(QtCore.Qt.AlignmentFlag.AlignRight)
        curve_stride.setMaximumWidth(120)
        curve_stride.setToolTip(
            _text("hold_curve_stride_tooltip", self.language)
        )
        curve_stride_label = QtWidgets.QLabel(
            _text("hold_curve_stride", self.language), curve_stride_row
        )
        curve_stride_label.setBuddy(curve_stride)
        hold_controls_layout.addWidget(follow)
        curve_stride_row_layout.addWidget(curve_stride_label)
        curve_stride_row_layout.addWidget(curve_stride)
        curve_stride_row_layout.addStretch(1)
        hold_controls_layout.addWidget(curve_stride_row)
        grid.addWidget(hold_controls, 4, 0, 1, 4)

        frame_count = QtWidgets.QLabel(group)
        frame_count.setObjectName(f"{axis}HoldFrameCount")
        frame_count.setProperty("fluentRole", "caption")
        frame_count.setWordWrap(True)
        grid.addWidget(frame_count, 5, 0, 1, 4)

        note_key = "azimuth_plane_note" if axis == "az" else "elevation_plane_note"
        plane_note = QtWidgets.QLabel(_text(note_key, self.language), group)
        plane_note.setObjectName(f"{axis}OrthogonalPlaneNote")
        plane_note.setWordWrap(True)
        plane_note.setProperty("fluentRole", "caption")
        grid.addWidget(plane_note, 6, 0, 1, 4)

        setattr(self, f"{axis}_focus_start", focus_start)
        setattr(self, f"{axis}_focus_stop", focus_stop)
        setattr(self, f"{axis}_hold_start", hold_start)
        setattr(self, f"{axis}_hold_stop", hold_stop)
        setattr(self, f"{axis}_hold_follows_focus", follow)
        setattr(self, f"{axis}_hold_curve_step", curve_stride)
        setattr(self, f"{axis}_hold_frame_count", frame_count)

        hold_start.setEnabled(False)
        hold_stop.setEnabled(False)
        group.setEnabled(available)
        return group

    def _axis_scroll_page(
        self, axis: str, group: QtWidgets.QGroupBox
    ) -> QtWidgets.QScrollArea:
        """Keep range controls intact when a short screen constrains the dialog."""

        page = QtWidgets.QScrollArea(self)
        page.setObjectName(f"{axis}ReportScrollArea")
        mark_workbench_role(page, "dialog-content")
        page.setFrameShape(QtWidgets.QFrame.Shape.NoFrame)
        page.setWidgetResizable(True)
        page.setHorizontalScrollBarPolicy(
            QtCore.Qt.ScrollBarPolicy.ScrollBarAsNeeded
        )
        page.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        page.viewport().setAutoFillBackground(False)
        page.setStyleSheet(
            f"QScrollArea#{page.objectName()} {{ border: 0; background: transparent; }}"
        )
        page.setWidget(group)
        return page

    @staticmethod
    def _angle_spin(
        object_name: str, value: int, parent: QtWidgets.QWidget
    ) -> QtWidgets.QSpinBox:
        spin = QtWidgets.QSpinBox(parent)
        spin.setObjectName(object_name)
        spin.setRange(-90, 90)
        spin.setSingleStep(1)
        spin.setSuffix("°")
        spin.setValue(value)
        spin.setAlignment(QtCore.Qt.AlignmentFlag.AlignRight)
        return spin

    def _connect_signals(self) -> None:
        self.browse_button.clicked.connect(self._browse_output_path)
        self.output_path_edit.textChanged.connect(self._refresh_validation)
        self.include_spectrum_db_checkbox.toggled.connect(self._spectrum_db_toggled)
        self.include_spectrum_magnitude_checkbox.toggled.connect(
            self._refresh_validation
        )
        self.button_box.accepted.connect(self._request_report_export)
        self.button_box.rejected.connect(self.reject)
        self.angle_image_button.clicked.connect(self._request_angle_image_export)

        for axis in ("az", "el"):
            focus_start = getattr(self, f"{axis}_focus_start")
            focus_stop = getattr(self, f"{axis}_focus_stop")
            hold_start = getattr(self, f"{axis}_hold_start")
            hold_stop = getattr(self, f"{axis}_hold_stop")
            follow = getattr(self, f"{axis}_hold_follows_focus")
            curve_stride = getattr(self, f"{axis}_hold_curve_step")

            focus_start.valueChanged.connect(
                lambda _value, current_axis=axis: self._focus_range_changed(current_axis)
            )
            focus_stop.valueChanged.connect(
                lambda _value, current_axis=axis: self._focus_range_changed(current_axis)
            )
            hold_start.valueChanged.connect(
                lambda _value, current_axis=axis: self._hold_range_changed(current_axis)
            )
            hold_stop.valueChanged.connect(
                lambda _value, current_axis=axis: self._hold_range_changed(current_axis)
            )
            follow.toggled.connect(
                lambda _checked, current_axis=axis: self._follow_toggled(current_axis)
            )
            curve_stride.valueChanged.connect(
                lambda _value, current_axis=axis: self._update_frame_count(current_axis)
            )

    @staticmethod
    def _default_filename() -> str:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        return f"mimo_performance_report_{timestamp}.pdf"

    @staticmethod
    def _ensure_pdf_suffix(path: Path) -> Path:
        if path.suffix.lower() == ".pdf":
            return path
        return path.with_suffix(".pdf")

    def _browse_output_path(self) -> None:
        selected, _selected_filter = QtWidgets.QFileDialog.getSaveFileName(
            self,
            _text("browse_title", self.language),
            self.output_path_edit.text(),
            _text("pdf_filter", self.language),
        )
        if selected:
            self.output_path_edit.setText(str(self._ensure_pdf_suffix(Path(selected))))

    def _focus_range_changed(self, axis: str) -> None:
        self._sync_hold_range(axis)
        self._refresh_validation()

    def _hold_range_changed(self, axis: str) -> None:
        self._update_frame_count(axis)
        self._refresh_validation()

    def _follow_toggled(self, axis: str) -> None:
        follows = getattr(self, f"{axis}_hold_follows_focus").isChecked()
        available = (
            self._azimuth_available if axis == "az" else self._elevation_available
        )
        getattr(self, f"{axis}_hold_start").setEnabled(available and not follows)
        getattr(self, f"{axis}_hold_stop").setEnabled(available and not follows)
        self._sync_hold_range(axis)
        self._refresh_validation()

    def _spectrum_db_toggled(self, checked: bool) -> None:
        self.spectrum_floor_spin.setEnabled(checked)
        self._refresh_validation()

    def _sync_hold_range(self, axis: str) -> None:
        if not getattr(self, f"{axis}_hold_follows_focus").isChecked():
            return
        getattr(self, f"{axis}_hold_start").setValue(
            getattr(self, f"{axis}_focus_start").value()
        )
        getattr(self, f"{axis}_hold_stop").setValue(
            getattr(self, f"{axis}_focus_stop").value()
        )
        self._update_frame_count(axis)

    def _update_frame_count(self, axis: str) -> None:
        start = getattr(self, f"{axis}_hold_start").value()
        stop = getattr(self, f"{axis}_hold_stop").value()
        range_count = max(0, stop - start + 1)
        step = getattr(self, f"{axis}_hold_curve_step").value()
        curve_count = hold_curve_frame_count(range_count, step)
        getattr(self, f"{axis}_hold_frame_count").setText(
            _text(
                "frame_count",
                self.language,
                range_count=range_count,
                step=step,
                curve_count=curve_count,
            )
        )

    def _validation_error(
        self,
        export_kind: str = "report",
    ) -> tuple[str, QtWidgets.QWidget | None]:
        if not self.output_path_edit.text().strip():
            return _text("validation_path", self.language), self.output_path_edit
        if not (self._azimuth_available or self._elevation_available):
            return _text("validation_no_axis", self.language), None
        if export_kind == "report" and not (
            self.include_spectrum_db_checkbox.isChecked()
            or self.include_spectrum_magnitude_checkbox.isChecked()
        ):
            return (
                _text("validation_spectrum_scale", self.language),
                self.include_spectrum_db_checkbox,
            )

        if export_kind == "report":
            for axis, available in (
                ("az", self._azimuth_available),
                ("el", self._elevation_available),
            ):
                if not available:
                    continue
                axis_name = _text(
                    "azimuth" if axis == "az" else "elevation", self.language
                )
                for kind in ("focus", "hold"):
                    start = getattr(self, f"{axis}_{kind}_start")
                    stop = getattr(self, f"{axis}_{kind}_stop")
                    if start.value() > stop.value():
                        return (
                            _text(
                                "validation_range",
                                self.language,
                                axis=axis_name,
                                kind=_text(f"{kind}_kind", self.language),
                            ),
                            start,
                        )
        return "", None

    def _set_validation_message(self, message: str) -> None:
        self.validation_label.setText(message)
        self.validation_label.setVisible(bool(message))

    def _refresh_validation(self, *_args: Any) -> None:
        report_message, _widget = self._validation_error("report")
        image_message, _image_widget = self._validation_error("angle_image")
        self._set_validation_message(report_message)
        self.save_button.setEnabled(not self._export_busy and not report_message)
        self.angle_image_button.setEnabled(
            not self._export_busy and not image_message
        )

    def _request_report_export(self) -> None:
        self._request_export("report")

    def _request_angle_image_export(self) -> None:
        self._request_export("angle_image")

    def _request_export(self, export_kind: str) -> None:
        if self._export_busy:
            return
        message, invalid_widget = self._validation_error(export_kind)
        self._set_validation_message(message)
        if message:
            if invalid_widget is not None:
                invalid_widget.setFocus(QtCore.Qt.FocusReason.OtherFocusReason)
            return

        normalised_path = self._ensure_pdf_suffix(
            Path(self.output_path_edit.text().strip()).expanduser()
        )
        self.output_path_edit.setText(str(normalised_path))
        self._selected_export_kind = export_kind
        self.export_requested.emit(export_kind)

    def set_export_busy(self, busy: bool) -> None:
        """Disable output actions while one background export is active."""

        self._export_busy = bool(busy)
        self.cancel_button.setEnabled(not self._export_busy)
        self._refresh_validation()

    def reject(self) -> None:
        if self._export_busy:
            return
        super().reject()

    def closeEvent(self, event: Any) -> None:  # noqa: N802
        if self._export_busy:
            event.ignore()
            return
        super().closeEvent(event)

    @property
    def export_kind(self) -> str:
        """Return the output action that accepted the dialog."""

        return self._selected_export_kind

    def angle_error_image_options(self) -> AngleErrorImageOptions:
        """Return standalone-image settings inherited from this report form."""

        from .performance_report import AngleErrorImageOptions

        report_path = self._ensure_pdf_suffix(
            Path(self.output_path_edit.text().strip()).expanduser()
        )
        image_path = report_path.with_name(f"{report_path.stem}_angle_error.png")
        return AngleErrorImageOptions(
            output_path=image_path,
            error_limit_deg=self.error_limit_spin.value(),
            language=self.language,
        )

    def options(self) -> PerformanceReportOptions:
        """Return the selected report options; no directories or files are created."""

        from .performance_report import AngleRange, PerformanceReportOptions

        def angle_range(axis: str, kind: str):
            return AngleRange(
                start_deg=getattr(self, f"{axis}_{kind}_start").value(),
                stop_deg=getattr(self, f"{axis}_{kind}_stop").value(),
            )

        output_path = self._ensure_pdf_suffix(
            Path(self.output_path_edit.text().strip()).expanduser()
        )
        title = self.title_edit.text().strip() or _text(
            "default_report_title", self.language
        )
        return PerformanceReportOptions(
            output_path=output_path,
            title=title,
            azimuth_focus=angle_range("az", "focus"),
            elevation_focus=angle_range("el", "focus"),
            azimuth_hold=angle_range("az", "hold"),
            elevation_hold=angle_range("el", "hold"),
            azimuth_hold_stride_frames=self.az_hold_curve_step.value(),
            elevation_hold_stride_frames=self.el_hold_curve_step.value(),
            error_limit_deg=self.error_limit_spin.value(),
            spectrum_floor_db=self.spectrum_floor_spin.value(),
            include_spectrum_db=self.include_spectrum_db_checkbox.isChecked(),
            include_spectrum_magnitude=(
                self.include_spectrum_magnitude_checkbox.isChecked()
            ),
            include_raw_data=self.include_raw_checkbox.isChecked(),
            language=self.language,
        )


__all__ = ["PerformanceReportDialog"]
