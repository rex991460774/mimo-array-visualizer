from __future__ import annotations

import numpy as np

from virtual_array.analysis import calculate_metrics_and_psf
from virtual_array.element_pattern import (
    ElementPattern,
    format_pattern_cut_metrics,
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
