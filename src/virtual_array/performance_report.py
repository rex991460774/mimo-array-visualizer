"""Deterministic PDF and audit-data export for the current array configuration."""

from __future__ import annotations

import csv
import json
import math
import os
import textwrap
import uuid
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

import numpy as np
from matplotlib import colormaps, colors, rc_context
from matplotlib.backends.backend_pdf import PdfPages
from matplotlib.collections import LineCollection
from matplotlib.figure import Figure

from .analysis import (
    AZIMUTH_FOV,
    DBF_QUALITY_OK,
    DBF_SCAN_FOV,
    DBF_SCAN_STEP_DEG,
    ELEVATION_FOV,
    ArrayMetrics,
    DbfAngleFrameSeries,
    DbfAngleMetrics,
    calculate_metrics_and_psf,
    dbf_angle_frame_series_from_spectra,
    dbf_angle_metrics_from_spectra,
    dbf_azimuth_spectrum_bank,
    dbf_elevation_spectrum_bank,
)
from .dbf_dictionary import DbfDictionaryConfig
from .element_pattern import ChannelPatternSet, ElementPattern
from .geometry import AntennaArray


REPORT_SCHEMA_VERSION = 1
LIGHT_SPEED_MM_PER_NS = 299.792458
DISPLAY_SCALE_LAMBDA = 0.5
SUPPORTED_LANGUAGES = {"zh", "en", "ja"}
REPORT_FONT_CANDIDATES = [
    "Microsoft YaHei",
    "Yu Gothic",
    "Meiryo",
    "Noto Sans CJK SC",
    "Noto Sans CJK JP",
    "PingFang SC",
    "SimHei",
    "WenQuanYi Micro Hei",
    "DejaVu Sans",
]

ProgressCallback = Callable[[int, str], None]


@dataclass(frozen=True)
class AngleRange:
    start_deg: float
    stop_deg: float

    def __post_init__(self) -> None:
        start = float(self.start_deg)
        stop = float(self.stop_deg)
        if not math.isfinite(start) or not math.isfinite(stop):
            raise ValueError("Angle range values must be finite.")
        if start < DBF_SCAN_FOV[0] or stop > DBF_SCAN_FOV[1]:
            raise ValueError("Angle range must stay within -90 to +90 degrees.")
        if start > stop:
            raise ValueError("Angle range start must not exceed its stop.")
        object.__setattr__(self, "start_deg", start)
        object.__setattr__(self, "stop_deg", stop)

    def mask(self, values_deg: np.ndarray) -> np.ndarray:
        values = np.asarray(values_deg, dtype=float)
        return (values >= self.start_deg) & (values <= self.stop_deg)

    @property
    def frame_count_1deg(self) -> int:
        return int(round(self.stop_deg - self.start_deg)) + 1


@dataclass(frozen=True)
class PerformanceReportOptions:
    output_path: Path
    title: str
    azimuth_focus: AngleRange
    elevation_focus: AngleRange
    azimuth_hold: AngleRange
    elevation_hold: AngleRange
    error_limit_deg: float = 1.0
    spectrum_floor_db: float = -40.0
    include_raw_data: bool = True
    language: str = "zh"
    include_spectrum_db: bool = True
    include_spectrum_magnitude: bool = False

    def __post_init__(self) -> None:
        output_path = Path(self.output_path)
        if output_path.suffix.lower() != ".pdf":
            raise ValueError("Performance report output must use the .pdf extension.")
        title = str(self.title).strip()
        if not title:
            raise ValueError("Performance report title must not be empty.")
        if len(title) > 100:
            raise ValueError("Performance report title must not exceed 100 characters.")
        error_limit = float(self.error_limit_deg)
        if not math.isfinite(error_limit) or not 0.0 < error_limit <= 30.0:
            raise ValueError("Error limit must be greater than 0 and at most 30 degrees.")
        floor = float(self.spectrum_floor_db)
        if not math.isfinite(floor) or not -120.0 <= floor <= -10.0:
            raise ValueError("Spectrum floor must be between -120 dB and -10 dB.")
        include_spectrum_db = bool(self.include_spectrum_db)
        include_spectrum_magnitude = bool(self.include_spectrum_magnitude)
        if not include_spectrum_db and not include_spectrum_magnitude:
            raise ValueError(
                "At least one DBF spectrum output must be enabled: dB or magnitude."
            )
        language = self.language if self.language in SUPPORTED_LANGUAGES else "zh"
        object.__setattr__(self, "output_path", output_path)
        object.__setattr__(self, "title", title)
        object.__setattr__(self, "error_limit_deg", error_limit)
        object.__setattr__(self, "spectrum_floor_db", floor)
        object.__setattr__(self, "language", language)
        object.__setattr__(self, "include_spectrum_db", include_spectrum_db)
        object.__setattr__(
            self,
            "include_spectrum_magnitude",
            include_spectrum_magnitude,
        )


@dataclass(frozen=True)
class PerformanceReportSnapshot:
    array: AntennaArray
    frequency_ghz: float
    ambiguity_margin_db: float
    dbf_dictionary: DbfDictionaryConfig
    element_pattern: ElementPattern | None
    channel_patterns: ChannelPatternSet
    current_config: dict[str, Any]
    app_version: str
    created_at: datetime


@dataclass(frozen=True)
class ReportArtifacts:
    pdf_path: Path
    data_directory: Path | None
    files: tuple[Path, ...]


@dataclass(frozen=True)
class DbfSpectrumSelection:
    frame_indices: np.ndarray
    true_angles_deg: np.ndarray
    scan_angles_deg: np.ndarray
    spectra_db: np.ndarray
    max_hold_db: np.ndarray


@dataclass(frozen=True)
class DbfFocusSummary:
    frame_count: int
    reliable_count: int
    reliable_coverage_pct: float
    bias_deg: float
    mae_deg: float
    rmse_deg: float
    p95_abs_error_deg: float
    max_abs_error_deg: float
    worst_true_angle_deg: float
    worst_estimated_angle_deg: float
    reliable_max_abs_error_deg: float | None
    min_peak_margin_db: float | None
    p5_peak_margin_db: float | None
    within_error_limit_count: int
    within_error_limit_pct: float


@dataclass(frozen=True)
class _AxisReportData:
    axis: str
    true_angles_deg: np.ndarray
    scan_angles_deg: np.ndarray
    spectra_db: np.ndarray
    frame_series: DbfAngleFrameSeries
    angle_metrics: DbfAngleMetrics
    focus_range: AngleRange
    hold_range: AngleRange
    focus_summary: DbfFocusSummary
    hold_selection: DbfSpectrumSelection


@dataclass(frozen=True)
class _PerformanceReportData:
    af_db: np.ndarray
    azimuths_deg: np.ndarray
    elevations_deg: np.ndarray
    array_metrics: ArrayMetrics
    axes: tuple[_AxisReportData, ...]


def select_dbf_spectrum_frames(
    true_angles_deg: np.ndarray,
    scan_angles_deg: np.ndarray,
    spectra_db: np.ndarray,
    selected_range: AngleRange,
) -> DbfSpectrumSelection:
    """Select every true-angle frame in an inclusive range without decimation."""
    true_angles = np.asarray(true_angles_deg, dtype=float)
    scan_angles = np.asarray(scan_angles_deg, dtype=float)
    spectra = np.asarray(spectra_db, dtype=float)
    if true_angles.ndim != 1 or scan_angles.ndim != 1 or spectra.ndim != 2:
        raise ValueError("DBF frame selection expects 1D angle arrays and a 2D spectrum bank.")
    if spectra.shape != (len(true_angles), len(scan_angles)):
        raise ValueError("DBF spectrum bank shape does not match its angle axes.")
    indices = np.flatnonzero(selected_range.mask(true_angles))
    if indices.size == 0:
        raise ValueError("The selected Hold range contains no true-angle frames.")
    selected = spectra[indices].copy()
    return DbfSpectrumSelection(
        frame_indices=indices,
        true_angles_deg=true_angles[indices].copy(),
        scan_angles_deg=scan_angles.copy(),
        spectra_db=selected,
        max_hold_db=np.max(selected, axis=0),
    )


def dbf_spectrum_magnitude_from_db(spectrum_db: np.ndarray) -> np.ndarray:
    """Convert the existing normalized DBF dB spectrum to normalized magnitude."""
    values_db = np.asarray(spectrum_db, dtype=float)
    return np.power(10.0, np.minimum(values_db, 0.0) / 20.0)


