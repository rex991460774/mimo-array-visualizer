from __future__ import annotations

import pytest

from virtual_array.gui import EditableElement, VirtualArrayGui


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
