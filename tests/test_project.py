from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest
from pydantic import ValidationError

from virtual_array.examples.case4_5tx7rx_sel import build_array
from virtual_array.project import (
    Layout,
    Point,
    Project,
    auto_layout,
    default_project,
    layout_from_v1,
    layout_to_v1,
    project_array,
    project_from_document,
    snap_lambda,
)

EXAMPLES = Path(__file__).resolve().parents[1] / "examples"


def test_default_project_matches_case4_reference_array() -> None:
    array = project_array(default_project())
    reference = build_array()

    assert np.array_equal(array.tx_xy(), reference.tx_xy())
    assert np.array_equal(array.rx_xy(), reference.rx_xy())
    assert [point.name for point in array.tx] == [point.name for point in reference.tx]


def test_layout_v1_example_imports_with_lambda_coordinates() -> None:
    document = json.loads((EXAMPLES / "antenna_layout_config.json").read_text(encoding="utf-8"))

    layout = layout_from_v1(document)

    assert len(layout.tx) == 8
    assert layout.tx[4] == Point(x=1.5, y=-12)
    assert layout.rx[6] == Point(x=9, y=5)


def test_layout_v1_snaps_to_half_lambda_grid_and_accepts_legacy_unit() -> None:
    layout = layout_from_v1(
        {
            "version": 1,
            "unit": "λ/2",
            "tx": [{"name": "A", "x": 3, "y": -1.2}],
            "rx": [{"x": 0.4, "y": 0}],
        }
    )

    assert layout.tx[0] == Point(x=1.5, y=-0.5)
    assert layout.rx[0] == Point(x=0.0, y=0.0)


@pytest.mark.parametrize(
    "document, message",
    [
        ({"version": 3}, "Unsupported layout version"),
        ({"version": 1, "unit": "mm", "tx": [], "rx": []}, "unit"),
        ({"version": 1, "unit": "lambda", "tx": [], "rx": [{"x": 0, "y": 0}]}, "non-empty"),
        (
            {"version": 1, "unit": "lambda", "tx": [{"x": 0}], "rx": [{"x": 0, "y": 0}]},
            "missing coordinate",
        ),
        (
            {
                "version": 1,
                "unit": "lambda",
                "tx": [{"x": i, "y": 0} for i in range(17)],
                "rx": [{"x": 0, "y": 0}],
            },
            "maximum is 16",
        ),
    ],
)
def test_layout_v1_rejects_invalid_documents(document: dict, message: str) -> None:
    with pytest.raises(ValueError, match=message):
        layout_from_v1(document)


def test_layout_v1_round_trip_preserves_coordinates_and_names() -> None:
    project = default_project()

    document = layout_to_v1(project)

    assert document["unit"] == "lambda"
    assert document["tx"][0] == {"name": "Tx1", "x": 0, "y": 0}
    assert document["rx"][5] == {"name": "Rx6", "x": 12, "y": -7}
    assert layout_from_v1(document) == project.layout


def test_project_from_v1_document_reads_evaluation_settings() -> None:
    document = layout_to_v1(default_project())
    document["evaluation"] = {"frequency_ghz": "79", "ambiguity_margin_db": 1.5}

    project = project_from_document(document)

    assert project.frequency_ghz == 79.0
    assert project.ambiguity_margin_db == 1.5


def test_project_from_v2_document_round_trips() -> None:
    project = default_project().model_copy(update={"name": "demo", "frequency_ghz": 24.125})

    restored = project_from_document(project.model_dump(mode="json"))

    assert restored == project


def test_auto_layout_centers_rows_on_half_lambda_grid() -> None:
    layout = auto_layout(3, 4)

    assert [point.x for point in layout.tx] == [-1.0, 0.0, 1.0]
    assert [point.x for point in layout.rx] == [-1.5, -0.5, 0.5, 1.5]
    assert {point.y for point in layout.tx} == {2.0}
    assert {point.y for point in layout.rx} == {-2.0}
    with pytest.raises(ValueError):
        auto_layout(0, 4)


def test_project_validation_rejects_bad_values() -> None:
    layout = Layout(tx=[Point(x=0, y=0)], rx=[Point(x=0, y=0)])
    with pytest.raises(ValidationError):
        Project(layout=layout, frequency_ghz=0)
    with pytest.raises(ValidationError):
        Project(layout=layout, dbf_dictionary={"mode": "custom"})
    with pytest.raises(ValidationError):
        Point(x=float("nan"), y=0)


def test_legacy_zero_ref_dictionary_mode_is_folded_into_channel_pattern() -> None:
    layout = Layout(tx=[Point(x=0, y=0)], rx=[Point(x=0, y=0)])

    project = Project(layout=layout, dbf_dictionary={"mode": "channel_pattern_zero_ref"})

    assert project.dbf_dictionary.mode == "channel_pattern"


def test_snap_lambda_avoids_negative_zero() -> None:
    assert str(snap_lambda(-0.1)) == "0.0"
    assert snap_lambda(0.76) == 1.0
