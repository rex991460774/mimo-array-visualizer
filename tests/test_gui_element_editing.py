from __future__ import annotations

from collections import deque
from types import SimpleNamespace

import numpy as np
import pytest

from virtual_array.gui import (
    EditableElement,
    MAX_HISTORY_STATES,
    VirtualArrayGui,
    _build_auto_layout_elements,
    _dbf_peak_index,
    _format_frequency_ghz,
    _parse_frequency_ghz,
    _validate_element_count,
    _validated_window_geometry,
)


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


def test_window_geometry_validation_accepts_tk_geometry_strings() -> None:
    assert _validated_window_geometry("1440x900+20-10") == "1440x900+20-10"
    assert _validated_window_geometry("1200x800") == "1200x800"
    assert _validated_window_geometry("0x800+0+0") is None
    assert _validated_window_geometry("not-geometry") is None


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
    assert "numbering aligned" in app.status.value


class _FakeRoot:
    def __init__(self) -> None:
        self.cancelled: list[str] = []

    def after_cancel(self, after_id: str) -> None:
        self.cancelled.append(after_id)


class _FakeProgressVar:
    def __init__(self) -> None:
        self.value = None

    def set(self, value: float) -> None:
        self.value = value


class _FakeLabel:
    def __init__(self) -> None:
        self.text = ""

    def configure(self, **kwargs) -> None:  # noqa: ANN003
        self.text = kwargs["text"]


def test_dbf_progress_scrub_pauses_animation_at_selected_frame() -> None:
    app = VirtualArrayGui.__new__(VirtualArrayGui)
    app.root = _FakeRoot()
    app.status = _FakeStatus()
    app.dbf_progress_updating = False
    app.dbf_scan_active = True
    app.dbf_scan_paused = False
    app.dbf_scan_mode = "azimuth"
    app.dbf_scan_after_id = "pending"
    app.dbf_true_angles = np.linspace(-90.0, 90.0, 91)
    app.dbf_scan_angles = np.linspace(-90.0, 90.0, 91)
    app.dbf_spectra_db = np.zeros((91, 91), dtype=float)
    drawn_frames: list[int] = []
    app._draw_dbf_scan_frame = lambda: drawn_frames.append(app.dbf_scan_frame)
    app._update_dbf_scan_controls = lambda: None

    app.on_dbf_progress_changed("azimuth", "20.2")

    assert app.dbf_scan_active
    assert app.dbf_scan_paused
    assert app.dbf_scan_frame == 20
    assert app.dbf_scan_after_id is None
    assert app.root.cancelled == ["pending"]
    assert drawn_frames == [20]
    assert "Paused Azimuth DBF spectrum at -50.0 deg" in app.status.value


def test_dbf_progress_label_tracks_chart_mode_and_frame() -> None:
    app = VirtualArrayGui.__new__(VirtualArrayGui)
    progress_var = _FakeProgressVar()
    progress_label = _FakeLabel()
    app.az_chart = SimpleNamespace(progress_var=None, progress_label=None)
    app.el_chart = SimpleNamespace(
        progress_var=progress_var,
        progress_label=progress_label,
    )
    app.dbf_progress_updating = False

    app._set_dbf_progress("elevation", 45, 0.0)

    assert progress_var.value == 45.0
    assert progress_label.text == "El 0 deg (46/91)"
    assert not app.dbf_progress_updating


def test_dbf_peak_marker_prefers_true_angle_when_peaks_are_tied() -> None:
    scan_angles = np.array([-90.0, 0.0, 90.0])
    spectrum_db = np.array([0.0, 0.0, 0.0])

    assert _dbf_peak_index(scan_angles, spectrum_db, true_angle=0.0) == 1
