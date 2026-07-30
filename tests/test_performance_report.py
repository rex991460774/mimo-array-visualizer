from __future__ import annotations

import csv
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

import virtual_array.performance_report as performance_report_module
from virtual_array.analysis import DBF_QUALITY_OK, DbfAngleFrameSeries
from virtual_array.dbf_dictionary import DbfDictionaryConfig
from virtual_array.element_pattern import (
    PATTERN_KIND_PHASE,
    PATTERN_PLANE_ELEVATION,
    PATTERN_PLANE_HORIZONTAL,
    ChannelPatternSet,
    PatternSeries,
)
from virtual_array.geometry import AntennaArray
from virtual_array.performance_report import (
    AngleErrorImageOptions,
    AngleRange,
    PerformanceReportOptions,
    PerformanceReportSnapshot,
    angle_error_data_range,
    angle_error_display_limit_deg,
    dbf_spectrum_magnitude_from_db,
    generate_angle_error_image,
    generate_performance_report,
    hold_curve_frame_count,
    select_dbf_spectrum_frames,
    summarize_dbf_focus_range,
)


def _angle_error_snapshot(
    channel_patterns: ChannelPatternSet | None = None,
) -> PerformanceReportSnapshot:
    return PerformanceReportSnapshot(
        array=AntennaArray.from_xy(
            tx_x=[0.0],
            tx_y=[0.0],
            rx_x=[0.0, 1.0],
            rx_y=[0.0, 0.0],
        ),
        frequency_ghz=77.0,
        ambiguity_margin_db=0.5,
        dbf_dictionary=DbfDictionaryConfig(),
        element_pattern=None,
        channel_patterns=channel_patterns or ChannelPatternSet(),
        current_config={"version": 1, "unit": "lambda"},
        app_version="test",
        created_at=datetime.now().astimezone(),
    )


def _phase_series(name: str, start_deg: float, stop_deg: float) -> PatternSeries:
    return PatternSeries(
        name=name,
        source_path=f"{name}.csv",
        angle_column="Theta",
        value_column=name,
        value_kind=PATTERN_KIND_PHASE,
        angles_deg=np.array([start_deg, stop_deg]),
        values=np.zeros(2),
    )


def _angle_error_plot_axis_data() -> SimpleNamespace:
    true_angles = np.array([-90.0, -60.0, 0.0, 60.0, 90.0])
    errors = np.array([-180.0, 2.0, 0.0, 3.0, 180.0])
    series = DbfAngleFrameSeries(
        true_angles_deg=true_angles,
        estimated_angles_deg=true_angles + errors,
        errors_deg=errors,
        main_peak_db=np.zeros(5),
        competitor_peak_db=np.full(5, -3.0),
        peak_margins_db=np.full(5, 3.0),
        quality_flags=("边界受限", DBF_QUALITY_OK, DBF_QUALITY_OK, DBF_QUALITY_OK, "边界受限"),
    )
    return SimpleNamespace(
        axis="azimuth",
        frame_series=series,
        display_range=AngleRange(-90.0, 90.0),
        focus_range=AngleRange(-60.0, 60.0),
        angle_metrics=SimpleNamespace(no_fold_left=-60.0, no_fold_right=60.0),
        focus_summary=SimpleNamespace(
            bias_deg=0.0,
            rmse_deg=0.0,
            p95_abs_error_deg=3.0,
            max_abs_error_deg=3.0,
            reliable_count=3,
            frame_count=5,
            reliable_coverage_pct=60.0,
            within_error_limit_pct=60.0,
        ),
    )


def _figure_legend_labels(figure: object) -> list[str]:
    return [
        text.get_text()
        for legend in getattr(figure, "legends")
        for text in legend.get_texts()
    ]


def test_angle_range_is_inclusive_and_validated() -> None:
    angle_range = AngleRange(-1.0, 1.0)
    assert np.array_equal(
        angle_range.mask(np.array([-2.0, -1.0, 0.0, 1.0, 2.0])),
        np.array([False, True, True, True, False]),
    )
    assert angle_range.frame_count_1deg == 3

    with pytest.raises(ValueError, match="start"):
        AngleRange(2.0, -2.0)
    with pytest.raises(ValueError, match="-90"):
        AngleRange(-91.0, 0.0)


