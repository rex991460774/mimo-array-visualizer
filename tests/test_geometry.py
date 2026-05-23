import numpy as np
import pytest

from virtual_array.geometry import AntennaArray
from virtual_array.examples.case4_5tx7rx_sel import build_array
from virtual_array.grid import snap_to_grid


def test_virtual_count_for_case4_table_coordinates() -> None:
    array = build_array()

    assert array.summary()["tx_count"] == 8
    assert array.summary()["rx_count"] == 8
    assert array.summary()["virtual_count"] == 64


def test_horizontal_subset_for_case4_is_5tx7rx() -> None:
    array = build_array().horizontal_subset(tx_y=0.0, rx_y=-10.0)

    assert array.summary()["tx_count"] == 5
    assert array.summary()["rx_count"] == 7
    assert array.summary()["virtual_count"] == 35
    assert array.summary()["unique_virtual_count"] == 35


def test_virtual_coordinates_are_tx_plus_rx() -> None:
    array = AntennaArray.from_xy(
        tx_x=[10, 20],
        tx_y=[1, 2],
        rx_x=[3, 4],
        rx_y=[5, 6],
    )

    assert np.array_equal(
        array.virtual_xy(),
        np.array(
            [
                [13.0, 6.0],
                [14.0, 7.0],
                [23.0, 7.0],
                [24.0, 8.0],
            ]
        ),
    )


def test_unique_virtual_coordinates_count_multiplicity() -> None:
    array = AntennaArray.from_xy(
        tx_x=[0, 1],
        tx_y=[0, 0],
        rx_x=[0, 1],
        rx_y=[0, 0],
    )

    unique, counts = array.unique_virtual_xy()

    assert np.array_equal(unique, np.array([[0.0, 0.0], [1.0, 0.0], [2.0, 0.0]]))
    assert np.array_equal(counts, np.array([1, 2, 1]))


def test_rejects_mismatched_coordinate_lengths() -> None:
    with pytest.raises(ValueError, match="tx_x and tx_y"):
        AntennaArray.from_xy(tx_x=[0], tx_y=[0, 1], rx_x=[0], rx_y=[0])


def test_snap_to_half_lambda_grid() -> None:
    assert snap_to_grid(10.49) == 10.0
    assert snap_to_grid(10.51) == 11.0
