from __future__ import annotations

from collections import deque
from types import SimpleNamespace

import numpy as np
import pytest
from matplotlib.figure import Figure

from virtual_array.analysis import DBF_SCAN_GRID_SIZE
from virtual_array.gui import (
    CHANNEL_PATTERN_TARGET_PHYSICAL,
    CHANNEL_PATTERN_TARGET_VIRTUAL,
    DBF_DISPLAY_MAGNITUDE,
    EditableElement,
    MAX_HISTORY_STATES,
    ResponseChart,
    VirtualArrayGui,
    _build_auto_layout_elements,
    _default_workspace_sash_position,
    _dbf_peak_index,
    _drag_position_with_offset,
    _format_frequency_ghz,
    _format_margin_db,
    _new_response_hover_annotation,
    _parse_frequency_ghz,
    _parse_margin_db,
    _square_axis_limits,
    _validate_element_count,
    _validated_window_geometry,
)


def test_drag_position_preserves_grab_offset_without_grid_jumps() -> None:
    assert _drag_position_with_offset(
        0.37,
        -1.22,
        (0.18, -0.08),
        None,
    ) == pytest.approx((0.55, -1.30))


def test_drag_position_clips_after_applying_grab_offset() -> None:
    assert _drag_position_with_offset(
        0.95,
        -1.95,
        (0.20, -0.20),
        (-1.0, 1.0, -2.0, 2.0),
    ) == pytest.approx((1.0, -2.0))


def test_layout_import_rejects_more_than_16_tx() -> None:
    app = VirtualArrayGui.__new__(VirtualArrayGui)
    config = {
        "version": 1,
        "unit": "lambda",
        "tx": [{"name": f"Tx{i}", "x": i, "y": 0} for i in range(17)],
        "rx": [{"name": "Rx1", "x": 0, "y": 0}],
    }

    with pytest.raises(ValueError, match="maximum is 16"):
        app._elements_from_layout_config(config)


def test_layout_import_normalizes_element_names() -> None:
    app = VirtualArrayGui.__new__(VirtualArrayGui)
    config = {
        "version": 1,
        "unit": "lambda",
        "tx": [
            {"name": "CustomA", "x": 0, "y": 0},
            {"name": "CustomB", "x": 1, "y": 0},
        ],
        "rx": [{"name": "Anything", "x": 0, "y": 0}],
    }

    elements = app._elements_from_layout_config(config)

    assert [element.name for element in elements] == ["Tx1", "Tx2", "Rx1"]


def test_renumber_elements_compacts_after_middle_delete() -> None:
    app = VirtualArrayGui.__new__(VirtualArrayGui)
    app.elements = [
        EditableElement(kind="tx", index=0, name="Tx1", x=0, y=0),
        EditableElement(kind="tx", index=2, name="Tx3", x=2, y=0),
        EditableElement(kind="rx", index=0, name="Rx1", x=0, y=-1),
        EditableElement(kind="rx", index=2, name="Rx3", x=2, y=-1),
    ]
    app.selected_element = app.elements[1]

    app._renumber_elements()

    assert [(element.kind, element.index, element.name) for element in app.elements] == [
        ("tx", 0, "Tx1"),
        ("tx", 1, "Tx2"),
        ("rx", 0, "Rx1"),
        ("rx", 1, "Rx2"),
    ]
    assert app.selected_element.name == "Tx2"


@pytest.mark.parametrize(
    ("raw_value", "expected"),
    [
        ("77", 77.0),
        ("77 GHz", 77.0),
        ("92.5ghz", 92.5),
        ("60g", 60.0),
        (79.25, 79.25),
    ],
)
def test_frequency_parser_accepts_custom_ghz_values(raw_value, expected) -> None:
    assert _parse_frequency_ghz(raw_value) == pytest.approx(expected)


@pytest.mark.parametrize("raw_value", ["", "abc", 0, -1, True, float("inf")])
def test_frequency_parser_rejects_invalid_values(raw_value) -> None:
    assert _parse_frequency_ghz(raw_value) is None


def test_frequency_formatter_keeps_compact_display() -> None:
    assert _format_frequency_ghz(77.0) == "77"
    assert _format_frequency_ghz(77.125000) == "77.125"


@pytest.mark.parametrize(
    ("raw_value", "expected"),
    [
        ("0.5", 0.5),
        ("1.25 dB", 1.25),
        ("2db", 2.0),
        (0, 0.0),
    ],
)
def test_margin_parser_accepts_non_negative_db_values(raw_value, expected) -> None:
    assert _parse_margin_db(raw_value) == pytest.approx(expected)