def test_select_dbf_spectrum_frames_keeps_every_selected_frame() -> None:
    true_angles = np.arange(-2.0, 3.0)
    scan_angles = np.array([-1.0, 0.0, 1.0])
    spectra = np.array(
        [
            [-5.0, -4.0, -3.0],
            [-4.0, -3.0, -2.0],
            [-3.0, -2.0, -1.0],
            [-2.0, -1.0, 0.0],
            [-1.0, 0.0, -1.0],
        ]
    )

    selection = select_dbf_spectrum_frames(
        true_angles,
        scan_angles,
        spectra,
        AngleRange(-1.0, 1.0),
    )

    assert np.array_equal(selection.frame_indices, np.array([1, 2, 3]))
    assert np.array_equal(selection.range_frame_indices, np.array([1, 2, 3]))
    assert np.array_equal(selection.true_angles_deg, np.array([-1.0, 0.0, 1.0]))
    assert np.array_equal(selection.spectra_db, spectra[1:4])
    assert np.array_equal(selection.max_hold_db, np.max(spectra[1:4], axis=0))
    assert selection.stride_frames == 1


def test_select_dbf_spectrum_frames_decimates_curves_but_not_max_hold() -> None:
    true_angles = np.arange(-2.0, 3.0)
    scan_angles = np.array([-1.0, 0.0, 1.0])
    spectra = np.array(
        [
            [-8.0, -8.0, -8.0],
            [-7.0, 0.0, -7.0],
            [-6.0, -6.0, -6.0],
            [0.0, -5.0, -5.0],
            [-4.0, -4.0, 0.0],
        ]
    )

    selection = select_dbf_spectrum_frames(
        true_angles,
        scan_angles,
        spectra,
        AngleRange(-2.0, 2.0),
        stride_frames=3,
    )

    assert np.array_equal(selection.range_frame_indices, np.arange(5))
    assert np.array_equal(selection.frame_indices, np.array([0, 3, 4]))
    assert np.array_equal(selection.true_angles_deg, np.array([-2.0, 1.0, 2.0]))
    assert np.array_equal(selection.spectra_db, spectra[[0, 3, 4]])
    assert np.array_equal(selection.max_hold_db, np.max(spectra, axis=0))
    assert selection.stride_frames == 3
    assert hold_curve_frame_count(5, 3) == 3
    assert hold_curve_frame_count(1, 180) == 1
    assert hold_curve_frame_count(3, 180) == 2


@pytest.mark.parametrize("stride", [0, -1, 1.5, 181, np.inf])
def test_hold_curve_stride_is_validated(stride: float) -> None:
    with pytest.raises(ValueError, match="Hold curve stride"):
        hold_curve_frame_count(5, stride)  # type: ignore[arg-type]


def test_report_options_require_at_least_one_spectrum_scale(tmp_path: Path) -> None:
    common = {
        "output_path": tmp_path / "report.pdf",
        "title": "Spectrum output options",
        "azimuth_focus": AngleRange(-10.0, 10.0),
        "elevation_focus": AngleRange(-5.0, 5.0),
        "azimuth_hold": AngleRange(-2.0, 2.0),
        "elevation_hold": AngleRange(-2.0, 2.0),
    }

    default_options = PerformanceReportOptions(**common)
    assert default_options.include_spectrum_db is True
    assert default_options.include_spectrum_magnitude is False
    assert default_options.azimuth_hold_stride_frames == 1
    assert default_options.elevation_hold_stride_frames == 1

    with pytest.raises(ValueError, match="At least one DBF spectrum"):
        PerformanceReportOptions(
            **common,
            include_spectrum_db=False,
            include_spectrum_magnitude=False,
        )

    with pytest.raises(ValueError, match="Azimuth Hold curve stride"):
        PerformanceReportOptions(
            **common,
            azimuth_hold_stride_frames=0,
        )


