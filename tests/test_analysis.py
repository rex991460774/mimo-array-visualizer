from __future__ import annotations

import numpy as np
import pytest

from virtual_array.analysis import (
    AF_GRID_SIZE,
    DBF_SCAN_GRID_SIZE,
    calculate_metrics_and_psf,
    dbf_angle_metrics_from_spectra,
    dbf_2d_spectrum,
    dbf_2d_normalization_reference,
    dbf_azimuth_angle_metrics,
    dbf_azimuth_spectrum,
    dbf_azimuth_spectrum_bank,
    dbf_elevation_spectrum,
    dbf_elevation_spectrum_bank,
    estimate_resolution,
)
from virtual_array.examples.case4_5tx7rx_sel import build_array
from virtual_array.element_pattern import (
    PATTERN_KIND_AMPLITUDE,
    PATTERN_PLANE_HORIZONTAL,
    ChannelPatternSet,
    PatternSeries,
)
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


def test_dbf_azimuth_spectrum_defaults_to_full_scan_range() -> None:
    array = AntennaArray.from_xy(tx_x=[0], tx_y=[0], rx_x=[0, 1], rx_y=[0, 0])

    angles, spectrum_db = dbf_azimuth_spectrum(array)

    assert len(angles) == DBF_SCAN_GRID_SIZE
    assert angles[0] == -90.0
    assert angles[-1] == 90.0
    assert spectrum_db[int(np.argmin(np.abs(angles)))] == pytest.approx(0.0)
    assert spectrum_db[0] < -100.0
    assert spectrum_db[-1] < -100.0


def test_dbf_azimuth_spectrum_matches_psf_azimuth_cut() -> None:
    array = AntennaArray.from_xy(tx_x=[0], tx_y=[0], rx_x=[0, 1, 2], rx_y=[0, 0, 0])
    af_db, azimuths, elevations, _metrics = calculate_metrics_and_psf(array)

    dbf_angles, dbf_db = dbf_azimuth_spectrum(array, angles_deg=azimuths)
    el0_index = int(np.argmin(np.abs(elevations)))

    assert np.array_equal(dbf_angles, azimuths)
    assert np.allclose(dbf_db, af_db[el0_index, :])


def test_dbf_azimuth_spectrum_bank_builds_181_true_angle_spectra() -> None:
    array = AntennaArray.from_xy(
        tx_x=[0],
        tx_y=[0],
        rx_x=[0, 1, 2, 3],
        rx_y=[0, 0, 0, 0],
    )

    true_angles, scan_angles, spectra_db = dbf_azimuth_spectrum_bank(array)

    assert len(true_angles) == DBF_SCAN_GRID_SIZE == 181
    assert len(scan_angles) == DBF_SCAN_GRID_SIZE == 181
    assert true_angles[0] == -90.0
    assert true_angles[1] == -89.0
    assert true_angles[-1] == 90.0
    assert spectra_db.shape == (181, 181)
    for index in (0, 30, 90, 150, 179):
        peak_index = int(np.argmax(spectra_db[index]))
        assert scan_angles[peak_index] == pytest.approx(true_angles[index])
        assert spectra_db[index, peak_index] == pytest.approx(0.0)


def test_dbf_spectrum_bank_uses_per_frame_correlation_normalization() -> None:
    array = AntennaArray.from_xy(tx_x=[0], tx_y=[0], rx_x=[0], rx_y=[0])
    amplitude_series = PatternSeries(
        name="amp",
        source_path="amp.csv",
        angle_column="Theta",
        value_column="amp",
        value_kind=PATTERN_KIND_AMPLITUDE,
        angles_deg=np.array([-90.0, 0.0, 90.0]),
        values=np.array([-20.0, 0.0, -20.0]),
    )
    channel_patterns = ChannelPatternSet()
    channel_patterns.set_series(
        "Rx1",
        PATTERN_KIND_AMPLITUDE,
        PATTERN_PLANE_HORIZONTAL,
        amplitude_series,
    )

    true_angles, _scan_angles, spectra_db = dbf_azimuth_spectrum_bank(
        array,
        true_angles_deg=np.array([-90.0, 0.0, 90.0]),
        scan_angles_deg=np.array([-90.0, 0.0, 90.0]),
        channel_patterns=channel_patterns,
    )

    assert np.array_equal(true_angles, np.array([-90.0, 0.0, 90.0]))
    assert np.max(spectra_db[1]) == pytest.approx(0.0)
    assert np.max(spectra_db[0]) == pytest.approx(0.0)
    assert np.max(spectra_db[2]) == pytest.approx(0.0)


