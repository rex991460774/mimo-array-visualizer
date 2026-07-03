from __future__ import annotations

import numpy as np
import pytest

from virtual_array.analysis import calculate_metrics_and_psf, dbf_azimuth_spectrum
from virtual_array.element_pattern import (
    PATTERN_KIND_PHASE,
    PATTERN_PLANE_HORIZONTAL,
    ChannelPatternSet,
    ElementPattern,
    PatternSeries,
    format_pattern_cut_metrics,
    load_hfss_summary_pattern,
    load_element_pattern,
    pattern_cut_metrics,
)
from virtual_array.geometry import AntennaArray


def test_loads_hfss_realized_gain_eh_plane_csv(tmp_path) -> None:
    csv_path = tmp_path / "pattern.csv"
    csv_path.write_text(
        '"Theta [deg]","dB(RealizedGainTotal) [] - Freq=\'77GHz\' Phi=\'0deg\'",'
        '"dB(RealizedGainTotal)_1 [] - Freq=\'77GHz\' Phi=\'90deg\'"\n'
        "-1,-10,-20\n"
        "0,0,-5\n"
        "1,-10,-20\n",
        encoding="utf-8",
    )

    pattern = load_element_pattern(csv_path)

    assert pattern.angle_column == "Theta [deg]"
    assert "Phi='90deg'" in pattern.horizontal_column
    assert pattern.elevation_column is not None
    assert "Phi='0deg'" in pattern.elevation_column
    assert np.array_equal(pattern.angles_deg, np.array([-1.0, 0.0, 1.0]))
    assert np.array_equal(pattern.horizontal_gain_db, np.array([-20.0, -5.0, -20.0]))
    assert np.array_equal(pattern.elevation_gain_db, np.array([-10.0, 0.0, -10.0]))


def test_loads_hfss_summary_columns_in_tx_rx_order_with_zero_phase_calibration(
    tmp_path,
) -> None:
    csv_path = tmp_path / "phase-summary.csv"
    csv_path.write_text(
        '"Freq [GHz]","Phi [deg]","Theta [deg]","cang_deg(rETheta) [deg]",'
        '"cang_deg(rETheta)_1 [deg]","cang_deg(rETheta)_2 [deg]",'
        '"cang_deg(rETheta)_3 [deg]"\n'
        "24.125,90,-1,10,20,30,40\n"
        "24.125,90,0,11,21,31,41\n",
        encoding="utf-8",
    )

    series_by_channel = load_hfss_summary_pattern(
        csv_path,
        ["Tx1", "Tx2", "Rx1", "Rx2"],
        value_kind=PATTERN_KIND_PHASE,
    )

    assert list(series_by_channel) == ["Tx1", "Tx2", "Rx1", "Rx2"]
    assert np.allclose(series_by_channel["Tx1"].values, np.array([-1.0, 0.0]))
    assert np.allclose(series_by_channel["Tx2"].values, np.array([-1.0, 0.0]))
    assert np.allclose(series_by_channel["Rx1"].values, np.array([-1.0, 0.0]))
    assert np.allclose(series_by_channel["Rx2"].values, np.array([-1.0, 0.0]))
    for series in series_by_channel.values():
        assert series.values_at(np.array([0.0]))[0] == pytest.approx(0.0)


def test_phase_series_unwraps_when_interpolating_across_wrap() -> None:
    phase_series = PatternSeries(
        name="phase",
        source_path="phase.csv",
        angle_column="Theta",
        value_column="phase",
        value_kind=PATTERN_KIND_PHASE,
        angles_deg=np.array([-1.0, 1.0]),
        values=np.array([179.0, -179.0]),
    )

    assert phase_series.values_at(np.array([0.0]))[0] == pytest.approx(180.0)


def test_pattern_series_rejects_angles_outside_csv_range() -> None:
    phase_series = PatternSeries(
        name="phase",
        source_path="phase.csv",
        angle_column="Theta",
        value_column="phase",
        value_kind=PATTERN_KIND_PHASE,
        angles_deg=np.array([-30.0, 30.0]),
        values=np.array([0.0, 0.0]),
    )

    with pytest.raises(ValueError, match="covers -30..30 deg"):
        phase_series.values_at(np.array([-90.0, 0.0, 90.0]))