def test_dbf_spectrum_magnitude_is_derived_from_the_same_db_values() -> None:
    spectrum_db = np.array([1.0, 0.0, -6.0, -20.0, -80.0, -np.inf])

    magnitude = dbf_spectrum_magnitude_from_db(spectrum_db)

    assert np.array_equal(
        spectrum_db,
        np.array([1.0, 0.0, -6.0, -20.0, -80.0, -np.inf]),
    )
    assert magnitude == pytest.approx(
        np.array(
            [
                1.0,
                1.0,
                10.0 ** (-6.0 / 20.0),
                0.1,
                0.0001,
                0.0,
            ]
        )
    )


def test_angle_error_display_limit_uses_focus_range_and_preserves_detail() -> None:
    true_angles = np.array([-90.0, -60.0, 0.0, 60.0, 90.0])
    errors = np.array([-180.0, 2.0, 0.0, 3.0, 180.0])

    display_limit = angle_error_display_limit_deg(
        true_angles,
        errors,
        AngleRange(-60.0, 60.0),
        error_limit_deg=10.0,
    )

    assert display_limit == 15.0


def test_angle_error_display_limit_prefers_normal_range_over_folded_focus_data() -> None:
    true_angles = np.array([-90.0, -80.0, -30.0, 0.0, 45.0, 80.0, 90.0])
    errors = np.array([-170.0, 150.0, -3.0, 0.0, 4.0, -150.0, 170.0])

    display_limit = angle_error_display_limit_deg(
        true_angles,
        errors,
        AngleRange(-80.0, 80.0),
        error_limit_deg=10.0,
        normal_range=AngleRange(-30.0, 45.0),
    )

    assert display_limit == 15.0


def test_angle_error_display_limit_falls_back_and_keeps_large_threshold_visible() -> None:
    assert angle_error_display_limit_deg(
        np.array([-90.0, 0.0, 90.0]),
        np.array([-18.0, np.nan, 17.0]),
        AngleRange(0.0, 0.0),
        error_limit_deg=1.0,
    ) == 27.0
    assert angle_error_display_limit_deg(
        np.array([-1.0, 0.0, 1.0]),
        np.array([np.nan, np.inf, -np.inf]),
        AngleRange(-1.0, 1.0),
        error_limit_deg=1.0,
    ) == 2.0
    assert angle_error_display_limit_deg(
        np.array([-1.0, 0.0, 1.0]),
        np.array([0.0, 3.0, 0.0]),
        AngleRange(-1.0, 1.0),
        error_limit_deg=20.0,
    ) == 30.0


@pytest.mark.parametrize(
    ("errors", "error_limit", "expected"),
    [
        (np.array([2.0, 2.0, 2.0]), 1.0, 3.0),
        (np.array([-2.0, -2.0, -2.0]), 1.0, 3.0),
        (np.array([0.25, 1.2, 2.0]), 1.0, 3.0),
        (np.array([-0.25, -1.2, -2.0]), 1.0, 3.0),
        (np.array([-2.0, np.nan, np.inf]), 1.0, 3.0),
        (np.array([2.01]), 0.0, 4.0),
        (np.array([0.0, 0.0, 0.0]), 0.0, 1.0),
        (np.array([0.0, 0.0, 0.0]), 1.0, 2.0),
    ],
)
def test_angle_error_display_limit_uses_symmetric_finite_envelope_with_headroom(
    errors: np.ndarray,
    error_limit: float,
    expected: float,
) -> None:
    true_angles = np.linspace(-1.0, 1.0, len(errors))

    assert angle_error_display_limit_deg(
        true_angles,
        errors,
        AngleRange(-1.0, 1.0),
        error_limit_deg=error_limit,
        normal_range=AngleRange(-1.0, 1.0),
    ) == expected


def test_angle_error_display_limit_does_not_fall_back_when_normal_range_is_nonfinite() -> None:
    assert angle_error_display_limit_deg(
        np.array([-80.0, 0.0, 80.0]),
        np.array([150.0, np.nan, -150.0]),
        AngleRange(-80.0, 80.0),
        error_limit_deg=1.0,
        normal_range=AngleRange(0.0, 0.0),
    ) == 2.0