def angle_error_display_limit_deg(
    true_angles_deg: np.ndarray,
    errors_deg: np.ndarray,
    focus_range: AngleRange,
    error_limit_deg: float,
) -> float:
    """Return a symmetric angle-error display limit based on the focus range.

    Folded errors outside the user-selected focus range must not compress the
    useful part of the curve.  When the focus range has no finite errors, the
    full finite series is used as a defensive fallback.  The minimum span and
    padding follow the HFSS report plotting convention.
    """
    true_angles = np.asarray(true_angles_deg, dtype=float)
    errors = np.asarray(errors_deg, dtype=float)
    if true_angles.ndim != 1 or errors.ndim != 1:
        raise ValueError("Angle-error display scaling expects 1D angle and error arrays.")
    if true_angles.shape != errors.shape:
        raise ValueError("Angle-error display scaling requires matching array lengths.")
    error_limit = float(error_limit_deg)
    if not math.isfinite(error_limit) or error_limit < 0.0:
        raise ValueError("Angle-error display limit must be finite and non-negative.")

    finite = np.isfinite(errors)
    focus_values = np.abs(errors[focus_range.mask(true_angles) & finite])
    displayed_values = focus_values if focus_values.size else np.abs(errors[finite])
    max_abs_error = float(np.max(displayed_values)) if displayed_values.size else 0.0
    return max(12.0, error_limit + 2.0, float(math.ceil(max_abs_error + 2.0)))


def summarize_dbf_focus_range(
    frame_series: DbfAngleFrameSeries,
    focus_range: AngleRange,
    ambiguity_margin_db: float,
    error_limit_deg: float = 1.0,
) -> DbfFocusSummary:
    """Aggregate error and reliability metrics over an arbitrary true-angle range."""
    margin_threshold = float(ambiguity_margin_db)
    error_limit = float(error_limit_deg)
    if not math.isfinite(margin_threshold) or margin_threshold < 0.0:
        raise ValueError("Ambiguity margin threshold must be finite and non-negative.")
    if not math.isfinite(error_limit) or error_limit <= 0.0:
        raise ValueError("Error limit must be finite and positive.")

    mask = focus_range.mask(frame_series.true_angles_deg)
    indices = np.flatnonzero(mask)
    if indices.size == 0:
        raise ValueError("The performance focus range contains no true-angle frames.")
    errors = frame_series.errors_deg[indices]
    absolute_errors = np.abs(errors)
    margins = frame_series.peak_margins_db[indices]
    quality = np.asarray(frame_series.quality_flags, dtype=object)[indices]
    reliable = quality == DBF_QUALITY_OK
    reliable &= margins > margin_threshold
    reliable &= np.isfinite(margins) | np.isposinf(margins)

    worst_local = int(np.argmax(absolute_errors))
    reliable_errors = absolute_errors[reliable]
    finite_margins = margins[np.isfinite(margins)]
    if finite_margins.size:
        min_margin: float | None = float(np.min(finite_margins))
        p5_margin: float | None = float(np.percentile(finite_margins, 5.0))
    elif np.any(np.isposinf(margins)):
        min_margin = float("inf")
        p5_margin = float("inf")
    else:
        min_margin = None
        p5_margin = None
    within_limit = reliable & (absolute_errors <= error_limit)
    frame_count = int(indices.size)
    reliable_count = int(np.count_nonzero(reliable))
    return DbfFocusSummary(
        frame_count=frame_count,
        reliable_count=reliable_count,
        reliable_coverage_pct=100.0 * reliable_count / frame_count,
        bias_deg=float(np.mean(errors)),
        mae_deg=float(np.mean(absolute_errors)),
        rmse_deg=float(np.sqrt(np.mean(errors**2))),
        p95_abs_error_deg=float(np.percentile(absolute_errors, 95.0)),
        max_abs_error_deg=float(absolute_errors[worst_local]),
        worst_true_angle_deg=float(frame_series.true_angles_deg[indices[worst_local]]),
        worst_estimated_angle_deg=float(
            frame_series.estimated_angles_deg[indices[worst_local]]
        ),
        reliable_max_abs_error_deg=(
            float(np.max(reliable_errors)) if reliable_errors.size else None
        ),
        min_peak_margin_db=min_margin,
        p5_peak_margin_db=p5_margin,
        within_error_limit_count=int(np.count_nonzero(within_limit)),
        within_error_limit_pct=100.0 * int(np.count_nonzero(within_limit)) / frame_count,
    )


def generate_performance_report(
    snapshot: PerformanceReportSnapshot,
    options: PerformanceReportOptions,
    progress_callback: ProgressCallback | None = None,
) -> ReportArtifacts:
    """Generate a multi-page PDF and optional reproducibility data package."""
    _validate_snapshot(snapshot)
    output_path = options.output_path.expanduser().resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    _notify(progress_callback, 5, _progress_text(options.language, "compute"))
    data = _compute_report_data(snapshot, options)

    temporary_pdf = output_path.with_name(
        f".{output_path.stem}.{uuid.uuid4().hex}.tmp.pdf"
    )
    written_data: list[Path] = []
    try:
        _write_pdf(temporary_pdf, snapshot, options, data, progress_callback)
        _notify(progress_callback, 95, _progress_text(options.language, "finalize"))
        if options.include_raw_data:
            written_data = _write_data_package(output_path, snapshot, options, data)
        os.replace(temporary_pdf, output_path)
    finally:
        temporary_pdf.unlink(missing_ok=True)

    data_directory = (
        output_path.with_name(f"{output_path.stem}_data")
        if options.include_raw_data
        else None
    )
    files = (output_path, *written_data)
    _notify(progress_callback, 100, _progress_text(options.language, "done"))
    return ReportArtifacts(
        pdf_path=output_path,
        data_directory=data_directory,
        files=tuple(files),
    )


def _validate_snapshot(snapshot: PerformanceReportSnapshot) -> None:
    frequency = float(snapshot.frequency_ghz)
    margin = float(snapshot.ambiguity_margin_db)
    if not math.isfinite(frequency) or frequency <= 0.0:
        raise ValueError("Snapshot frequency must be finite and positive.")
    if not math.isfinite(margin) or margin < 0.0:
        raise ValueError("Snapshot ambiguity margin must be finite and non-negative.")
    if snapshot.created_at.tzinfo is None:
        raise ValueError("Snapshot creation time must include a timezone.")


def _compute_report_data(
    snapshot: PerformanceReportSnapshot,
    options: PerformanceReportOptions,
) -> _PerformanceReportData:
    unique, counts = snapshot.array.unique_virtual_xy()
    af_db, azimuths, elevations, metrics = calculate_metrics_and_psf(
        snapshot.array,
        unique,
        counts,
        tx_pattern=snapshot.element_pattern,
        rx_pattern=snapshot.element_pattern,
        channel_patterns=snapshot.channel_patterns,
    )
    axes: list[_AxisReportData] = []
    axis_specs = (
        (
            "azimuth",
            metrics.x_aperture > 0.0 and metrics.azimuth_resolution is not None,
            dbf_azimuth_spectrum_bank,
            options.azimuth_focus,
            options.azimuth_hold,
        ),
        (
            "elevation",
            metrics.y_aperture > 0.0 and metrics.elevation_resolution is not None,
            dbf_elevation_spectrum_bank,
            options.elevation_focus,
            options.elevation_hold,
        ),
    )
    for axis, available, bank_function, focus_range, hold_range in axis_specs:
        if not available:
            continue
        true_angles, scan_angles, spectra = bank_function(
            snapshot.array,
            tx_pattern=snapshot.element_pattern,
            rx_pattern=snapshot.element_pattern,
            channel_patterns=snapshot.channel_patterns,
            dbf_dictionary=snapshot.dbf_dictionary,
        )
        frame_series = dbf_angle_frame_series_from_spectra(
            true_angles,
            scan_angles,
            spectra,
        )
        angle_metrics = dbf_angle_metrics_from_spectra(
            true_angles,
            scan_angles,
            spectra,
            ambiguity_margin_db=snapshot.ambiguity_margin_db,
        )
        axes.append(
            _AxisReportData(
                axis=axis,
                true_angles_deg=true_angles,
                scan_angles_deg=scan_angles,
                spectra_db=spectra,
                frame_series=frame_series,
                angle_metrics=angle_metrics,
                focus_range=focus_range,
                hold_range=hold_range,
                focus_summary=summarize_dbf_focus_range(
                    frame_series,
                    focus_range,
                    snapshot.ambiguity_margin_db,
                    options.error_limit_deg,
                ),
                hold_selection=select_dbf_spectrum_frames(
                    true_angles,
                    scan_angles,
                    spectra,
                    hold_range,
                ),
            )
        )
    if not axes:
        raise ValueError(
            "The current array has no usable azimuth or elevation aperture for angle reporting."
        )
    return _PerformanceReportData(
        af_db=af_db,
        azimuths_deg=azimuths,
        elevations_deg=elevations,
        array_metrics=metrics,
        axes=tuple(axes),
    )