@pytest.mark.parametrize("raw_value", ["", "abc", -0.1, True, float("inf")])
def test_margin_parser_rejects_invalid_values(raw_value) -> None:
    assert _parse_margin_db(raw_value) is None


def test_margin_formatter_keeps_compact_display() -> None:
    assert _format_margin_db(1.0) == "1"
    assert _format_margin_db(0.125) == "0.125"


def test_response_hover_tooltip_follows_cursor_without_arrow() -> None:
    class DummyCanvas:
        def __init__(self) -> None:
            self.draw_count = 0

        def draw_idle(self) -> None:
            self.draw_count += 1

    fig = Figure()
    ax = fig.add_subplot(111)
    ax.set_xlim(-90, 90)
    ax.set_ylim(-40, 0)
    annotation = _new_response_hover_annotation(ax)
    canvas = DummyCanvas()
    chart = ResponseChart(fig=fig, ax=ax, canvas=canvas, hover_annotation=annotation)
    chart.hover_angles = np.array([-10.0, 0.0, 10.0])
    chart.hover_db = np.array([-12.0, -6.0, -18.0])
    app = VirtualArrayGui.__new__(VirtualArrayGui)

    app._update_response_hover(
        SimpleNamespace(inaxes=ax, xdata=1.25, ydata=-8.5),
        chart,
        "Az",
    )

    assert annotation.arrow_patch is None
    assert annotation.get_visible()
    assert annotation.xy == pytest.approx((1.25, -8.5))
    assert "Az = 0.0" in annotation.get_text()
    assert canvas.draw_count == 1

    app._update_response_hover(
        SimpleNamespace(inaxes=None, xdata=None, ydata=None),
        chart,
        "Az",
    )

    assert not annotation.get_visible()
    assert canvas.draw_count == 2


def test_dbf_display_values_convert_db_to_correlation_magnitude() -> None:
    app = VirtualArrayGui.__new__(VirtualArrayGui)
    app.dbf_display_mode = SimpleNamespace(get=lambda: DBF_DISPLAY_MAGNITUDE)

    values = app._dbf_display_values(np.array([-40.0, -6.020599913, 0.0, 3.0]))

    assert values == pytest.approx([0.01, 0.5, 1.0, 1.0])
    assert app._format_dbf_display_value(-6.020599913) == "相关系数 = 0.500"


def test_window_geometry_validation_accepts_tk_geometry_strings() -> None:
    assert _validated_window_geometry("1440x900+20-10") == "1440x900+20-10"
    assert _validated_window_geometry("1200x800") == "1200x800"
    assert _validated_window_geometry("0x800+0+0") is None
    assert _validated_window_geometry("not-geometry") is None


def test_default_workspace_sash_position_uses_half_available_width() -> None:
    assert _default_workspace_sash_position(1720) == 860
    assert _default_workspace_sash_position(1280) == 640
    assert _default_workspace_sash_position(2) == 1
    assert _default_workspace_sash_position(1) is None


def test_layout_snapshot_restore_round_trip_preserves_selection() -> None:
    app = VirtualArrayGui.__new__(VirtualArrayGui)
    app.elements = [
        EditableElement(kind="tx", index=0, name="Tx1", x=0, y=0),
        EditableElement(kind="rx", index=0, name="Rx1", x=1, y=-2),
    ]
    app.selected_element = app.elements[1]
    snapshot = app._capture_layout_snapshot()

    app.elements[1].x = 9
    app.selected_element = None
    app.dragging = app.elements[0]
    app.drag_bounds = (0, 1, 0, 1)
    app.drag_axis_limits = ((0, 1), (0, 1))
    app.drag_start_snapshot = snapshot

    app._restore_layout_snapshot(snapshot)

    assert [(element.name, element.x, element.y) for element in app.elements] == [
        ("Tx1", 0, 0),
        ("Rx1", 1, -2),
    ]
    assert app.selected_element is app.elements[1]
    assert app.dragging is None
    assert app.drag_start_snapshot is None