def test_dbf_elevation_spectrum_matches_psf_elevation_cut() -> None:
    array = AntennaArray.from_xy(tx_x=[0], tx_y=[0], rx_x=[0, 0, 0], rx_y=[0, 1, 2])
    af_db, azimuths, elevations, _metrics = calculate_metrics_and_psf(array)

    dbf_angles, dbf_db = dbf_elevation_spectrum(array, angles_deg=elevations)
    az0_index = int(np.argmin(np.abs(azimuths)))

    assert np.array_equal(dbf_angles, elevations)
    assert np.allclose(dbf_db, af_db[:, az0_index])


def test_dbf_elevation_spectrum_bank_builds_181_true_angle_spectra() -> None:
    array = AntennaArray.from_xy(
        tx_x=[0],
        tx_y=[0],
        rx_x=[0, 0, 0, 0],
        rx_y=[0, 1, 2, 3],
    )

    true_angles, scan_angles, spectra_db = dbf_elevation_spectrum_bank(array)

    assert len(true_angles) == DBF_SCAN_GRID_SIZE == 181
    assert len(scan_angles) == DBF_SCAN_GRID_SIZE == 181
    assert true_angles[0] == -90.0
    assert true_angles[1] == -89.0
    assert true_angles[-1] == 90.0
    assert spectra_db.shape == (181, 181)
    for index in (0, 30, 90, 150, 179):
        peak_index = int(np.argmax(spectra_db[index]))
        assert scan_angles[peak_index] == pytest.approx(true_angles[index])
        assert spectra_db[index, peak_index] == pytest.approx(0.0)


def test_dbf_2d_spectrum_peaks_at_true_azimuth_and_elevation() -> None:
    array = AntennaArray.from_xy(
        tx_x=[0],
        tx_y=[0],
        rx_x=[0, 1, 0, 1],
        rx_y=[0, 0, 1, 1],
    )
    scan_azimuths = np.array([-20.0, 0.0, 20.0])
    scan_elevations = np.array([-10.0, 0.0, 10.0])

    azimuths, elevations, spectrum_db = dbf_2d_spectrum(
        array,
        true_azimuth_deg=20.0,
        true_elevation_deg=10.0,
        scan_azimuths_deg=scan_azimuths,
        scan_elevations_deg=scan_elevations,
    )

    peak_el_index, peak_az_index = np.unravel_index(
        int(np.argmax(spectrum_db)), spectrum_db.shape
    )
    assert np.array_equal(azimuths, scan_azimuths)
    assert np.array_equal(elevations, scan_elevations)
    assert spectrum_db.shape == (3, 3)
    assert azimuths[peak_az_index] == pytest.approx(20.0)
    assert elevations[peak_el_index] == pytest.approx(10.0)
    assert spectrum_db[peak_el_index, peak_az_index] == pytest.approx(0.0)


def test_dbf_2d_spectrum_uses_correlation_normalization() -> None:
    array = AntennaArray.from_xy(tx_x=[0], tx_y=[0], rx_x=[0], rx_y=[0])
    amplitude_series = PatternSeries(
        name="amp",
        source_path="amp.csv",
        angle_column="Theta",
        value_column="amp",
        value_kind=PATTERN_KIND_AMPLITUDE,
        angles_deg=np.array([-90.0, 0.0, 90.0]),
        values=np.array([-20.0, 0.0, -20.0]),
    )
    channel_patterns = ChannelPatternSet()
    channel_patterns.set_series(
        "Rx1",
        PATTERN_KIND_AMPLITUDE,
        PATTERN_PLANE_HORIZONTAL,
        amplitude_series,
    )
    reference = dbf_2d_normalization_reference(
        array,
        scan_azimuths_deg=np.array([-90.0, 0.0, 90.0]),
        scan_elevations_deg=np.array([0.0]),
        true_azimuths_deg=np.array([-90.0, 0.0, 90.0]),
        true_elevations_deg=np.array([0.0]),
        channel_patterns=channel_patterns,
    )

    _azimuths, _elevations, spectrum_db = dbf_2d_spectrum(
        array,
        true_azimuth_deg=-90.0,
        true_elevation_deg=0.0,
        scan_azimuths_deg=np.array([-90.0, 0.0, 90.0]),
        scan_elevations_deg=np.array([0.0]),
        channel_patterns=channel_patterns,
        normalization_max=reference,
    )

    assert reference == pytest.approx(1.0)
    assert np.max(spectrum_db) == pytest.approx(0.0)