def _write_pdf(
    target: Path,
    snapshot: PerformanceReportSnapshot,
    options: PerformanceReportOptions,
    data: _PerformanceReportData,
    progress_callback: ProgressCallback | None,
) -> None:
    metadata = {
        "Title": options.title,
        "Author": "MIMO Array Visualizer",
        "Subject": "Current-configuration DBF angle-performance report",
        "Keywords": "MIMO, DBF, angle error, frame hold",
        "CreationDate": snapshot.created_at,
    }
    rc_settings = {
        "font.family": "sans-serif",
        "font.sans-serif": REPORT_FONT_CANDIDATES,
        "axes.unicode_minus": False,
        "pdf.fonttype": 42,
        "figure.facecolor": "white",
        "axes.facecolor": "#fbfdff",
        "axes.edgecolor": "#94a3b8",
        "axes.labelcolor": "#334155",
        "xtick.color": "#475569",
        "ytick.color": "#475569",
        "grid.color": "#dbe5ef",
    }
    with rc_context(rc_settings), PdfPages(target, metadata=metadata) as pdf:
        _notify(progress_callback, 25, _progress_text(options.language, "summary"))
        pdf.savefig(_summary_figure(snapshot, options, data))
        _notify(progress_callback, 40, _progress_text(options.language, "array"))
        pdf.savefig(_array_response_figure(snapshot, options, data))
        _notify(progress_callback, 55, _progress_text(options.language, "error"))
        pdf.savefig(_angle_error_figure(snapshot, options, data))
        spectrum_scales = (
            *(("db",) if options.include_spectrum_db else ()),
            *(("magnitude",) if options.include_spectrum_magnitude else ()),
        )
        progress = 65
        hold_page_count = len(data.axes) * len(spectrum_scales)
        increment = 30 / max(hold_page_count, 1)
        for axis_data in data.axes:
            for spectrum_scale in spectrum_scales:
                _notify(
                    progress_callback,
                    int(progress),
                    _progress_text(options.language, "hold", axis=axis_data.axis),
                )
                pdf.savefig(
                    _hold_figure(
                        snapshot,
                        options,
                        axis_data,
                        spectrum_scale=spectrum_scale,
                    )
                )
                progress += increment


def _summary_figure(
    snapshot: PerformanceReportSnapshot,
    options: PerformanceReportOptions,
    data: _PerformanceReportData,
) -> Figure:
    language = options.language
    metrics = data.array_metrics
    figure = Figure(figsize=(11.69, 8.27), dpi=120)
    figure.suptitle(options.title, x=0.04, y=0.975, ha="left", fontsize=20, fontweight="bold")
    subtitle = (
        f"{_label(language, 'generated')}: {snapshot.created_at.isoformat(timespec='seconds')}    "
        f"{_label(language, 'version')}: {snapshot.app_version}    "
        f"{_label(language, 'frequency')}: {snapshot.frequency_ghz:g} GHz"
    )
    figure.text(0.04, 0.925, subtitle, fontsize=9.5, color="#475569")
    figure.text(
        0.04,
        0.885,
        (
            f"{_label(language, 'dictionary')}: {snapshot.dbf_dictionary.display_name}    "
            f"{_label(language, 'margin_threshold')}: > {snapshot.ambiguity_margin_db:g} dB    "
            f"{_label(language, 'error_limit')}: ±{options.error_limit_deg:g}°"
        ),
        fontsize=9.5,
        color="#334155",
    )

    metrics_axis = figure.add_axes([0.04, 0.54, 0.92, 0.30])
    metrics_axis.axis("off")
    metrics_axis.set_title(
        _label(language, "basic_metrics"),
        loc="left",
        fontsize=12,
        fontweight="bold",
        pad=8,
    )
    metric_rows = _basic_metric_rows(snapshot, metrics, language)
    metric_table = metrics_axis.table(
        cellText=metric_rows,
        colLabels=[_label(language, "metric"), _label(language, "value")],
        cellLoc="left",
        colLoc="left",
        loc="upper left",
        colWidths=[0.34, 0.62],
    )
    _style_table(metric_table, font_size=8.2)

    angle_axis = figure.add_axes([0.04, 0.265, 0.92, 0.21])
    angle_axis.axis("off")
    angle_axis.set_title(
        _label(language, "angle_summary"),
        loc="left",
        fontsize=12,
        fontweight="bold",
        pad=8,
    )
    angle_headers = [
        _label(language, "axis"),
        _label(language, "focus"),
        _label(language, "frames"),
        _label(language, "bias"),
        "RMSE",
        "P95 |Error|",
        _label(language, "max_error"),
        _label(language, "reliable"),
        _label(language, "pass_rate"),
        _label(language, "no_fold"),
        _label(language, "min_margin"),
    ]
    angle_rows = [_axis_summary_row(axis_data, language) for axis_data in data.axes]
    angle_table = angle_axis.table(
        cellText=angle_rows,
        colLabels=angle_headers,
        cellLoc="center",
        colLoc="center",
        loc="upper left",
        colWidths=[0.07, 0.10, 0.06, 0.075, 0.075, 0.09, 0.09, 0.09, 0.08, 0.105, 0.09],
    )
    _style_table(angle_table, font_size=6.8)

    method_axis = figure.add_axes([0.04, 0.035, 0.92, 0.17])
    method_axis.axis("off")
    method_axis.set_title(
        _label(language, "method_notes"),
        loc="left",
        fontsize=11,
        fontweight="bold",
        pad=4,
    )
    notes = _method_notes(snapshot, options, data)
    wrapped = "\n".join(
        f"• {textwrap.fill(note, width=155, subsequent_indent='  ')}" for note in notes
    )
    method_axis.text(
        0.0,
        0.94,
        wrapped,
        va="top",
        ha="left",
        fontsize=8.2,
        color="#334155",
        linespacing=1.35,
    )
    return figure


def _array_response_figure(
    snapshot: PerformanceReportSnapshot,
    options: PerformanceReportOptions,
    data: _PerformanceReportData,
) -> Figure:
    language = options.language
    figure = Figure(figsize=(11.69, 8.27), dpi=120)
    figure.suptitle(
        _label(language, "array_response"),
        x=0.04,
        y=0.985,
        ha="left",
        fontsize=17,
        fontweight="bold",
    )
    axes = figure.subplots(2, 2)
    physical_axis, virtual_axis, heatmap_axis, cut_axis = axes.ravel()

    tx = snapshot.array.tx_xy() * DISPLAY_SCALE_LAMBDA
    rx = snapshot.array.rx_xy() * DISPLAY_SCALE_LAMBDA
    physical_axis.scatter(tx[:, 0], tx[:, 1], s=42, marker="^", color="#dc2626", label="Tx")
    physical_axis.scatter(rx[:, 0], rx[:, 1], s=38, marker="o", color="#2563eb", label="Rx")
    if len(snapshot.array.tx) + len(snapshot.array.rx) <= 32:
        for point, xy in zip((*snapshot.array.tx, *snapshot.array.rx), np.vstack([tx, rx])):
            physical_axis.annotate(point.name, xy, xytext=(4, 4), textcoords="offset points", fontsize=7)
    physical_axis.set_title(_label(language, "physical_array"), loc="left", fontweight="bold")
    physical_axis.set_xlabel("x (λ)")
    physical_axis.set_ylabel("y (λ)")
    physical_axis.set_aspect("equal", adjustable="datalim")
    physical_axis.grid(True, alpha=0.8)
    physical_axis.legend(loc="best", fontsize=8)

    unique, counts = snapshot.array.unique_virtual_xy()
    unique_lambda = unique * DISPLAY_SCALE_LAMBDA
    virtual_axis.scatter(
        unique_lambda[:, 0],
        unique_lambda[:, 1],
        s=28.0 + 16.0 * np.sqrt(counts),
        color="#7c3aed",
        alpha=0.82,
        edgecolor="white",
        linewidth=0.6,
    )
    virtual_axis.set_title(
        f"{_label(language, 'virtual_array')} ({len(unique)}/{data.array_metrics.virtual_count})",
        loc="left",
        fontweight="bold",
    )
    virtual_axis.set_xlabel("x (λ)")
    virtual_axis.set_ylabel("y (λ)")
    virtual_axis.set_aspect("equal", adjustable="datalim")
    virtual_axis.grid(True, alpha=0.8)

    image = heatmap_axis.imshow(
        np.clip(data.af_db, options.spectrum_floor_db, 0.0),
        origin="lower",
        aspect="auto",
        extent=[
            float(data.azimuths_deg[0]),
            float(data.azimuths_deg[-1]),
            float(data.elevations_deg[0]),
            float(data.elevations_deg[-1]),
        ],
        cmap="viridis",
        vmin=options.spectrum_floor_db,
        vmax=0.0,
    )
    heatmap_axis.set_title(_label(language, "array_factor_2d"), loc="left", fontweight="bold")
    heatmap_axis.set_xlabel(_label(language, "azimuth_angle"))
    heatmap_axis.set_ylabel(_label(language, "elevation_angle"))
    figure.colorbar(image, ax=heatmap_axis, label="dB", shrink=0.86)

    az0 = int(np.argmin(np.abs(data.azimuths_deg)))
    el0 = int(np.argmin(np.abs(data.elevations_deg)))
    cut_axis.plot(
        data.azimuths_deg,
        data.af_db[el0, :],
        color="#2563eb",
        linewidth=1.8,
        label=_label(language, "azimuth_cut"),
    )
    cut_axis.plot(
        data.elevations_deg,
        data.af_db[:, az0],
        color="#dc2626",
        linewidth=1.8,
        label=_label(language, "elevation_cut"),
    )
    cut_axis.set_xlim(DBF_SCAN_FOV)
    cut_axis.set_ylim(options.spectrum_floor_db, 1.0)
    cut_axis.set_title(_label(language, "principal_cuts"), loc="left", fontweight="bold")
    cut_axis.set_xlabel(_label(language, "scan_angle"))
    cut_axis.set_ylabel("dB")
    cut_axis.grid(True, alpha=0.8)
    cut_axis.legend(loc="best", fontsize=8)
    figure.tight_layout(rect=(0.025, 0.025, 0.98, 0.95), h_pad=2.2, w_pad=1.8)
    return figure


