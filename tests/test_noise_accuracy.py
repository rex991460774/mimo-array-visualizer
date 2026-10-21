from __future__ import annotations

import math

import numpy as np
import pytest

from virtual_array.analysis import (
    EvaluationSettings,
    dbf_noise_accuracy,
    evaluate_dbf_axis,
    noise_true_angles,
)
from virtual_array.examples.case4_5tx7rx_sel import build_array
from virtual_array.geometry import AntennaArray, ArrayPoint


def scaled(array: AntennaArray, factor: float) -> AntennaArray:
    def scale(points: list[ArrayPoint]) -> list[ArrayPoint]:
        return [ArrayPoint(name=p.name, x=p.x * factor, y=p.y * factor) for p in points]

    return AntennaArray(tx=scale(array.tx), rx=scale(array.rx))


def test_noise_true_angles_span_fov_and_include_boresight() -> None:
    angles = noise_true_angles((-75, 75))
    assert angles[0] == -75 and angles[-1] == 75 and 0 in angles
    assert np.allclose(np.diff(angles), 5)
    asymmetric = noise_true_angles((-60, 45))
    assert 0 in asymmetric and asymmetric[0] >= -60 and asymmetric[-1] <= 45
    assert np.allclose(noise_true_angles((-15, 15)), np.arange(-15, 16))


def test_monte_carlo_spread_matches_cramer_rao_bound() -> None:
    result = dbf_noise_accuracy(build_array(), "azimuth", EvaluationSettings(), snr_db=10.0)
    assert not result.ambiguous.any()
    assert np.all(result.outlier_rate == 0.0)
    # Ideal dictionary: the DBF peak is the ML estimate, so its spread approaches the CRB.
    ratio = result.std_deg / result.crb_deg
    assert np.all((ratio > 0.8) & (ratio < 1.25)), ratio
    assert np.max(np.abs(result.bias_deg)) < 0.3 * np.max(result.crb_deg)
    # The bound grows off boresight roughly as 1/cos(θ).
    boresight = result.crb_deg[result.true_angles_deg == 0][0]
    edge = result.crb_deg[result.true_angles_deg == 60][0]
    assert edge / boresight == pytest.approx(1 / math.cos(math.radians(60)), rel=0.05)


def test_crb_scales_with_snr() -> None:
    settings = EvaluationSettings()
    low = dbf_noise_accuracy(build_array(), "elevation", settings, snr_db=10.0, trials=10)
    high = dbf_noise_accuracy(build_array(), "elevation", settings, snr_db=30.0, trials=10)
    assert np.allclose(low.crb_deg / high.crb_deg, 10.0, rtol=1e-6)


def test_snr_sweep_finds_outlier_threshold() -> None:
    result = dbf_noise_accuracy(build_array(), "azimuth", EvaluationSettings(), snr_db=-15.0)
    assert result.outlier_rate.max() > 0.5  # far below threshold: peaks jump to sidelobes
    rates = result.sweep_max_outlier_rate
    assert rates[0] > 0.5 and rates[-1] == 0.0
    threshold = result.threshold_snr_db
    assert threshold is not None and -15.0 < threshold < 10.0
    above = result.sweep_snr_db >= threshold
    assert np.all(rates[above] <= result.outlier_limit)
    assert rates[result.sweep_snr_db == threshold - 1][0] > result.outlier_limit


def test_results_are_reproducible() -> None:
    settings = EvaluationSettings()
    first = dbf_noise_accuracy(build_array(), "elevation", settings, snr_db=0.0, trials=50)
    second = dbf_noise_accuracy(build_array(), "elevation", settings, snr_db=0.0, trials=50)
    assert np.array_equal(first.rmse_deg, second.rmse_deg, equal_nan=True)
    assert np.array_equal(first.sweep_max_outlier_rate, second.sweep_max_outlier_rate)


def test_dictionary_fixed_at_design_frequency_scales_estimates() -> None:
    design = build_array()
    operating = scaled(design, 81.0 / 77.0)
    settings = EvaluationSettings(azimuth_fov_deg=(-40.0, 40.0))
    tracking = evaluate_dbf_axis(operating, "azimuth", settings)
    assert tracking.metrics.focus_max_abs_error == pytest.approx(0.0, abs=1e-3)
    fixed = evaluate_dbf_axis(operating, "azimuth", settings, dictionary_array=design)
    estimated = fixed.frame_series.estimated_angles_deg
    # sin(θ_est) = sin(θ) · f / f_design for a geometric dictionary at the design frequency.
    expected = np.degrees(np.arcsin(np.sin(np.radians(fixed.true_angles_deg)) * 81.0 / 77.0))
    assert np.allclose(estimated, expected, atol=0.01)
    assert fixed.metrics.focus_max_abs_error > 1.5


def test_dictionary_array_must_match_channels() -> None:
    array = build_array()
    smaller = AntennaArray(tx=array.tx[:-1], rx=array.rx)
    with pytest.raises(ValueError, match="same Tx/Rx channels"):
        evaluate_dbf_axis(array, "azimuth", EvaluationSettings(), dictionary_array=smaller)