@pytest.mark.parametrize(
    ("true_angles", "expected"),
    [
        (np.array([-90.0, 0.0, 90.0]), AngleRange(-90.0, 90.0)),
        (np.array([-80.0, 0.0, 75.0]), AngleRange(-80.0, 75.0)),
        (np.array([-120.0, 0.0, 100.0]), AngleRange(-90.0, 90.0)),
    ],
)
def test_angle_error_data_range_uses_available_true_angle_extent(
    true_angles: np.ndarray,
    expected: AngleRange,
) -> None:
    assert angle_error_data_range(
        _angle_error_snapshot(),
        "azimuth",
        true_angles,
    ) == expected


@pytest.mark.parametrize(
    ("axis", "axis_plane", "other_plane"),
    [
        ("azimuth", PATTERN_PLANE_HORIZONTAL, PATTERN_PLANE_ELEVATION),
        ("elevation", PATTERN_PLANE_ELEVATION, PATTERN_PLANE_HORIZONTAL),
    ],
)
def test_angle_error_data_range_intersects_axis_phase_coverage(
    axis: str,
    axis_plane: str,
    other_plane: str,
) -> None:
    patterns = ChannelPatternSet()
    patterns.set_series(
        "Rx1",
        PATTERN_KIND_PHASE,
        axis_plane,
        _phase_series("wide", -85.0, 80.0),
    )
    patterns.set_series(
        "Rx2",
        PATTERN_KIND_PHASE,
        axis_plane,
        _phase_series("narrow", -70.0, 75.0),
    )
    # The orthogonal plane is always queried at zero for a 1D cut and must not
    # incorrectly shrink this axis's true-angle range.
    patterns.set_series(
        "Rx1",
        PATTERN_KIND_PHASE,
        other_plane,
        _phase_series("orthogonal", -5.0, 5.0),
    )

    result = angle_error_data_range(
        _angle_error_snapshot(patterns),
        axis,
        np.array([-90.0, 0.0, 90.0]),
    )

    assert result == AngleRange(-70.0, 75.0)


