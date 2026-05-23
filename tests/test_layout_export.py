from __future__ import annotations

import json

from virtual_array.gui import _layout_config_to_json, _note_display


def test_layout_config_json_keeps_points_compact_and_evaluation_readable() -> None:
    config = {
        "version": 1,
        "unit": "lambda",
        "tx": [{"name": "Tx1", "x": -9, "y": -12}],
        "rx": [{"name": "Rx1", "x": -9, "y": 0}],
        "evaluation": {
            "frequency_mode": "77 GHz",
            "virtual_utilization": {
                "unique_points": 1,
                "virtual_channels": 1,
                "ratio": 1,
                "duplicate_points": 0,
            },
        },
    }

    text = _layout_config_to_json(config)

    assert '    {"name": "Tx1", "x": -9, "y": -12}' in text
    assert '    {"name": "Rx1", "x": -9, "y": 0}' in text
    assert '  "evaluation": {' in text
    assert json.loads(text) == config


def test_note_display_assigns_icons_and_colors() -> None:
    duplicate_text, duplicate_color = _note_display("Duplicate virtual points detected")
    windowing_text, windowing_color = _note_display("Windowing recommended")
    high_text, high_color = _note_display("elevation ambiguity high")
    none_text, none_color = _note_display("None")

    assert duplicate_text.startswith("⚠️ ")
    assert duplicate_color == "#ef6c00"
    assert windowing_text.startswith("📉 ")
    assert windowing_color == "#b58900"
    assert high_text.startswith("🚨 ")
    assert high_color == "#c62828"
    assert none_text.startswith("✅ ")
    assert none_color == "#2e7d32"
