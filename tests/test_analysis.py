from __future__ import annotations

import numpy as np
import pytest

from virtual_array.analysis import (
    AF_GRID_SIZE,
    calculate_metrics_and_psf,
    estimate_resolution,
)
from virtual_array.examples.case4_5tx7rx_sel import build_array
from virtual_array.geometry import AntennaArray


def test_case4_analysis_metrics_are_stable() -> None:
    af_db, azimuths, elevations, metrics = calculate_metrics_and_psf(build_array())

    assert af_db.shape == (AF_GRID_SIZE, AF_GRID_SIZE)
    assert azimuths[0] == -75.0
    assert azimuths[-1] == 75.0
    assert elevations[0] == -15.0
    assert elevations[-1] == 15.0
    assert metrics.tx_count == 8
    assert metrics.rx_count == 8
    assert metrics.virtual_count == 64
    assert metrics.unique_count == 64
    assert metrics.azimuth_resolution == pytest.approx(1.3537, abs=1e-4)
    assert metrics.azimuth_3db_beamwidth == pytest.approx(1.7230, abs=1e-4)
    assert metrics.azimuth_psl_db == pytest.approx(-12.6615, abs=1e-4)
    assert metrics.psl_db == pytest.approx(-3.8061, abs=1e-4)
    assert metrics.sidelobe_azimuth == pytest.approx(0.0)
    assert metrics.sidelobe_elevation == pytest.approx(-11.8333, abs=1e-4)
    assert metrics.front_radar_status == "Good"
    assert metrics.elevation_ambiguity_level == "High"
    assert metrics.warning_messages == ("High elevation ambiguity",)


def test_analysis_tracks_duplicate_virtual_points() -> None:
    array = AntennaArray.from_xy(
        tx_x=[0, 1],
        tx_y=[0, 0],
        rx_x=[0, 1],
        rx_y=[0, 0],
    )

    _af_db, _azimuths, _elevations, metrics = calculate_metrics_and_psf(array)

    assert metrics.virtual_count == 4
    assert metrics.unique_count == 3
    assert metrics.duplicate_locations == 1
    assert metrics.duplicate_excess == 1


def test_single_element_array_factor_is_flat() -> None:
    array = AntennaArray.from_xy(tx_x=[0], tx_y=[0], rx_x=[0], rx_y=[0])

    af_db, _azimuths, _elevations, metrics = calculate_metrics_and_psf(array)

    assert np.allclose(af_db, 0.0)
    assert metrics.azimuth_resolution is None
    assert metrics.elevation_resolution is None
    assert metrics.azimuth_psl_db == pytest.approx(0.0)
    assert metrics.psl_grade == "Bad"


def test_estimate_resolution_uses_half_lambda_aperture_units() -> None:
    assert estimate_resolution(0.0) is None
    assert estimate_resolution(75.0) == pytest.approx(1.3537, abs=1e-4)