def test_generate_angle_error_image_writes_png_atomically(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    output_path = tmp_path / "report-output" / "angle-error.png"
    options = AngleErrorImageOptions(output_path=output_path)
    computed_axes = object()
    compute_calls: list[tuple[tuple[object, ...], dict[str, object]]] = []
    figure_calls: list[tuple[tuple[object, ...], dict[str, object]]] = []
    replace_calls: list[tuple[Path, Path]] = []

    def fake_compute(*args: object, **kwargs: object) -> object:
        compute_calls.append((args, kwargs))
        return computed_axes

    def fake_figure(*args: object, **kwargs: object):
        figure_calls.append((args, kwargs))
        figure = performance_report_module.Figure(figsize=(2.0, 1.0), dpi=72)
        figure.subplots().plot([-1.0, 1.0], [0.0, 0.0])
        return figure

    real_replace = performance_report_module.os.replace

    def capture_replace(source: str | Path, target: str | Path) -> None:
        replace_calls.append((Path(source), Path(target)))
        real_replace(source, target)

    monkeypatch.setattr(performance_report_module, "_compute_angle_error_axes", fake_compute)
    monkeypatch.setattr(performance_report_module, "_angle_error_image_figure", fake_figure)
    monkeypatch.setattr(performance_report_module.os, "replace", capture_replace)

    artifacts = generate_angle_error_image(_angle_error_snapshot(), options)
    resolved_output = output_path.resolve()

    assert options.error_limit_deg == 1.0
    assert options.language == "zh"
    assert artifacts.png_path == resolved_output
    assert resolved_output.read_bytes().startswith(b"\x89PNG\r\n\x1a\n")
    assert len(compute_calls) == 1
    assert len(figure_calls) == 1
    assert replace_calls and replace_calls[-1][1] == resolved_output
    temporary_path = replace_calls[-1][0]
    assert temporary_path != resolved_output
    assert temporary_path.parent == resolved_output.parent
    assert not temporary_path.exists()


def test_standalone_angle_error_figure_has_only_primary_legend_and_no_scale_note(
    tmp_path: Path,
) -> None:
    axis_data = _angle_error_plot_axis_data()
    figure = performance_report_module._angle_error_image_figure(
        _angle_error_snapshot(),
        AngleErrorImageOptions(
            output_path=tmp_path / "angle-error.png",
            error_limit_deg=10.0,
            language="en",
        ),
        (axis_data,),
    )

    plot_axis = figure.axes[0]
    main_line = next(
        line for line in plot_axis.lines if line.get_label() == "Angle-error curve"
    )
    plotted_errors = np.asarray(main_line.get_ydata(), dtype=float)

    assert plot_axis.get_ylim() == pytest.approx((-15.0, 15.0))
    assert np.all(np.isfinite(plotted_errors))
    assert np.array_equal(plotted_errors, axis_data.frame_series.errors_deg)
    assert np.array_equal(main_line.get_xdata(), axis_data.frame_series.true_angles_deg)
    assert main_line.get_color() == "#2563a9"
    assert main_line.get_marker() == "o"
    assert len(plot_axis.collections) == 0
    assert len(plot_axis.patches) == 0
    assert _figure_legend_labels(figure) == [
        "Angle-error curve",
        "Error limit ±10 deg",
    ]
    assert not any(
        "Y-axis scaled" in text.get_text()
        for plot_axis in figure.axes
        for text in plot_axis.texts
    )


def test_angle_error_figure_applies_normal_scale_and_explains_clipping(tmp_path: Path) -> None:
    options = PerformanceReportOptions(
        output_path=tmp_path / "angle-error-scale.pdf",
        title="Angle error scale",
        azimuth_focus=AngleRange(-60.0, 60.0),
        elevation_focus=AngleRange(-15.0, 15.0),
        azimuth_hold=AngleRange(-60.0, 60.0),
        elevation_hold=AngleRange(-15.0, 15.0),
        error_limit_deg=10.0,
        language="en",
    )
    axis_data = _angle_error_plot_axis_data()

    figure = performance_report_module._angle_error_figure(
        _angle_error_snapshot(),
        options,
        SimpleNamespace(axes=(axis_data,)),
    )

    assert figure.axes[0].get_ylim() == pytest.approx((-15.0, 15.0))
    report_main_line = next(
        line
        for line in figure.axes[0].lines
        if line.get_label() == "Angle-error curve"
    )
    report_errors = np.asarray(report_main_line.get_ydata(), dtype=float)
    assert np.isnan(report_errors[[0, -1]]).all()
    assert np.array_equal(report_errors[1:-1], axis_data.frame_series.errors_deg[1:-1])
    assert len(figure.axes[0].collections) == 1
    assert {patch.get_label() for patch in figure.axes[0].patches} == {
        "Focus range",
        "No-fold range",
    }
    legend_labels = _figure_legend_labels(figure)
    assert "No-fold range" in legend_labels
    assert "Unreliable frame" in legend_labels
    assert any(
        "Y-axis scaled to the no-fold range" in " ".join(text.get_text().split())
        for text in figure.axes[0].texts
    )
    assert "无折叠正常范围缩放" in performance_report_module._label(
        "zh", "normal_scaled_y_axis_note"
    )
    assert "非折り返し範囲" in performance_report_module._label(
        "ja", "normal_scaled_y_axis_note"
    )


def test_magnitude_hold_plot_does_not_apply_the_db_display_floor(
    tmp_path: Path,
) -> None:
    selection = select_dbf_spectrum_frames(
        np.array([0.0]),
        np.array([-1.0, 0.0, 1.0]),
        np.array([[-80.0, 0.0, -20.0]]),
        AngleRange(0.0, 0.0),
    )
    options = PerformanceReportOptions(
        output_path=tmp_path / "magnitude.pdf",
        title="Magnitude floor regression",
        azimuth_focus=AngleRange(0.0, 0.0),
        elevation_focus=AngleRange(0.0, 0.0),
        azimuth_hold=AngleRange(0.0, 0.0),
        elevation_hold=AngleRange(0.0, 0.0),
        spectrum_floor_db=-40.0,
        include_spectrum_db=False,
        include_spectrum_magnitude=True,
        language="en",
    )
    axis_data = SimpleNamespace(
        axis="azimuth",
        hold_selection=selection,
        hold_range=AngleRange(0.0, 0.0),
        focus_summary=SimpleNamespace(worst_true_angle_deg=0.0),
    )

    figure = performance_report_module._hold_figure(
        SimpleNamespace(),
        options,
        axis_data,
        spectrum_scale="magnitude",
    )

    assert len(figure.axes) == 1
    frame_segments = figure.axes[0].collections[0].get_segments()
    assert frame_segments[0][:, 1] == pytest.approx(np.array([0.0001, 1.0, 0.1]))


def test_hold_plot_decimates_only_curves_and_does_not_fake_worst_highlight(
    tmp_path: Path,
) -> None:
    true_angles = np.arange(-2.0, 3.0)
    scan_angles = np.array([-1.0, 0.0, 1.0])
    spectra = np.array(
        [
            [-8.0, -8.0, -8.0],
            [-7.0, 0.0, -7.0],
            [-6.0, -6.0, -6.0],
            [0.0, -5.0, -5.0],
            [-4.0, -4.0, 0.0],
        ]
    )
    selection = select_dbf_spectrum_frames(
        true_angles,
        scan_angles,
        spectra,
        AngleRange(-2.0, 2.0),
        stride_frames=3,
    )
    options = PerformanceReportOptions(
        output_path=tmp_path / "decimated.pdf",
        title="Decimated Hold",
        azimuth_focus=AngleRange(-2.0, 2.0),
        elevation_focus=AngleRange(-2.0, 2.0),
        azimuth_hold=AngleRange(-2.0, 2.0),
        elevation_hold=AngleRange(-2.0, 2.0),
        azimuth_hold_stride_frames=3,
        language="en",
    )
    axis_data = SimpleNamespace(
        axis="azimuth",
        hold_selection=selection,
        hold_range=AngleRange(-2.0, 2.0),
        focus_summary=SimpleNamespace(worst_true_angle_deg=-1.0),
    )

    figure = performance_report_module._hold_figure(
        SimpleNamespace(),
        options,
        axis_data,
        spectrum_scale="db",
    )

    plot_axis = figure.axes[0]
    assert len(plot_axis.collections[0].get_segments()) == 3
    assert plot_axis.lines[0].get_ydata() == pytest.approx(np.max(spectra, axis=0))
    assert len(plot_axis.lines) == 4
    footer = " ".join(text.get_text() for text in figure.texts)
    assert "5 range frames" in footer
    assert "curve interval: 3° (3 frames)" in footer
    assert "3 plotted curves" in footer
    assert "Max-hold uses all in-range frames" in footer


def test_summarize_dbf_focus_range_reports_error_and_reliability() -> None:
    series = DbfAngleFrameSeries(
        true_angles_deg=np.array([-2.0, -1.0, 0.0, 1.0, 2.0]),
        estimated_angles_deg=np.array([-1.0, -1.0, 0.5, 2.0, 4.0]),
        errors_deg=np.array([1.0, 0.0, 0.5, 1.0, 2.0]),
        main_peak_db=np.zeros(5),
        competitor_peak_db=np.array([-3.0, -2.0, -1.0, -0.2, -4.0]),
        peak_margins_db=np.array([3.0, 2.0, 1.0, 0.2, 4.0]),
        quality_flags=(DBF_QUALITY_OK, DBF_QUALITY_OK, DBF_QUALITY_OK, DBF_QUALITY_OK, "边界受限"),
    )

    summary = summarize_dbf_focus_range(
        series,
        AngleRange(-1.0, 2.0),
        ambiguity_margin_db=0.5,
        error_limit_deg=1.0,
    )

    assert summary.frame_count == 4
    assert summary.bias_deg == pytest.approx(0.875)
    assert summary.mae_deg == pytest.approx(0.875)
    assert summary.rmse_deg == pytest.approx(np.sqrt(5.25 / 4.0))
    assert summary.max_abs_error_deg == pytest.approx(2.0)
    assert summary.worst_true_angle_deg == pytest.approx(2.0)
    assert summary.reliable_count == 2
    assert summary.reliable_coverage_pct == pytest.approx(50.0)
    assert summary.within_error_limit_count == 2
    assert summary.within_error_limit_pct == pytest.approx(50.0)


def test_generate_single_axis_pdf_and_audit_data(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original_hold_figure = performance_report_module._hold_figure
    hold_scales: list[str] = []
    hold_axes_per_page: list[int] = []

    def capture_hold_figure(*args: object, **kwargs: object):
        figure = original_hold_figure(*args, **kwargs)
        hold_scales.append(str(kwargs["spectrum_scale"]))
        hold_axes_per_page.append(len(figure.axes))
        return figure

    original_azimuth_bank = performance_report_module.dbf_azimuth_spectrum_bank
    azimuth_bank_calls = 0

    def count_azimuth_bank(*args: object, **kwargs: object):
        nonlocal azimuth_bank_calls
        azimuth_bank_calls += 1
        return original_azimuth_bank(*args, **kwargs)

    monkeypatch.setattr(
        performance_report_module,
        "_hold_figure",
        capture_hold_figure,
    )
    monkeypatch.setattr(
        performance_report_module,
        "dbf_azimuth_spectrum_bank",
        count_azimuth_bank,
    )
    array = AntennaArray.from_xy(
        tx_x=[0.0],
        tx_y=[0.0],
        rx_x=[0.0, 1.0, 2.0, 3.0],
        rx_y=[0.0, 0.0, 0.0, 0.0],
    )
    output = tmp_path / "single-axis-report.pdf"
    options = PerformanceReportOptions(
        output_path=output,
        title="Single-axis report smoke test",
        azimuth_focus=AngleRange(-10.0, 10.0),
        elevation_focus=AngleRange(-5.0, 5.0),
        azimuth_hold=AngleRange(-2.0, 2.0),
        elevation_hold=AngleRange(-2.0, 2.0),
        azimuth_hold_stride_frames=2,
        include_raw_data=True,
        language="en",
        include_spectrum_db=True,
        include_spectrum_magnitude=True,
    )
    snapshot = PerformanceReportSnapshot(
        array=array,
        frequency_ghz=77.0,
        ambiguity_margin_db=0.5,
        dbf_dictionary=DbfDictionaryConfig(),
        element_pattern=None,
        channel_patterns=ChannelPatternSet(),
        current_config={"version": 1, "unit": "lambda"},
        app_version="test",
        created_at=datetime.now().astimezone(),
    )

    artifacts = generate_performance_report(snapshot, options)

    assert artifacts.pdf_path == output.resolve()
    assert azimuth_bank_calls == 1
    assert hold_scales == ["db", "magnitude"]
    assert hold_axes_per_page == [1, 1]
    assert output.read_bytes().startswith(b"%PDF")
    assert output.stat().st_size > 10_000
    assert artifacts.data_directory is not None
    data_directory = artifacts.data_directory
    assert (data_directory / "azimuth_angle_performance.csv").exists()
    assert (data_directory / "azimuth_hold_spectra.csv").exists()
    assert not (data_directory / "elevation_angle_performance.csv").exists()
    assert not (data_directory / "elevation_hold_spectra.csv").exists()

    with (data_directory / "azimuth_angle_performance.csv").open(
        newline="", encoding="utf-8-sig"
    ) as handle:
        rows = list(csv.DictReader(handle))
    assert len(rows) == 181
    assert {
        "TrueAngleDeg",
        "DBFEstimateDeg",
        "DBFErrorDeg",
        "PeakMarginDb",
        "InHoldPlot",
        "ReliableFlag",
        "WithinErrorLimitFlag",
    } <= set(rows[0])
    plotted_angles = [
        float(row["TrueAngleDeg"])
        for row in rows
        if row["InHoldPlot"] == "1"
    ]
    assert plotted_angles == [-2.0, 0.0, 2.0]

    with (data_directory / "azimuth_hold_spectra.csv").open(
        newline="", encoding="utf-8-sig"
    ) as handle:
        hold_rows = list(csv.reader(handle))
    assert len(hold_rows) == 6
    assert len(hold_rows[0]) == 182

    manifest = json.loads(
        (data_directory / "report_manifest.json").read_text(encoding="utf-8")
    )
    assert manifest["schema_version"] == 1
    assert manifest["ranges"]["azimuth"]["hold_frame_count"] == 5
    assert manifest["ranges"]["azimuth"] == {
        "focus_deg": [-10.0, 10.0],
        "hold_deg": [-2.0, 2.0],
        "hold_endpoints_retained": True,
        "hold_frame_count": 5,
        "hold_plotted_curve_count": 3,
        "hold_plotted_true_angles_deg": [-2.0, 0.0, 2.0],
        "hold_range_frame_count": 5,
        "hold_step_deg": 2.0,
        "hold_stride_frames": 2,
        "max_hold_source": "all_frames_in_hold_range",
    }
    assert manifest["spectrum_plots"] == {
        "db_enabled": True,
        "layout": "one DBF spectrum plot per PDF page",
        "magnitude_conversion": "10^(dB/20) from the same per-frame DBF correlation spectrum",
        "normalized_magnitude_enabled": True,
    }
    assert "elevation" not in manifest["ranges"]
    assert "Hold spectrum CSV files retain every frame in the selected range." in manifest[
        "method_assumptions"
    ]
    assert "The max-hold envelope uses every frame in the selected Hold range." in manifest[
        "method_assumptions"
    ]
    assert manifest["thresholds"]["spectrum_floor_applies_to"] == (
        "dB spectrum plot display only"
    )


def test_two_axis_db_and_magnitude_create_four_single_plot_spectrum_pages() -> None:
    array = AntennaArray.from_xy(
        tx_x=[-1.0, 1.0],
        tx_y=[-0.5, 0.5],
        rx_x=[-1.5, 1.5],
        rx_y=[-1.0, 1.0],
    )
    options = PerformanceReportOptions(
        output_path=Path("two-axis-report.pdf"),
        title="Two-axis spectrum pagination",
        azimuth_focus=AngleRange(-10.0, 10.0),
        elevation_focus=AngleRange(-10.0, 10.0),
        azimuth_hold=AngleRange(-2.0, 2.0),
        elevation_hold=AngleRange(-2.0, 2.0),
        include_raw_data=False,
        language="en",
        include_spectrum_db=True,
        include_spectrum_magnitude=True,
    )
    snapshot = PerformanceReportSnapshot(
        array=array,
        frequency_ghz=77.0,
        ambiguity_margin_db=0.5,
        dbf_dictionary=DbfDictionaryConfig(),
        element_pattern=None,
        channel_patterns=ChannelPatternSet(),
        current_config={"version": 1, "unit": "lambda"},
        app_version="test",
        created_at=datetime.now().astimezone(),
    )

    data = performance_report_module._compute_report_data(
        snapshot,
        options,
    )
    spectrum_figures = [
        performance_report_module._hold_figure(
            snapshot,
            options,
            axis_data,
            spectrum_scale=scale,
        )
        for axis_data in data.axes
        for scale in ("db", "magnitude")
    ]

    assert [axis_data.axis for axis_data in data.axes] == ["azimuth", "elevation"]
    assert len(spectrum_figures) == 4
    assert all(len(figure.axes) == 1 for figure in spectrum_figures)


def test_performance_report_import_does_not_import_pyplot() -> None:
    project_root = Path(__file__).resolve().parents[1]
    code = (
        "import sys;"
        "sys.path.insert(0, 'src');"
        "import virtual_array.performance_report;"
        "raise SystemExit(1 if 'matplotlib.pyplot' in sys.modules else 0)"
    )
    result = subprocess.run([sys.executable, "-c", code], cwd=project_root, check=False)
    assert result.returncode == 0