def _angle_error_figure(
    snapshot: PerformanceReportSnapshot,
    options: PerformanceReportOptions,
    data: _PerformanceReportData,
) -> Figure:
    language = options.language
    column_count = len(data.axes)
    figure = Figure(figsize=(11.69, 8.27), dpi=120)
    figure.suptitle(
        _label(language, "angle_error_reliability"),
        x=0.04,
        y=0.985,
        ha="left",
        fontsize=17,
        fontweight="bold",
    )
    axes = figure.subplots(2, column_count, squeeze=False)
    for column, axis_data in enumerate(data.axes):
        error_axis = axes[0, column]
        margin_axis = axes[1, column]
        series = axis_data.frame_series
        focus = axis_data.focus_range
        summary = axis_data.focus_summary
        reliable = _reliable_mask(series, snapshot.ambiguity_margin_db)

        error_axis.axvspan(
            focus.start_deg,
            focus.stop_deg,
            color="#dbeafe",
            alpha=0.48,
            label=_label(language, "focus"),
        )
        metrics = axis_data.angle_metrics
        if metrics.no_fold_left is not None and metrics.no_fold_right is not None:
            error_axis.axvspan(
                metrics.no_fold_left,
                metrics.no_fold_right,
                color="#dcfce7",
                alpha=0.55,
                label=_label(language, "no_fold"),
            )
        error_axis.plot(
            series.true_angles_deg,
            series.errors_deg,
            color="#2563eb",
            linewidth=1.8,
            label=_label(language, "error_curve"),
        )
        if np.any(~reliable):
            error_axis.scatter(
                series.true_angles_deg[~reliable],
                series.errors_deg[~reliable],
                s=13,
                marker="x",
                color="#dc2626",
                linewidth=0.8,
                label=_label(language, "unreliable_frame"),
                zorder=4,
            )
        error_axis.axhline(0.0, color="#475569", linewidth=1.0)
        error_axis.axhline(
            options.error_limit_deg,
            color="#d97706",
            linestyle="--",
            linewidth=1.0,
        )
        error_axis.axhline(
            -options.error_limit_deg,
            color="#d97706",
            linestyle="--",
            linewidth=1.0,
        )
        error_axis.set_xlim(DBF_SCAN_FOV)
        error_display_limit = angle_error_display_limit_deg(
            series.true_angles_deg,
            series.errors_deg,
            focus,
            options.error_limit_deg,
        )
        error_axis.set_ylim(-error_display_limit, error_display_limit)
        error_axis.set_title(
            f"{_axis_label(axis_data.axis, language)} — {_label(language, 'error_curve')}",
            loc="left",
            fontweight="bold",
        )
        error_axis.set_xlabel(_label(language, "true_angle"))
        error_axis.set_ylabel(_label(language, "estimated_minus_true"))
        error_axis.grid(True, alpha=0.8)
        error_axis.legend(loc="best", fontsize=7)
        error_axis.text(
            0.02,
            0.04,
            (
                f"Bias {summary.bias_deg:.3f}°  |  RMSE {summary.rmse_deg:.3f}°  |  "
                f"P95 {summary.p95_abs_error_deg:.3f}°  |  Max {summary.max_abs_error_deg:.3f}°"
            ),
            transform=error_axis.transAxes,
            fontsize=7.5,
            color="#334155",
            bbox={"boxstyle": "round,pad=0.3", "fc": "white", "ec": "#cbd5e1", "alpha": 0.92},
        )
        error_axis.text(
            0.98,
            0.96,
            textwrap.fill(_label(language, "focus_scaled_y_axis_note"), width=32),
            transform=error_axis.transAxes,
            ha="right",
            va="top",
            fontsize=6.5,
            color="#64748b",
            bbox={"boxstyle": "round,pad=0.25", "fc": "white", "ec": "#e2e8f0", "alpha": 0.9},
        )

        margins = series.peak_margins_db
        finite = margins[np.isfinite(margins)]
        margin_cap = max(
            snapshot.ambiguity_margin_db + 3.0,
            5.0,
            float(np.percentile(finite, 95.0)) if finite.size else 10.0,
        )
        margin_cap = min(margin_cap, 40.0)
        display_margins = np.where(np.isposinf(margins), margin_cap, margins)
        margin_axis.axvspan(
            focus.start_deg,
            focus.stop_deg,
            color="#dbeafe",
            alpha=0.48,
        )
        margin_axis.plot(
            series.true_angles_deg,
            display_margins,
            color="#7c3aed",
            linewidth=1.7,
        )
        margin_axis.axhline(
            snapshot.ambiguity_margin_db,
            color="#dc2626",
            linestyle="--",
            linewidth=1.2,
            label=f"> {snapshot.ambiguity_margin_db:g} dB",
        )
        margin_axis.set_xlim(DBF_SCAN_FOV)
        margin_axis.set_ylim(bottom=min(-0.25, float(np.min(display_margins)) - 0.5), top=margin_cap * 1.08)
        margin_axis.set_title(
            f"{_axis_label(axis_data.axis, language)} — {_label(language, 'peak_margin')}",
            loc="left",
            fontweight="bold",
        )
        margin_axis.set_xlabel(_label(language, "true_angle"))
        margin_axis.set_ylabel("dB")
        margin_axis.grid(True, alpha=0.8)
        margin_axis.legend(loc="best", fontsize=7)
        margin_axis.text(
            0.02,
            0.04,
            (
                f"{_label(language, 'reliable')}: {summary.reliable_count}/{summary.frame_count} "
                f"({summary.reliable_coverage_pct:.1f}%)  |  "
                f"{_label(language, 'pass_rate')}: {summary.within_error_limit_pct:.1f}%"
            ),
            transform=margin_axis.transAxes,
            fontsize=7.5,
            color="#334155",
            bbox={"boxstyle": "round,pad=0.3", "fc": "white", "ec": "#cbd5e1", "alpha": 0.92},
        )
    figure.tight_layout(rect=(0.025, 0.025, 0.98, 0.95), h_pad=2.5, w_pad=2.0)
    return figure


