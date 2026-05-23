from __future__ import annotations

from virtual_array.app_state import load_state, save_state


def test_save_and_load_state_round_trip(tmp_path) -> None:
    path = tmp_path / "state.json"
    state = {
        "version": 1,
        "last_layout_dir": str(tmp_path / "layouts"),
        "last_pattern_dir": str(tmp_path / "patterns"),
        "frequency_mode": "77 GHz",
        "layout": {
            "version": 1,
            "unit": "lambda",
            "tx": [{"name": "Tx1", "x": 0, "y": 0}],
            "rx": [{"name": "Rx1", "x": 0, "y": 0}],
        },
    }

    assert save_state(state, path) == path
    assert load_state(path) == state


def test_load_missing_state_returns_empty_dict(tmp_path) -> None:
    assert load_state(tmp_path / "missing.json") == {}
