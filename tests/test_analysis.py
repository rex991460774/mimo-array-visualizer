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
from virtual_array.gui import (
    RESPONSE_MODE_AZIMUTH,
    RESPONSE_MODE_ELEVATION,
    _response_cut_for_mode,
    _response_sidelobe_marker,
)


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


def test_response_cut_switches_between_azimuth_and_elevation() -> None:
    af_db = np.array(
        [
            [-30.0, -20.0, -10.0],
            [-12.0, 0.0, -12.0],
            [-9.0, -18.0, -27.0],
        ]
    )
    azimuths = np.array([-1.0, 0.0, 1.0])
    elevations = np.array([-10.0, 0.0, 10.0])

    az_cut = _response_cut_for_mode(
        af_db, azimuths, elevations, RESPONSE_MODE_AZIMUTH
    )
    el_cut = _response_cut_for_mode(
        af_db, azimuths, elevations, RESPONSE_MODE_ELEVATION
    )

    assert az_cut.label == "Az"
    assert np.array_equal(az_cut.angles, azimuths)
    assert np.array_equal(az_cut.gains_db, af_db[1, :])
    assert el_cut.label == "El"
    assert np.array_equal(el_cut.angles, elevations)
    assert np.array_equal(el_cut.gains_db, af_db[:, 1])


def test_response_sidelobe_marker_prefers_local_peak() -> None:
    angles = np.array([-4.0, -3.0, -2.0, -1.0, 0.0, 1.0, 2.0, 3.0, 4.0])
    gains_db = np.array([-18.0, -10.0, -12.0, -14.0, 0.0, -15.0, -13.0, -11.0, -18.0])

    index, is_peak = _response_sidelobe_marker(angles, gains_db, guard=1.5)

    assert is_peak
    assert angles[index] == -3.0


def test_response_sidelobe_marker_rejects_low_clearance_peak() -> None:
    angles = np.array([-3.0, -2.0, -1.0, 0.0, 1.0, 2.0, 3.0])
    gains_db = np.array([-18.0, -10.0, -10.2, 0.0, -10.2, -10.0, -18.0])

    index, is_peak = _response_sidelobe_marker(angles, gains_db, guard=1.5)

    assert not is_peak
    assert angles[index] == -2.0


def test_response_sidelobe_marker_marks_fallback_when_no_peak_exists() -> None:
    angles = np.array([-3.0, -2.0, -1.0, 0.0, 1.0, 2.0, 3.0])
    gains_db = np.array([-12.0, -8.0, -3.0, 0.0, -3.0, -8.0, -12.0])

    index, is_peak = _response_sidelobe_marker(angles, gains_db, guard=1.5)

    assert not is_peak
    assert angles[index] == -2.0