def _hold_figure(
    snapshot: PerformanceReportSnapshot,
    options: PerformanceReportOptions,
    axis_data: _AxisReportData,
    *,
    spectrum_scale: str,
) -> Figure:
    language = options.language
    selection = axis_data.hold_selection
    if spectrum_scale not in {"db", "magnitude"}:
        raise ValueError(f"Unsupported DBF spectrum scale: {spectrum_scale}")
    figure = Figure(figsize=(11.69, 8.27), dpi=120)
    fixed_text = (
        _label(language, "fixed_elevation_zero")
        if axis_data.axis == "azimuth"
        else _label(language, "fixed_azimuth_zero")
    )
    scale_title = _label(
        language,
        "spectrum_db" if spectrum_scale == "db" else "spectrum_magnitude",
    )
    title = (
        f"{_axis_label(axis_data.axis, language)} 1D DBF "
        f"{_label(language, 'frame_hold')} — {scale_title} ({fixed_text})"
    )
    figure.suptitle(title, x=0.04, y=0.985, ha="left", fontsize=16, fontweight="bold")
    overlay_axis = figure.subplots(1, 1)
    clipped_db = np.clip(selection.spectra_db, options.spectrum_floor_db, 0.0)
    max_hold_db = np.clip(
        selection.max_hold_db,
        options.spectrum_floor_db,
        0.0,
    )
    if spectrum_scale == "db":
        display_spectra = clipped_db
        display_max_hold = max_hold_db
        y_limits = (options.spectrum_floor_db, 1.0)
        y_label = _label(language, "correlation_db")
    else:
        display_spectra = dbf_spectrum_magnitude_from_db(selection.spectra_db)
        display_max_hold = dbf_spectrum_magnitude_from_db(selection.max_hold_db)
        y_limits = (0.0, 1.02)
        y_label = _label(language, "normalized_magnitude")
    segments = np.asarray(
        [
            np.column_stack([selection.scan_angles_deg, row])
            for row in display_spectra
        ],
        dtype=float,
    )
    color_min = float(selection.true_angles_deg[0])
    color_max = float(selection.true_angles_deg[-1])
    if math.isclose(color_min, color_max):
        color_min -= 0.5
        color_max += 0.5
    normalization = colors.Normalize(vmin=color_min, vmax=color_max)
    collection = LineCollection(
        segments,
        cmap="turbo",
        norm=normalization,
        linewidths=0.55,
        alpha=0.34,
        rasterized=True,
    )
    collection.set_array(selection.true_angles_deg)
    overlay_axis.add_collection(collection)
    overlay_axis.plot(
        selection.scan_angles_deg,
        display_max_hold,
        color="#111827",
        linewidth=1.8,
        linestyle="--",
        label=_label(language, "max_hold_envelope"),
    )
    highlight_angles = {
        float(selection.true_angles_deg[0]),
        float(selection.true_angles_deg[-1]),
        float(selection.true_angles_deg[int(np.argmin(np.abs(selection.true_angles_deg)))]),
    }
    worst = axis_data.focus_summary.worst_true_angle_deg
    if axis_data.hold_range.start_deg <= worst <= axis_data.hold_range.stop_deg:
        highlight_angles.add(worst)
    cmap = colormaps["turbo"]
    for angle in sorted(highlight_angles):
        index = int(np.argmin(np.abs(selection.true_angles_deg - angle)))
        normalized_angle = normalization(float(selection.true_angles_deg[index]))
        overlay_axis.plot(
            selection.scan_angles_deg,
            display_spectra[index],
            color=cmap(normalized_angle),
            linewidth=1.15,
            alpha=0.95,
        )
    overlay_axis.set_xlim(DBF_SCAN_FOV)
    overlay_axis.set_ylim(*y_limits)
    overlay_axis.set_title(_label(language, "all_frames_overlay"), loc="left", fontweight="bold")
    overlay_axis.set_xlabel(_label(language, "scan_angle"))
    overlay_axis.set_ylabel(y_label)
    overlay_axis.grid(True, alpha=0.8)
    overlay_axis.legend(loc="lower right", fontsize=8)
    overlay_axis.text(
        0.02,
        0.04,
        (
            f"{_label(language, 'frame_color')}: "
            f"{selection.true_angles_deg[0]:g}° → "
            f"{selection.true_angles_deg[-1]:g}°"
        ),
        transform=overlay_axis.transAxes,
        fontsize=8,
        color="#334155",
        bbox={
            "boxstyle": "round,pad=0.3",
            "fc": "white",
            "ec": "#cbd5e1",
            "alpha": 0.92,
        },
    )

    figure.text(
        0.04,
        0.035,
        (
            f"{_label(language, 'hold_range')}: "
            f"{_format_range(axis_data.hold_range)}  |  "
            f"{len(selection.true_angles_deg)} {_label(language, 'frames')}  |  "
            f"{_label(language, 'every_frame_note')}  |  {fixed_text}"
        ),
        fontsize=8.5,
        color="#334155",
    )
    figure.tight_layout(rect=(0.035, 0.075, 0.98, 0.94))
    return figure


def _write_data_package(
    output_path: Path,
    snapshot: PerformanceReportSnapshot,
    options: PerformanceReportOptions,
    data: _PerformanceReportData,
) -> list[Path]:
    data_directory = output_path.with_name(f"{output_path.stem}_data")
    data_directory.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []

    config_path = data_directory / "current_config.json"
    _atomic_write_json(config_path, snapshot.current_config)
    written.append(config_path)

    for axis_data in data.axes:
        performance_path = data_directory / f"{axis_data.axis}_angle_performance.csv"
        _write_angle_performance_csv(
            performance_path,
            axis_data,
            snapshot.ambiguity_margin_db,
            options.error_limit_deg,
        )
        written.append(performance_path)
        hold_path = data_directory / f"{axis_data.axis}_hold_spectra.csv"
        _write_hold_spectra_csv(hold_path, axis_data.hold_selection)
        written.append(hold_path)

    manifest_path = data_directory / "report_manifest.json"
    manifest = _report_manifest(
        output_path,
        snapshot,
        options,
        data,
        [path.name for path in written],
    )
    _atomic_write_json(manifest_path, manifest)
    written.append(manifest_path)
    return written


def _write_angle_performance_csv(
    path: Path,
    axis_data: _AxisReportData,
    ambiguity_margin_db: float,
    error_limit_deg: float,
) -> None:
    series = axis_data.frame_series
    focus_mask = axis_data.focus_range.mask(series.true_angles_deg)
    hold_mask = axis_data.hold_range.mask(series.true_angles_deg)
    reliable = _reliable_mask(series, ambiguity_margin_db)
    within_error = reliable & (np.abs(series.errors_deg) <= error_limit_deg)
    rows = [
        [
            _csv_value(series.true_angles_deg[index]),
            _csv_value(series.estimated_angles_deg[index]),
            _csv_value(series.errors_deg[index]),
            _csv_value(series.main_peak_db[index]),
            _csv_value(series.competitor_peak_db[index]),
            _csv_value(series.peak_margins_db[index]),
            series.quality_flags[index],
            int(focus_mask[index]),
            int(hold_mask[index]),
            int(reliable[index]),
            int(within_error[index]),
        ]
        for index in range(len(series.true_angles_deg))
    ]
    _atomic_write_csv(
        path,
        [
            "TrueAngleDeg",
            "DBFEstimateDeg",
            "DBFErrorDeg",
            "MainPeakDb",
            "CompetitorPeakDb",
            "PeakMarginDb",
            "DbfQualityFlag",
            "InFocusRange",
            "InHoldRange",
            "ReliableFlag",
            "WithinErrorLimitFlag",
        ],
        rows,
    )


def _write_hold_spectra_csv(
    path: Path,
    selection: DbfSpectrumSelection,
) -> None:
    header = ["TrueAngleDeg"] + [
        f"Scan_{angle:g}Deg" for angle in selection.scan_angles_deg
    ]
    rows = [
        [_csv_value(true_angle), *(_csv_value(value) for value in spectrum)]
        for true_angle, spectrum in zip(
            selection.true_angles_deg,
            selection.spectra_db,
        )
    ]
    _atomic_write_csv(path, header, rows)


def _report_manifest(
    output_path: Path,
    snapshot: PerformanceReportSnapshot,
    options: PerformanceReportOptions,
    data: _PerformanceReportData,
    data_files: list[str],
) -> dict[str, Any]:
    return {
        "schema_version": REPORT_SCHEMA_VERSION,
        "report_pdf": output_path.name,
        "generated_at": snapshot.created_at.isoformat(),
        "application_version": snapshot.app_version,
        "language": options.language,
        "frequency_ghz": snapshot.frequency_ghz,
        "dbf_scan": {
            "minimum_deg": DBF_SCAN_FOV[0],
            "maximum_deg": DBF_SCAN_FOV[1],
            "step_deg": DBF_SCAN_STEP_DEG,
            "normalization": "normalized complex correlation; 0 dB equals correlation 1",
            "peak_interpolation": "none; discrete scan-grid peak",
            "tie_policy": "deterministic first maximum for performance metrics",
        },
        "spectrum_plots": {
            "db_enabled": options.include_spectrum_db,
            "normalized_magnitude_enabled": options.include_spectrum_magnitude,
            "magnitude_conversion": "10^(dB/20) from the same per-frame DBF correlation spectrum",
            "layout": "one DBF spectrum plot per PDF page",
        },
        "array_factor_fov": {
            "azimuth_deg": list(AZIMUTH_FOV),
            "elevation_deg": list(ELEVATION_FOV),
        },
        "thresholds": {
            "ambiguity_margin_db_strictly_greater_than": snapshot.ambiguity_margin_db,
            "absolute_error_limit_deg": options.error_limit_deg,
            "spectrum_floor_db": options.spectrum_floor_db,
            "spectrum_floor_applies_to": "dB spectrum plot display only",
        },
        "ranges": {
            axis_data.axis: {
                "focus_deg": [
                    axis_data.focus_range.start_deg,
                    axis_data.focus_range.stop_deg,
                ],
                "hold_deg": [
                    axis_data.hold_range.start_deg,
                    axis_data.hold_range.stop_deg,
                ],
                "hold_frame_count": len(axis_data.hold_selection.true_angles_deg),
            }
            for axis_data in data.axes
        },
        "dictionary": _dictionary_metadata(snapshot.dbf_dictionary),
        "element_pattern": _element_pattern_metadata(snapshot.element_pattern),
        "channel_patterns": _channel_pattern_metadata(snapshot.channel_patterns),
        "method_assumptions": [
            "Azimuth 1D DBF fixes true elevation at 0 degrees.",
            "Elevation 1D DBF fixes true azimuth at 0 degrees.",
            "The orthogonal 1D results are diagnostics, not a full joint 2D error-volume validation.",
            "Element-pattern gain affects array-factor metrics but is not consumed by the current 1D DBF implementation.",
            "Every selected Hold frame is exported without decimation.",
            "All DBF spectrum plots reuse the same per-frame signal-to-dictionary correlation spectrum bank.",
            "Normalized magnitude is derived as 10^(dB/20); it is not recomputed as a second spectrum.",
        ],
        "artifacts": [*data_files, "report_manifest.json"],
    }