def test_element_pattern_axes_can_be_swapped(tmp_path) -> None:
    csv_path = tmp_path / "pattern.csv"
    csv_path.write_text(
        "Theta [deg],Phi0,Phi90\n"
        "-1,-10,-20\n"
        "0,0,-5\n"
        "1,-10,-20\n",
        encoding="utf-8",
    )

    pattern = load_element_pattern(csv_path)
    swapped = pattern.swapped_axes()

    assert swapped.horizontal_column == pattern.elevation_column
    assert swapped.elevation_column == pattern.horizontal_column
    assert np.array_equal(swapped.horizontal_gain_db, pattern.elevation_gain_db)
    assert np.array_equal(swapped.elevation_gain_db, pattern.horizontal_gain_db)


def test_single_gain_column_is_reused_as_horizontal_only(tmp_path) -> None:
    csv_path = tmp_path / "pattern.csv"
    csv_path.write_text("Angle(deg),Gain(dBi)\n-90,-30\n0,0\n90,-30\n", encoding="utf-8")

    pattern = load_element_pattern(csv_path)

    assert pattern.horizontal_column == "Gain(dBi)"
    assert pattern.elevation_column is None
    assert pattern.normalized_horizontal_gain_db_at(np.array([0.0]))[0] == 0.0
    assert pattern.normalized_elevation_gain_db_at(np.array([90.0]))[0] == -30.0


def test_element_pattern_weights_array_factor_grid() -> None:
    array = AntennaArray.from_xy(tx_x=[0], tx_y=[0], rx_x=[0], rx_y=[0])
    pattern = ElementPattern(
        name="test",
        source_path="test.csv",
        angle_column="Angle",
        horizontal_column="Horizontal",
        elevation_column=None,
        angles_deg=np.array([-75.0, 0.0, 75.0]),
        horizontal_gain_db=np.array([-20.0, 0.0, -20.0]),
    )

    af_db, azimuths, elevations, _metrics = calculate_metrics_and_psf(
        array,
        tx_pattern=pattern,
    )

    center_el = int(np.argmin(np.abs(elevations)))
    center_az = int(np.argmin(np.abs(azimuths)))
    edge_az = int(np.argmax(azimuths))

    assert af_db[center_el, center_az] == 0.0
    assert af_db[center_el, edge_az] == -20.0


def test_physical_channel_phase_pattern_weights_virtual_channels() -> None:
    array = AntennaArray.from_xy(tx_x=[0], tx_y=[0], rx_x=[0, 1], rx_y=[0, 0])
    phase_series = PatternSeries(
        name="phase",
        source_path="phase.csv",
        angle_column="Theta",
        value_column="phase",
        value_kind=PATTERN_KIND_PHASE,
        angles_deg=np.array([-90.0, 0.0, 90.0]),
        values=np.array([180.0, 180.0, 180.0]),
    )
    channel_patterns = ChannelPatternSet()
    channel_patterns.set_series(
        "Rx2",
        PATTERN_KIND_PHASE,
        PATTERN_PLANE_HORIZONTAL,
        phase_series,
    )

    af_db, azimuths, elevations, _metrics = calculate_metrics_and_psf(
        array,
        channel_patterns=channel_patterns,
    )

    center_el = int(np.argmin(np.abs(elevations)))
    center_az = int(np.argmin(np.abs(azimuths)))

    assert af_db[center_el, center_az] < -100.0


def test_dbf_uses_channel_patterns_on_true_signal_not_scan_dictionary() -> None:
    array = AntennaArray.from_xy(tx_x=[0], tx_y=[0], rx_x=[0, 1], rx_y=[0, 0])
    phase_series = PatternSeries(
        name="phase",
        source_path="phase.csv",
        angle_column="Theta",
        value_column="phase",
        value_kind=PATTERN_KIND_PHASE,
        angles_deg=np.array([-90.0, 0.0, 90.0]),
        values=np.array([180.0, 180.0, 180.0]),
    )
    channel_patterns = ChannelPatternSet()
    channel_patterns.set_series(
        "Rx2",
        PATTERN_KIND_PHASE,
        PATTERN_PLANE_HORIZONTAL,
        phase_series,
    )

    angles, spectrum_db = dbf_azimuth_spectrum(
        array,
        true_angle_deg=0.0,
        angles_deg=np.array([-90.0, 0.0, 90.0]),
        channel_patterns=channel_patterns,
    )

    center_index = int(np.where(angles == 0.0)[0][0])
    assert spectrum_db[center_index] < -100.0
    assert np.max(spectrum_db) == pytest.approx(0.0)