def test_escape_mid_drag_restores_layout_and_releases_pointer() -> None:
    app = VirtualArrayGui.__new__(VirtualArrayGui)
    app.elements = [
        EditableElement(kind="tx", index=0, name="Tx1", x=0.0, y=2.0),
        EditableElement(kind="rx", index=0, name="Rx1", x=0.0, y=-2.0),
    ]
    app.selected_element = None
    snapshot = app._capture_layout_snapshot()
    app.dragging = app.elements[0]
    app.dragging.x = 0.55
    app.drag_bounds = (-4.0, 4.0, -4.0, 4.0)
    app.drag_axis_limits = ((-2.0, 2.0), (-2.0, 2.0))
    app.drag_start_snapshot = snapshot
    app.drag_grab_offset = (0.15, -0.10)
    app._physical_drag_after_id = "drag-redraw"
    app.delete_mode = False

    cancelled: list[str] = []
    released: list[bool] = []
    generated: list[bool] = []
    status: list[str] = []
    app.root = SimpleNamespace(after_cancel=cancelled.append)
    app.phys_canvas = SimpleNamespace(release_pointer=lambda: released.append(True))
    app.generate_virtual_array = lambda: generated.append(True)
    app.status = SimpleNamespace(set=status.append)
    app._t = lambda key, **_kwargs: key

    assert app.on_escape_key() == "break"
    assert [(element.x, element.y) for element in app.elements] == [
        (0.0, 2.0),
        (0.0, -2.0),
    ]
    assert app.dragging is None
    assert app.drag_start_snapshot is None
    assert app.drag_grab_offset is None
    assert app._physical_drag_after_id is None
    assert cancelled == ["drag-redraw"]
    assert released == [True]
    assert generated == [True]
    assert status == ["drag_cancel"]


def test_default_gui_layout_uses_clean_1t1r_starter() -> None:
    app = VirtualArrayGui.__new__(VirtualArrayGui)

    elements = app._build_elements()

    assert [(element.name, element.x, element.y) for element in elements] == [
        ("Tx1", 0.0, 4.0),
        ("Rx1", 0.0, -4.0),
    ]


def test_auto_layout_builds_centered_tx_rx_rows() -> None:
    elements = _build_auto_layout_elements(tx_count=3, rx_count=2)

    assert [(element.name, element.x, element.y) for element in elements] == [
        ("Tx1", -2.0, 4.0),
        ("Tx2", 0.0, 4.0),
        ("Tx3", 2.0, 4.0),
        ("Rx1", -1.0, -4.0),
        ("Rx2", 1.0, -4.0),
    ]


def test_pattern_channel_names_switch_between_physical_and_virtual_targets() -> None:
    app = VirtualArrayGui.__new__(VirtualArrayGui)
    app.elements = _build_auto_layout_elements(tx_count=2, rx_count=3)

    assert app._pattern_channel_names(CHANNEL_PATTERN_TARGET_PHYSICAL) == [
        "Tx1",
        "Tx2",
        "Rx1",
        "Rx2",
        "Rx3",
    ]
    assert app._pattern_channel_names(CHANNEL_PATTERN_TARGET_VIRTUAL) == [
        "Tx1Rx1",
        "Tx1Rx2",
        "Tx1Rx3",
        "Tx2Rx1",
        "Tx2Rx2",
        "Tx2Rx3",
    ]
    assert app._all_pattern_channel_names() == [
        "Tx1",
        "Tx2",
        "Rx1",
        "Rx2",
        "Rx3",
        "Tx1Rx1",
        "Tx1Rx2",
        "Tx1Rx3",
        "Tx2Rx1",
        "Tx2Rx2",
        "Tx2Rx3",
    ]


def test_square_axis_limits_keep_physical_grid_square() -> None:
    x_limits, y_limits = _square_axis_limits(
        [-1.0, 1.0],
        [-4.0, 4.0],
        minimum_span=4.0,
        padding=2.0,
    )

    assert x_limits[1] - x_limits[0] == pytest.approx(y_limits[1] - y_limits[0])
    assert x_limits[0] < -1.0 < x_limits[1]
    assert y_limits[0] < -4.0 < y_limits[1]


@pytest.mark.parametrize(
    ("raw_value", "kind", "expected"),
    [
        ("1", "tx", 1),
        ("16", "rx", 16),
        (4, "tx", 4),
    ],
)
def test_validate_element_count_accepts_valid_ranges(raw_value, kind, expected) -> None:
    assert _validate_element_count(raw_value, kind) == expected


@pytest.mark.parametrize("raw_value", ["", "abc", "0", "17"])
def test_validate_element_count_rejects_invalid_ranges(raw_value) -> None:
    with pytest.raises(ValueError):
        _validate_element_count(raw_value, "tx")