def _dictionary_metadata(dictionary: DbfDictionaryConfig) -> dict[str, Any]:
    return {
        "mode": dictionary.mode,
        "display_name": dictionary.display_name,
        "custom_azimuth": _dictionary_table_metadata(
            dictionary.custom_azimuth_table
        ),
        "custom_elevation": _dictionary_table_metadata(
            dictionary.custom_elevation_table
        ),
        "custom_phase_reversed": dictionary.custom_phase_reversed,
        "custom_zero_phase_calibrated": dictionary.custom_zero_phase_calibrated,
    }


def _dictionary_table_metadata(table: Any | None) -> dict[str, Any] | None:
    if table is None:
        return None
    metadata: dict[str, Any] = {
        "source_path": table.source_path,
        "channel_mode": table.channel_mode,
        "row_count": int(len(table.values)),
        "is_2d": bool(table.is_2d),
    }
    if table.is_2d:
        metadata["azimuth_coverage_deg"] = [
            float(np.min(table.azimuths_deg)),
            float(np.max(table.azimuths_deg)),
        ]
        metadata["elevation_coverage_deg"] = [
            float(np.min(table.elevations_deg)),
            float(np.max(table.elevations_deg)),
        ]
    else:
        metadata["angle_coverage_deg"] = [
            float(np.min(table.angles_deg)),
            float(np.max(table.angles_deg)),
        ]
    return metadata


def _element_pattern_metadata(pattern: ElementPattern | None) -> dict[str, Any]:
    if pattern is None:
        return {"configured": False}
    return {
        "configured": True,
        "name": pattern.name,
        "source_path": pattern.source_path,
        "horizontal_column": pattern.horizontal_column,
        "elevation_column": pattern.elevation_column,
        "dbf_usage": "not used by the current 1D DBF implementation",
    }


def _channel_pattern_metadata(patterns: ChannelPatternSet) -> dict[str, Any]:
    sources: dict[str, list[str]] = {}
    for channel_name, channel_pattern in sorted(patterns.patterns.items()):
        series_values = (
            channel_pattern.amplitude_horizontal,
            channel_pattern.amplitude_elevation,
            channel_pattern.phase_horizontal,
            channel_pattern.phase_elevation,
        )
        channel_sources = sorted(
            {
                str(series.source_path)
                for series in series_values
                if series is not None and series.source_path
            }
        )
        if channel_sources:
            sources[channel_name] = channel_sources
    return {
        "configured_channels": patterns.configured_channel_count(),
        "configured_series": patterns.configured_series_count(),
        "sources": sources,
    }


def _atomic_write_json(path: Path, payload: Any) -> None:
    text = json.dumps(
        payload,
        ensure_ascii=False,
        indent=2,
        sort_keys=True,
        default=_json_default,
    )
    temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    try:
        temporary.write_text(f"{text}\n", encoding="utf-8")
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def _atomic_write_csv(path: Path, header: list[str], rows: list[list[Any]]) -> None:
    temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    try:
        with temporary.open("w", newline="", encoding="utf-8-sig") as handle:
            writer = csv.writer(handle)
            writer.writerow(header)
            writer.writerows(rows)
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def _json_default(value: Any) -> Any:
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, np.generic):
        return value.item()
    raise TypeError(f"Object of type {type(value).__name__} is not JSON serializable")


def _csv_value(value: Any) -> Any:
    if isinstance(value, (float, np.floating)):
        number = float(value)
        if math.isinf(number):
            return "inf" if number > 0 else "-inf"
        if math.isnan(number):
            return ""
        return f"{number:.9g}"
    return value


def _basic_metric_rows(
    snapshot: PerformanceReportSnapshot,
    metrics: ArrayMetrics,
    language: str,
) -> list[list[str]]:
    wavelength_mm = LIGHT_SPEED_MM_PER_NS / snapshot.frequency_ghz
    x_aperture_lambda = metrics.x_aperture * DISPLAY_SCALE_LAMBDA
    y_aperture_lambda = metrics.y_aperture * DISPLAY_SCALE_LAMBDA
    utilization = (
        100.0 * metrics.unique_count / metrics.virtual_count
        if metrics.virtual_count
        else 0.0
    )
    return [
        [
            _label(language, "channel_count"),
            f"Tx {metrics.tx_count} / Rx {metrics.rx_count}",
        ],
        [
            _label(language, "virtual_utilization"),
            (
                f"{metrics.unique_count}/{metrics.virtual_count} ({utilization:.1f}%), "
                f"{_label(language, 'duplicates')} {metrics.duplicate_excess}"
            ),
        ],
        [
            _label(language, "aperture"),
            (
                f"Az {x_aperture_lambda:.3f} λ / {x_aperture_lambda * wavelength_mm:.3f} mm; "
                f"El {y_aperture_lambda:.3f} λ / {y_aperture_lambda * wavelength_mm:.3f} mm"
            ),
        ],
        [
            _label(language, "resolution"),
            (
                f"Az {_format_number(metrics.azimuth_resolution, '°')}; "
                f"El {_format_number(metrics.elevation_resolution, '°')}"
            ),
        ],
        [
            _label(language, "beamwidth_3db"),
            (
                f"Az {_format_number(metrics.azimuth_3db_beamwidth, '°')}; "
                f"El {_format_number(metrics.elevation_3db_beamwidth, '°')}; "
                f"Az null {_format_number(metrics.azimuth_null_beamwidth, '°')}"
            ),
        ],
        [
            "PSL / ISLR",
            (
                f"Az {metrics.azimuth_psl_db:.2f} dB; El {metrics.elevation_psl_db:.2f} dB; "
                f"2D {metrics.psl_db:.2f} dB; Az ISLR {_format_number(metrics.azimuth_islr_db, ' dB')}"
            ),
        ],
        [
            _label(language, "sidelobe_grating"),
            (
                f"{_label(language, 'first_sidelobe')} "
                f"{_format_db_angle(metrics.azimuth_first_sidelobe_db, metrics.azimuth_first_sidelobe_angle)}; "
                f"{_label(language, 'grating_lobe')} "
                f"{_format_db_angle(metrics.azimuth_grating_lobe_db, metrics.azimuth_grating_lobe_angle)}"
            ),
        ],
        [
            _label(language, "capability"),
            (
                f"{_status_label(metrics.front_radar_status, language)}; "
                f"{_label(language, 'elevation_ambiguity')} "
                f"{_ambiguity_label(metrics.elevation_ambiguity_level, language)}"
            ),
        ],
    ]


def _axis_summary_row(axis_data: _AxisReportData, language: str) -> list[str]:
    summary = axis_data.focus_summary
    metrics = axis_data.angle_metrics
    if metrics.no_fold_left is None or metrics.no_fold_right is None:
        no_fold = "N/A"
    else:
        no_fold = f"{metrics.no_fold_left:g}°..{metrics.no_fold_right:g}°"
    return [
        _axis_label(axis_data.axis, language),
        _format_range(axis_data.focus_range),
        str(summary.frame_count),
        f"{summary.bias_deg:.3f}°",
        f"{summary.rmse_deg:.3f}°",
        f"{summary.p95_abs_error_deg:.3f}°",
        f"{summary.max_abs_error_deg:.3f}° @ {summary.worst_true_angle_deg:g}°",
        f"{summary.reliable_coverage_pct:.1f}%",
        f"{summary.within_error_limit_pct:.1f}%",
        no_fold,
        _format_number(summary.min_peak_margin_db, " dB"),
    ]