def test_dbf_angle_metrics_report_no_fold_range_for_ideal_linear_array() -> None:
    array = AntennaArray.from_xy(
        tx_x=[0],
        tx_y=[0],
        rx_x=list(range(8)),
        rx_y=[0] * 8,
    )

    metrics = dbf_azimuth_angle_metrics(array)

    assert metrics.no_fold_left <= -70.0
    assert metrics.no_fold_right >= 70.0
    assert metrics.focus_max_abs_error == pytest.approx(0.0)


def test_dbf_angle_metrics_truncate_when_competitor_peak_is_too_close() -> None:
    true_angles = np.array([-4.0, -2.0, 0.0, 2.0, 4.0])
    scan_angles = np.array([-4.0, -2.0, 0.0, 2.0, 4.0])
    spectra_db = np.array(
        [
            [0.0, -20.0, -25.0, -25.0, -25.0],
            [-20.0, 0.0, -20.0, -20.0, -20.0],
            [-20.0, -20.0, 0.0, -20.0, -20.0],
            [-0.2, -20.0, -20.0, 0.0, -20.0],
            [-25.0, -25.0, -25.0, -20.0, 0.0],
        ]
    )

    metrics = dbf_angle_metrics_from_spectra(true_angles, scan_angles, spectra_db)

    assert metrics.no_fold_left == pytest.approx(-2.0)
    assert metrics.no_fold_right == pytest.approx(0.0)
    assert metrics.positive_cut_reason == "竞争峰模糊"


def test_dbf_angle_metrics_accept_custom_competitor_margin_threshold() -> None:
    true_angles = np.array([-2.0, 0.0, 2.0])
    scan_angles = np.array([-4.0, -2.0, 0.0, 2.0, 4.0])
    spectra_db = np.array(
        [
            [-20.0, 0.0, -20.0, -20.0, -20.0],
            [-0.2, -20.0, 0.0, -20.0, -20.0],
            [-20.0, -20.0, -20.0, 0.0, -20.0],
        ]
    )

    strict = dbf_angle_metrics_from_spectra(
        true_angles,
        scan_angles,
        spectra_db,
        ambiguity_margin_db=0.5,
    )
    relaxed = dbf_angle_metrics_from_spectra(
        true_angles,
        scan_angles,
        spectra_db,
        ambiguity_margin_db=0.1,
    )

    assert strict.no_fold_left == pytest.approx(0.0)
    assert relaxed.no_fold_left == pytest.approx(-2.0)


def test_dbf_angle_metrics_treat_flat_spectrum_as_unusable() -> None:
    true_angles = np.array([-2.0, 0.0, 2.0])
    scan_angles = np.linspace(-90.0, 90.0, DBF_SCAN_GRID_SIZE)
    spectra_db = np.zeros((3, DBF_SCAN_GRID_SIZE), dtype=float)

    metrics = dbf_angle_metrics_from_spectra(true_angles, scan_angles, spectra_db)

    assert metrics.no_fold_left == pytest.approx(0.0)
    assert metrics.no_fold_right == pytest.approx(0.0)
    assert metrics.negative_cut_reason == "边界受限"
    assert metrics.positive_cut_reason == "边界受限"


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

    assert az_cut.label == "方位"
    assert np.array_equal(az_cut.angles, azimuths)
    assert np.array_equal(az_cut.gains_db, af_db[1, :])
    assert el_cut.label == "俯仰"
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