def test_dbf_uses_hfss_phase_as_signal_without_extra_ideal_phase() -> None:
    array = AntennaArray.from_xy(
        tx_x=[0],
        tx_y=[0],
        rx_x=[0, 1, 2],
        rx_y=[0, 0, 0],
    )
    angles_deg = np.array([-30.0, 0.0, 30.0])
    channel_patterns = ChannelPatternSet()
    for rx_name, position in (("Rx2", 1.0), ("Rx3", 2.0)):
        phase_series = PatternSeries(
            name=f"{rx_name}-phase",
            source_path=f"{rx_name}.csv",
            angle_column="Theta",
            value_column="phase",
            value_kind=PATTERN_KIND_PHASE,
            angles_deg=angles_deg,
            values=180.0 * position * np.sin(np.radians(angles_deg)),
        )
        channel_patterns.set_series(
            rx_name,
            PATTERN_KIND_PHASE,
            PATTERN_PLANE_HORIZONTAL,
            phase_series,
        )

    scan_angles, spectrum_db = dbf_azimuth_spectrum(
        array,
        true_angle_deg=30.0,
        angles_deg=angles_deg,
        channel_patterns=channel_patterns,
    )

    peak_index = int(np.argmax(spectrum_db))
    center_index = int(np.where(scan_angles == 0.0)[0][0])
    assert scan_angles[peak_index] == pytest.approx(30.0)
    assert spectrum_db[peak_index] == pytest.approx(0.0)
    assert spectrum_db[center_index] < -3.0


def test_dbf_auto_selects_steering_sign_for_hfss_phase_convention() -> None:
    array = AntennaArray.from_xy(
        tx_x=[0],
        tx_y=[0],
        rx_x=[0, 1, 2],
        rx_y=[0, 0, 0],
    )
    angles_deg = np.array([-30.0, 0.0, 30.0])
    channel_patterns = ChannelPatternSet()
    for rx_name, position in (("Rx2", 1.0), ("Rx3", 2.0)):
        phase_series = PatternSeries(
            name=f"{rx_name}-phase",
            source_path=f"{rx_name}.csv",
            angle_column="Theta",
            value_column="phase",
            value_kind=PATTERN_KIND_PHASE,
            angles_deg=angles_deg,
            values=-180.0 * position * np.sin(np.radians(angles_deg)),
        )
        channel_patterns.set_series(
            rx_name,
            PATTERN_KIND_PHASE,
            PATTERN_PLANE_HORIZONTAL,
            phase_series,
        )

    scan_angles, spectrum_db = dbf_azimuth_spectrum(
        array,
        true_angle_deg=30.0,
        angles_deg=angles_deg,
        channel_patterns=channel_patterns,
    )

    peak_index = int(np.argmax(spectrum_db))
    assert scan_angles[peak_index] == pytest.approx(30.0)


def test_pattern_cut_metrics_reports_peak_and_beamwidths() -> None:
    angles = np.array([-4.0, -2.0, 0.0, 2.0, 4.0])
    gain = np.array([-8.0, -3.0, 1.0, -3.0, -8.0])

    metrics = pattern_cut_metrics(angles, gain)

    assert metrics.peak_angle_deg == 0.0
    assert metrics.peak_gain_dbi == 1.0
    assert metrics.beamwidth_3db_deg == 3.0
    assert metrics.beamwidth_6db_deg == 5.6
    assert format_pattern_cut_metrics(metrics) == (
        "Peak 1.00 dBi @ 0.0° | 3dB BW 3.0° | 6dB BW 5.6°"
    )


def test_pattern_cut_metrics_returns_none_for_open_beamwidth() -> None:
    angles = np.array([-1.0, 0.0, 1.0])
    gain = np.array([-1.0, 0.0, -1.0])

    metrics = pattern_cut_metrics(angles, gain)

    assert metrics.beamwidth_3db_deg is None
    assert metrics.beamwidth_6db_deg is None
    assert "3dB BW N/A" in format_pattern_cut_metrics(metrics)