def _method_notes(
    snapshot: PerformanceReportSnapshot,
    options: PerformanceReportOptions,
    data: _PerformanceReportData,
) -> list[str]:
    language = options.language
    notes = [
        _label(language, "note_main_plane"),
        _label(language, "note_dbf_pattern"),
        _label(language, "note_grid"),
        _label(language, "note_fov"),
        _label(language, "note_hold"),
    ]
    if snapshot.dbf_dictionary.mode == "custom":
        notes.append(_label(language, "note_custom_dictionary"))
        notes.extend(_dictionary_coverage_notes(snapshot, options, data))
    if data.array_metrics.warning_messages:
        notes.extend(str(message) for message in data.array_metrics.warning_messages)
    return notes


def _dictionary_coverage_notes(
    snapshot: PerformanceReportSnapshot,
    options: PerformanceReportOptions,
    data: _PerformanceReportData,
) -> list[str]:
    notes: list[str] = []
    for axis_data in data.axes:
        table = snapshot.dbf_dictionary.custom_table_for_axis(axis_data.axis)
        axis_name = _axis_label(axis_data.axis, options.language)
        if table is None:
            if options.language == "en":
                notes.append(f"{axis_name} has no external dictionary and uses the ideal fallback.")
            elif options.language == "ja":
                notes.append(f"{axis_name}に外部辞書がないため、理想辞書にフォールバックします。")
            else:
                notes.append(f"{axis_name}未配置外部字典，该轴使用理想字典回退。")
            continue
        if table.is_2d:
            values = (
                table.azimuths_deg
                if axis_data.axis == "azimuth"
                else table.elevations_deg
            )
        else:
            values = table.angles_deg
        coverage_start = float(np.min(values))
        coverage_stop = float(np.max(values))
        selected_start = min(
            axis_data.focus_range.start_deg,
            axis_data.hold_range.start_deg,
        )
        selected_stop = max(
            axis_data.focus_range.stop_deg,
            axis_data.hold_range.stop_deg,
        )
        if selected_start >= coverage_start and selected_stop <= coverage_stop:
            continue
        if options.language == "en":
            notes.append(
                f"Warning: {axis_name} focus/Hold range {selected_start:g}°..{selected_stop:g}° "
                f"exceeds dictionary coverage {coverage_start:g}°..{coverage_stop:g}°."
            )
        elif options.language == "ja":
            notes.append(
                f"警告: {axis_name}の評価/Hold範囲 {selected_start:g}°..{selected_stop:g}° は"
                f"辞書範囲 {coverage_start:g}°..{coverage_stop:g}° を超えています。"
            )
        else:
            notes.append(
                f"警告：{axis_name}关注/Hold 范围 {selected_start:g}°..{selected_stop:g}° "
                f"超出字典覆盖 {coverage_start:g}°..{coverage_stop:g}°。"
            )
    return notes


def _reliable_mask(
    series: DbfAngleFrameSeries,
    ambiguity_margin_db: float,
) -> np.ndarray:
    quality = np.asarray(series.quality_flags, dtype=object)
    margins = series.peak_margins_db
    reliable = quality == DBF_QUALITY_OK
    reliable &= margins > ambiguity_margin_db
    reliable &= np.isfinite(margins) | np.isposinf(margins)
    return reliable


def _style_table(table: Any, font_size: float) -> None:
    table.auto_set_font_size(False)
    table.set_fontsize(font_size)
    table.scale(1.0, 1.35)
    for (row, _column), cell in table.get_celld().items():
        cell.set_edgecolor("#dbe5ef")
        cell.set_linewidth(0.7)
        if row == 0:
            cell.set_facecolor("#eaf3ff")
            cell.set_text_props(fontweight="bold", color="#1e3a5f")
        else:
            cell.set_facecolor("#fbfdff" if row % 2 else "#f5f9fd")


def _format_number(value: float | None, suffix: str = "") -> str:
    if value is None:
        return "N/A"
    number = float(value)
    if math.isinf(number):
        return f"{'-' if number < 0.0 else ''}∞{suffix}"
    return f"{number:.3f}{suffix}"


def _format_db_angle(value: float | None, angle: float | None) -> str:
    if value is None or angle is None:
        return "N/A"
    return f"{value:.2f} dB @ {angle:.2f}°"


def _format_range(angle_range: AngleRange) -> str:
    return f"{angle_range.start_deg:g}°..{angle_range.stop_deg:g}°"


def _notify(callback: ProgressCallback | None, percent: int, message: str) -> None:
    if callback is not None:
        callback(int(percent), message)


def _progress_text(language: str, stage: str, axis: str = "") -> str:
    if stage == "hold":
        return f"{_label(language, 'render_hold')}: {_axis_label(axis, language)}"
    return _label(language, f"progress_{stage}")


def _axis_label(axis: str, language: str) -> str:
    return _label(language, "azimuth" if axis == "azimuth" else "elevation")


def _status_label(value: str, language: str) -> str:
    mapping = {
        "Good": {"zh": "良好", "en": "Good", "ja": "良好"},
        "Acceptable": {"zh": "可接受", "en": "Acceptable", "ja": "許容"},
        "Risky": {"zh": "有风险", "en": "Risky", "ja": "リスクあり"},
        "Bad": {"zh": "较差", "en": "Bad", "ja": "不良"},
    }
    translations = mapping.get(value)
    return value if translations is None else translations.get(language, value)


def _ambiguity_label(value: str, language: str) -> str:
    mapping = {
        "Low": {"zh": "低", "en": "Low", "ja": "低"},
        "Medium": {"zh": "中", "en": "Medium", "ja": "中"},
        "High": {"zh": "高", "en": "High", "ja": "高"},
    }
    translations = mapping.get(value)
    return value if translations is None else translations.get(language, value)


def _label(language: str, key: str) -> str:
    translations = _REPORT_TEXT.get(key)
    if translations is None:
        return key
    return translations.get(language) or translations["zh"]