class _FakeStatus:
    def __init__(self) -> None:
        self.value = ""

    def set(self, value: str) -> None:
        self.value = value


def test_delete_element_renumbers_by_position_without_gaps() -> None:
    app = VirtualArrayGui.__new__(VirtualArrayGui)
    app.elements = [
        EditableElement(kind="tx", index=0, name="Tx1", x=4, y=0),
        EditableElement(kind="tx", index=1, name="Tx2", x=0, y=0),
        EditableElement(kind="tx", index=2, name="Tx3", x=2, y=0),
        EditableElement(kind="rx", index=0, name="Rx1", x=0, y=-2),
    ]
    app.selected_element = app.elements[1]
    app.dragging = None
    app.drag_bounds = None
    app.drag_axis_limits = None
    app.drag_start_snapshot = None
    app.delete_mode = True
    app.undo_stack = deque(maxlen=MAX_HISTORY_STATES)
    app.redo_stack = deque(maxlen=MAX_HISTORY_STATES)
    app.status = _FakeStatus()
    app.generate_virtual_array = lambda: None

    assert app._delete_element(app.elements[1])

    assert [(element.name, element.x) for element in app.elements if element.kind == "tx"] == [
        ("Tx1", 2),
        ("Tx2", 4),
    ]
    assert "编号已自动对齐" in app.status.value


class _FakeRoot:
    def __init__(self) -> None:
        self.cancelled: list[str] = []

    def after_cancel(self, after_id: str) -> None:
        self.cancelled.append(after_id)


class _FakeLabel:
    def __init__(self) -> None:
        self.text = ""

    def configure(self, **kwargs) -> None:  # noqa: ANN003
        self.text = kwargs["text"]


class _FakeCursorWidget:
    def __init__(self) -> None:
        self.cursor = ""

    def configure(self, **kwargs) -> None:  # noqa: ANN003
        if "cursor" in kwargs:
            self.cursor = kwargs["cursor"]


class _FakeCanvasWithWidget:
    def __init__(self) -> None:
        self.draw_count = 0
        self.widget = _FakeCursorWidget()

    def draw_idle(self) -> None:
        self.draw_count += 1

    def get_tk_widget(self) -> _FakeCursorWidget:
        return self.widget


def test_dbf_true_line_drag_pauses_animation_at_selected_angle() -> None:
    app = VirtualArrayGui.__new__(VirtualArrayGui)
    app.root = _FakeRoot()
    app.status = _FakeStatus()
    app.dbf_scan_active = True
    app.dbf_scan_paused = False
    app.dbf_scan_mode = "azimuth"
    app.dbf_scan_after_id = "pending"
    app.dbf_true_angles = np.linspace(-90.0, 90.0, DBF_SCAN_GRID_SIZE)
    app.dbf_scan_angles = np.linspace(-90.0, 90.0, DBF_SCAN_GRID_SIZE)
    app.dbf_spectra_db = np.zeros(
        (DBF_SCAN_GRID_SIZE, DBF_SCAN_GRID_SIZE), dtype=float
    )
    drawn_frames: list[int] = []
    app._draw_dbf_scan_frame = lambda: drawn_frames.append(app.dbf_scan_frame)
    app._update_dbf_scan_controls = lambda: None

    app._set_dbf_scan_angle("azimuth", -69.8)

    assert app.dbf_scan_active
    assert app.dbf_scan_paused
    assert app.dbf_scan_frame == 20
    assert app.dbf_scan_after_id is None
    assert app.root.cancelled == ["pending"]
    assert drawn_frames == [20]
    assert "方位DBF角谱已暂停在-70.0°" in app.status.value


def test_dbf_angle_label_tracks_chart_mode_and_frame() -> None:
    app = VirtualArrayGui.__new__(VirtualArrayGui)
    progress_label = _FakeLabel()
    app.az_chart = SimpleNamespace(progress_label=None)
    app.el_chart = SimpleNamespace(
        progress_label=progress_label,
    )

    app._set_dbf_progress("elevation", 45, 0.0)

    assert progress_label.text == "俯仰 0° (46/181)"


