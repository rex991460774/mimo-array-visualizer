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
    duplicate_text, duplicate_color = _note_display("存在重复虚拟通道")
    windowing_text, windowing_color = _note_display("建议加窗降低旁瓣")
    high_text, high_color = _note_display("俯仰模糊风险高")
    none_text, none_color = _note_display("暂无风险提示")

    assert duplicate_text.startswith("WARN  ")
    assert duplicate_color == "#c2410c"
    assert windowing_text.startswith("TAPER  ")
    assert windowing_color == "#a16207"
    assert high_text.startswith("RISK  ")
    assert high_color == "#b91c1c"
    assert none_text.startswith("OK  ")
    assert none_color == "#15803d"