_REPORT_TEXT: dict[str, dict[str, str]] = {
    "generated": {"zh": "生成时间", "en": "Generated", "ja": "生成日時"},
    "version": {"zh": "软件版本", "en": "App version", "ja": "アプリ版"},
    "frequency": {"zh": "频率", "en": "Frequency", "ja": "周波数"},
    "dictionary": {"zh": "DBF字典", "en": "DBF dictionary", "ja": "DBF辞書"},
    "margin_threshold": {"zh": "竞争峰裕量阈值", "en": "Peak-margin threshold", "ja": "ピーク余裕しきい値"},
    "error_limit": {"zh": "误差门限", "en": "Error limit", "ja": "誤差上限"},
    "basic_metrics": {"zh": "基本阵列与测角性能", "en": "Basic array and angle-performance metrics", "ja": "基本アレイ・測角性能"},
    "metric": {"zh": "指标", "en": "Metric", "ja": "指標"},
    "value": {"zh": "结果", "en": "Value", "ja": "結果"},
    "angle_summary": {"zh": "关注范围测角摘要", "en": "Angle summary in focus ranges", "ja": "評価範囲の測角要約"},
    "axis": {"zh": "维度", "en": "Axis", "ja": "軸"},
    "focus": {"zh": "关注范围", "en": "Focus range", "ja": "評価範囲"},
    "frames": {"zh": "帧", "en": "frames", "ja": "フレーム"},
    "bias": {"zh": "偏差", "en": "Bias", "ja": "バイアス"},
    "max_error": {"zh": "最大误差", "en": "Max error", "ja": "最大誤差"},
    "reliable": {"zh": "可靠覆盖", "en": "Reliable coverage", "ja": "信頼カバレッジ"},
    "pass_rate": {"zh": "误差通过率", "en": "Error pass rate", "ja": "誤差合格率"},
    "no_fold": {"zh": "无折叠范围", "en": "No-fold range", "ja": "非折り返し範囲"},
    "min_margin": {"zh": "最小裕量", "en": "Min margin", "ja": "最小余裕"},
    "method_notes": {"zh": "方法、口径与适用边界", "en": "Method, scope, and limitations", "ja": "方法・範囲・制限"},
    "array_response": {"zh": "当前配置的阵列与响应", "en": "Array and response for the current configuration", "ja": "現在設定のアレイと応答"},
    "physical_array": {"zh": "物理阵列", "en": "Physical array", "ja": "物理アレイ"},
    "virtual_array": {"zh": "虚拟阵列", "en": "Virtual array", "ja": "仮想アレイ"},
    "array_factor_2d": {"zh": "2D阵因子", "en": "2D array factor", "ja": "2Dアレイファクタ"},
    "principal_cuts": {"zh": "阵因子主切面", "en": "Array-factor principal cuts", "ja": "アレイファクタ主断面"},
    "azimuth_cut": {"zh": "方位主切面", "en": "Azimuth cut", "ja": "方位カット"},
    "elevation_cut": {"zh": "俯仰主切面", "en": "Elevation cut", "ja": "仰角カット"},
    "azimuth_angle": {"zh": "方位角 (°)", "en": "Azimuth (deg)", "ja": "方位角 (°)"},
    "elevation_angle": {"zh": "俯仰角 (°)", "en": "Elevation (deg)", "ja": "仰角 (°)"},
    "scan_angle": {"zh": "扫描角 (°)", "en": "Scan angle (deg)", "ja": "スキャン角 (°)"},
    "angle_error_reliability": {"zh": "测角误差与峰值可靠性", "en": "Angle error and peak reliability", "ja": "測角誤差とピーク信頼性"},
    "error_curve": {"zh": "测角误差曲线", "en": "Angle-error curve", "ja": "測角誤差曲線"},
    "unreliable_frame": {"zh": "不可靠帧", "en": "Unreliable frame", "ja": "信頼性なし"},
    "focus_scaled_y_axis_note": {
        "zh": "Y轴按关注范围缩放；范围外折返误差可能被裁切。",
        "en": "Y-axis scaled to the focus range; folded errors outside it may be clipped.",
        "ja": "Y軸は評価範囲に合わせて拡大表示；範囲外の折り返し誤差は切り取られる場合があります。",
    },
    "true_angle": {"zh": "真实角 (°)", "en": "True angle (deg)", "ja": "真値角 (°)"},
    "estimated_minus_true": {"zh": "估计角 - 真实角 (°)", "en": "Estimated - true (deg)", "ja": "推定 - 真値 (°)"},
    "peak_margin": {"zh": "竞争峰裕量", "en": "Competitor-peak margin", "ja": "競合ピーク余裕"},
    "azimuth": {"zh": "方位", "en": "Azimuth", "ja": "方位"},
    "elevation": {"zh": "俯仰", "en": "Elevation", "ja": "仰角"},
    "frame_hold": {"zh": "逐帧 Hold", "en": "frame hold", "ja": "全フレーム Hold"},
    "spectrum_db": {"zh": "dB角谱", "en": "dB spectrum", "ja": "dB角度スペクトル"},
    "spectrum_magnitude": {"zh": "模值角谱", "en": "magnitude spectrum", "ja": "振幅角度スペクトル"},
    "correlation_db": {"zh": "相关性 (dB)", "en": "Correlation (dB)", "ja": "相関 (dB)"},
    "normalized_magnitude": {"zh": "归一化模值", "en": "Normalized magnitude", "ja": "正規化振幅"},
    "frame_color": {"zh": "帧颜色对应真实角", "en": "Frame color by true angle", "ja": "フレーム色の真値角"},
    "fixed_elevation_zero": {"zh": "真实俯仰固定 0°", "en": "true elevation fixed at 0°", "ja": "真値仰角を0°に固定"},
    "fixed_azimuth_zero": {"zh": "真实方位固定 0°", "en": "true azimuth fixed at 0°", "ja": "真値方位を0°に固定"},
    "max_hold_envelope": {"zh": "Max-Hold包络", "en": "Max-hold envelope", "ja": "Max-Hold包絡"},
    "all_frames_overlay": {"zh": "所选每帧全量叠加", "en": "All selected frames overlaid", "ja": "選択全フレーム重ね合わせ"},
    "ideal_track": {"zh": "理想跟踪", "en": "Ideal track", "ja": "理想トラック"},
    "estimated_track": {"zh": "估计峰跟踪", "en": "Estimated peak track", "ja": "推定ピーク軌跡"},
    "angle_response_matrix": {"zh": "真实角×扫描角响应矩阵", "en": "True-angle × scan-angle response", "ja": "真値角×スキャン角応答"},
    "hold_range": {"zh": "Hold真实角范围", "en": "Hold true-angle range", "ja": "Hold真値角範囲"},
    "every_frame_note": {"zh": "1°每帧全部计入，无抽帧", "en": "every 1° frame included; no decimation", "ja": "1°ごとの全フレームを使用"},
    "channel_count": {"zh": "物理通道", "en": "Physical channels", "ja": "物理チャネル"},
    "virtual_utilization": {"zh": "虚拟通道利用率", "en": "Virtual-channel utilization", "ja": "仮想チャネル利用率"},
    "duplicates": {"zh": "重复", "en": "duplicates", "ja": "重複"},
    "aperture": {"zh": "阵列口径", "en": "Array aperture", "ja": "アレイ開口"},
    "resolution": {"zh": "估算分辨率", "en": "Estimated resolution", "ja": "推定分解能"},
    "beamwidth_3db": {"zh": "3 dB / 零点波束宽度", "en": "3 dB / null beamwidth", "ja": "3 dB / ヌルビーム幅"},
    "sidelobe_grating": {"zh": "首旁瓣 / 栅瓣", "en": "First sidelobe / grating lobe", "ja": "第1サイドローブ / グレーティング"},
    "first_sidelobe": {"zh": "首旁瓣", "en": "first sidelobe", "ja": "第1サイドローブ"},
    "grating_lobe": {"zh": "栅瓣", "en": "grating lobe", "ja": "グレーティングローブ"},
    "capability": {"zh": "前视能力评价", "en": "Front-radar capability", "ja": "前方レーダー能力"},
    "elevation_ambiguity": {"zh": "俯仰模糊度", "en": "elevation ambiguity", "ja": "仰角曖昧度"},
    "note_main_plane": {
        "zh": "方位与俯仰结果是正交主平面 1D 诊断：方位扫描固定真实俯仰 0°，俯仰扫描固定真实方位 0°；不等同于完整联合二维误差体验证。",
        "en": "Azimuth and elevation are orthogonal 1D main-plane diagnostics (the other true angle is fixed at 0°), not a full joint 2D error-volume validation.",
        "ja": "方位・仰角は他方の真値角を0°に固定した直交1D主断面診断であり、完全な結合2D誤差検証ではありません。",
    },
    "note_dbf_pattern": {
        "zh": "单元方向图增益会进入阵因子指标；当前 1D DBF 算法不使用 tx/rx 单元方向图，但会使用已配置的通道幅相和 DBF 字典。",
        "en": "Element-pattern gain affects array-factor metrics; the current 1D DBF does not consume tx/rx element patterns, but it does use configured channel amp/phase and the DBF dictionary.",
        "ja": "要素パターンはアレイファクタ指標にのみ反映され、1D DBFはチャネル振幅/位相と辞書を使います。",
    },
    "note_grid": {
        "zh": "DBF 真实角与扫描角均为 -90°..+90°、1°步进；峰值取离散栅格最大值，未做亚栅格插值。",
        "en": "DBF true/scan grids are -90°..+90° in 1° steps; peaks are discrete-grid maxima without sub-bin interpolation.",
        "ja": "DBF真値/スキャングリッドは-90°..+90°、1°間隔で、サブビン補間は行いません。",
    },
    "note_fov": {
        "zh": "阵因子 FOV 为方位 -75°..+75°、俯仰 -15°..+15°；与 DBF 的 -90°..+90° 扫描域不同。",
        "en": "Array-factor FOV (Az -75°..+75°, El -15°..+15°) differs from the DBF -90°..+90° scan domain.",
        "ja": "アレイファクタFOVとDBFの-90°..+90°スキャン領域は異なります。",
    },
    "note_hold": {
        "zh": "Hold 图保留选中范围的每一个 1° 真实角帧；粗虚线仅是附加 Max-Hold 包络，不替代逐帧曲线。",
        "en": "Hold plots retain every selected 1° true-angle frame; the dashed max-hold envelope is supplemental and does not replace per-frame curves.",
        "ja": "Hold図は選択した1°ごとの全フレームを保持し、破線のMax-Holdは補助表示です。",
    },
    "note_custom_dictionary": {
        "zh": "已使用外部字典；请在数据包 manifest 中核对方位/俯仰字典源文件及理想回退轴。",
        "en": "An external dictionary is active; verify per-axis sources and any ideal fallback in the data-package manifest.",
        "ja": "外部辞書を使用中です。manifestで軸ごとの出典と理想辞書へのフォールバックを確認してください。",
    },
    "progress_compute": {"zh": "正在计算报告数据", "en": "Computing report data", "ja": "レポートデータを計算中"},
    "progress_summary": {"zh": "正在绘制摘要", "en": "Rendering summary", "ja": "要約を描画中"},
    "progress_array": {"zh": "正在绘制阵列与响应", "en": "Rendering array response", "ja": "アレイ応答を描画中"},
    "progress_error": {"zh": "正在绘制误差与裕量", "en": "Rendering error and margin", "ja": "誤差と余裕を描画中"},
    "render_hold": {"zh": "正在绘制逐帧 Hold", "en": "Rendering frame hold", "ja": "フレームHoldを描画中"},
    "progress_finalize": {"zh": "正在原子保存 PDF 与数据包", "en": "Saving the PDF and data package atomically", "ja": "PDFとデータをアトミックに保存中"},
    "progress_done": {"zh": "性能报告已完成", "en": "Performance report complete", "ja": "性能レポート完了"},
}