def test_response_true_angle_line_sets_hand_cursor_near_guide() -> None:
    fig = Figure()
    ax = fig.add_subplot(111)
    ax.set_xlim(-90, 90)
    ax.set_ylim(-40, 0)
    canvas = _FakeCanvasWithWidget()
    chart = ResponseChart(fig=fig, ax=ax, canvas=canvas, true_angle=0.0)
    app = VirtualArrayGui.__new__(VirtualArrayGui)

    app._update_response_cursor(
        SimpleNamespace(inaxes=ax, xdata=1.0, ydata=-10.0),
        chart,
    )

    assert canvas.widget.cursor == "hand2"

    app._update_response_cursor(
        SimpleNamespace(inaxes=ax, xdata=12.0, ydata=-10.0),
        chart,
    )

    assert canvas.widget.cursor == ""


def test_dbf2d_crosshair_sets_hand_cursor_near_true_angle_guides() -> None:
    fig = Figure()
    ax = fig.add_subplot(111)
    ax.set_xlim(-90, 90)
    ax.set_ylim(-90, 90)
    app = VirtualArrayGui.__new__(VirtualArrayGui)
    app.dbf2d_ax = ax
    app.dbf2d_canvas = _FakeCanvasWithWidget()
    app.dbf2d_az_frame = 90
    app.dbf2d_el_frame = 90

    app._update_dbf2d_cursor(SimpleNamespace(inaxes=ax, xdata=1.0, ydata=45.0))

    assert app.dbf2d_canvas.widget.cursor == "hand2"

    app._update_dbf2d_cursor(SimpleNamespace(inaxes=ax, xdata=20.0, ydata=45.0))

    assert app.dbf2d_canvas.widget.cursor == ""


def test_dbf2d_hover_tooltip_reports_nearest_angle_and_correlation() -> None:
    fig = Figure()
    ax = fig.add_subplot(111)
    ax.set_xlim(-1, 1)
    ax.set_ylim(-2, 2)
    app = VirtualArrayGui.__new__(VirtualArrayGui)
    app.dbf2d_ax = ax
    app.dbf2d_canvas = _FakeCanvasWithWidget()
    app.dbf2d_hover_azimuths = np.array([-1.0, 0.0, 1.0])
    app.dbf2d_hover_elevations = np.array([-2.0, 2.0])
    app.dbf2d_hover_db = np.array([[-10.0, -9.0, -8.0], [-7.0, -6.0, -5.0]])
    app.dbf2d_hover_annotation = _new_response_hover_annotation(ax)
    app.dbf2d_hover_marker = ax.scatter([], [])

    app._update_dbf2d_hover(SimpleNamespace(inaxes=ax, xdata=0.2, ydata=1.9))

    assert app.dbf2d_hover_annotation.get_visible()
    assert app.dbf2d_hover_annotation.xy == pytest.approx((0.2, 1.9))
    tooltip = app.dbf2d_hover_annotation.get_text()
    assert "方位 = +0.0" in tooltip
    assert "俯仰 = +2.0" in tooltip
    assert "相关系数 = -6.00 dB" in tooltip
    assert app.dbf2d_canvas.draw_count == 1


def test_dbf2d_hover_tooltip_uses_magnitude_display_mode() -> None:
    fig = Figure()
    ax = fig.add_subplot(111)
    ax.set_xlim(-1, 1)
    ax.set_ylim(-2, 2)
    app = VirtualArrayGui.__new__(VirtualArrayGui)
    app.dbf_display_mode = SimpleNamespace(get=lambda: DBF_DISPLAY_MAGNITUDE)
    app.dbf2d_ax = ax
    app.dbf2d_canvas = _FakeCanvasWithWidget()
    app.dbf2d_hover_azimuths = np.array([-1.0, 0.0, 1.0])
    app.dbf2d_hover_elevations = np.array([-2.0, 2.0])
    app.dbf2d_hover_db = np.array([[-10.0, -9.0, -8.0], [-7.0, -6.0, -5.0]])
    app.dbf2d_hover_annotation = _new_response_hover_annotation(ax)
    app.dbf2d_hover_marker = ax.scatter([], [])

    app._update_dbf2d_hover(SimpleNamespace(inaxes=ax, xdata=0.2, ydata=1.9))

    tooltip = app.dbf2d_hover_annotation.get_text()
    assert "方位 = +0.0" in tooltip
    assert "俯仰 = +2.0" in tooltip
    assert "相关系数 = 0.501" in tooltip


def test_dbf_peak_marker_prefers_true_angle_when_peaks_are_tied() -> None:
    scan_angles = np.array([-90.0, 0.0, 90.0])
    spectrum_db = np.array([0.0, 0.0, 0.0])

    assert _dbf_peak_index(scan_angles, spectrum_db, true_angle=0.0) == 1
