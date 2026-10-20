"""Service layer between project documents and the computation core.

The engine turns a :class:`~virtual_array.project.Project` into core objects
(array, element pattern, channel patterns, DBF dictionary), runs the analysis,
and returns JSON-ready dictionaries.  Expensive intermediate results are kept
in small LRU caches keyed by the canonical JSON of exactly the project fields
they depend on, so editing the frequency does not recompute DBF spectra and
an animation reuses one 2D scan dictionary.
"""

from __future__ import annotations

import base64
import hashlib
import json
import math
import threading
from collections import OrderedDict, defaultdict
from collections.abc import Callable, Hashable
from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Any, TypeVar

import numpy as np

from .analysis import (
    DBF_CUT_REASON_BOUNDARY,
    DBF_CUT_REASON_COMPETITOR,
    DBF_CUT_REASON_EDGE,
    DBF_CUT_REASON_ERROR_JUMP,
    DBF_CUT_REASON_FLAT,
    DBF_QUALITY_OK,
    DBF_SCAN_FOV,
    DBF_SCAN_GRID_SIZE,
    ArrayMetrics,
    Dbf2dScanner,
    DbfAngleMetrics,
    calculate_metrics_and_psf,
    dbf_angle_frame_series_from_spectra,
    dbf_angle_metrics_from_spectra,
    dbf_azimuth_spectrum_bank,
    dbf_elevation_spectrum_bank,
)
from .assets import AssetStore
from .dbf_dictionary import (
    DBF_DICT_CUSTOM,
    DBF_DICTIONARY_QUALITY_DANGER,
    DBF_DICTIONARY_QUALITY_OK,
    DBF_DICTIONARY_QUALITY_WARNING,
    DbfDictionaryConfig,
    DbfDictionaryTable,
    dictionary_phase_preview,
    dictionary_quality_report,
    load_dbf_dictionary_table,
)
from .element_pattern import (
    PATTERN_KIND_AMPLITUDE,
    PATTERN_KIND_PHASE,
    ChannelPatternSet,
    ElementPattern,
    PatternSeries,
    load_element_pattern,
    load_hfss_pattern_series_columns,
    load_hfss_summary_pattern,
    pattern_cut_metrics,
)
from .geometry import AntennaArray
from .project import (
    ChannelPatternBinding,
    Project,
    json_number,
    layout_to_v1,
    project_array,
)
from .version import APP_VERSION

AXES = ("azimuth", "elevation")
HALF_LAMBDA_TO_LAMBDA = 0.5
ROUND_DECIMALS = 9

CUT_REASON_CODES = {
    DBF_CUT_REASON_COMPETITOR: "competitor",
    DBF_CUT_REASON_ERROR_JUMP: "error_jump",
    DBF_CUT_REASON_EDGE: "boundary_limited",
    DBF_CUT_REASON_FLAT: "unreliable",
    DBF_CUT_REASON_BOUNDARY: "data_boundary",
    DBF_QUALITY_OK: "normal",
}

T = TypeVar("T")


class ProjectComputationError(ValueError):
    """A project is valid JSON but cannot be evaluated (e.g. mismatched files)."""


class _LruCache:
    def __init__(self, maxsize: int) -> None:
        self.maxsize = maxsize
        self._items: OrderedDict[Hashable, Any] = OrderedDict()
        self._lock = threading.Lock()

    def get_or_create(self, key: Hashable, factory: Callable[[], T]) -> T:
        with self._lock:
            if key in self._items:
                self._items.move_to_end(key)
                return self._items[key]
        value = factory()
        with self._lock:
            self._items[key] = value
            self._items.move_to_end(key)
            while len(self._items) > self.maxsize:
                self._items.popitem(last=False)
        return value

    def clear(self) -> None:
        with self._lock:
            self._items.clear()


@dataclass(frozen=True)
class StudyContext:
    project: Project
    array: AntennaArray
    element_pattern: ElementPattern | None
    channel_patterns: ChannelPatternSet
    dictionary: DbfDictionaryConfig


def encode_array(values: np.ndarray, dtype: str = "float32") -> dict[str, Any]:
    """Compact binary transport for large numeric matrices."""
    array = np.ascontiguousarray(np.asarray(values, dtype=dtype))
    return {
        "dtype": dtype,
        "shape": list(array.shape),
        "data": base64.b64encode(array.tobytes()).decode("ascii"),
    }


def num(value: float | None, digits: int | None = None) -> float | str | None:
    """JSON-safe number: ±inf become strings, NaN becomes null."""
    if value is None:
        return None
    number = float(value)
    if math.isnan(number):
        return None
    if math.isinf(number):
        return "Infinity" if number > 0 else "-Infinity"
    return round(number, digits) if digits is not None else number


def num_list(values: np.ndarray, digits: int | None = None) -> list[float | str | None]:
    return [num(value, digits) for value in np.asarray(values, dtype=float).tolist()]


def _digest(payload: Any) -> str:
    text = json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha1(text.encode("utf-8")).hexdigest()


class Engine:
    def __init__(self, assets: AssetStore) -> None:
        self.assets = assets
        self._element_patterns = _LruCache(16)
        self._pattern_columns = _LruCache(32)
        self._dictionary_tables = _LruCache(16)
        self._metrics = _LruCache(16)
        self._banks = _LruCache(16)
        self._scanners = _LruCache(2)

    # ── Project → core objects ───────────────────────────────────────

    def context(self, project: Project) -> StudyContext:
        self._require_assets(project)
        array = project_array(project)
        return StudyContext(
            project=project,
            array=array,
            element_pattern=self._element_pattern(project),
            channel_patterns=self._channel_pattern_set(project),
            dictionary=self._dictionary_config(project, array),
        )

    def _require_assets(self, project: Project) -> None:
        missing = sorted(asset for asset in project.asset_ids() if not self.assets.exists(asset))
        if missing:
            raise ProjectComputationError(
                "Referenced data files are missing on this server: "
                + ", ".join(asset[:12] for asset in missing)
            )

    def _element_pattern(self, project: Project) -> ElementPattern | None:
        settings = project.element_pattern
        if settings is None:
            return None
        return self.element_pattern(settings.asset, settings.swap_axes)

    def element_pattern(self, asset: str, swap_axes: bool = False) -> ElementPattern:
        def build() -> ElementPattern:
            pattern = load_element_pattern(self.assets.path(asset))
            return pattern.swapped_axes() if swap_axes else pattern

        return self._element_patterns.get_or_create((asset, swap_axes), build)

    def pattern_columns(self, asset: str, kind: str) -> list[PatternSeries]:
        return self._pattern_columns.get_or_create(
            (asset, kind),
            lambda: load_hfss_pattern_series_columns(self.assets.path(asset), value_kind=kind),
        )

    def _channel_pattern_set(self, project: Project) -> ChannelPatternSet:
        patterns = ChannelPatternSet()
        for binding in project.channel_patterns:
            series = self.pattern_columns(binding.asset, binding.kind)
            if binding.column_index >= len(series):
                raise ProjectComputationError(
                    f"Channel pattern for {binding.channel} refers to data column "
                    f"{binding.column_index + 1}, but the file has {len(series)}."
                )
            patterns.set_series(
                binding.channel, binding.kind, binding.plane, series[binding.column_index]
            )
        return patterns

    def _dictionary_table(
        self, asset: str, array: AntennaArray, channel_mode: str
    ) -> DbfDictionaryTable:
        key = (asset, len(array.tx), len(array.rx), channel_mode)

        def build() -> DbfDictionaryTable:
            try:
                return load_dbf_dictionary_table(
                    self.assets.path(asset), array, channel_mode=channel_mode
                )
            except ValueError as exc:
                raise ProjectComputationError(str(exc)) from exc

        return self._dictionary_tables.get_or_create(key, build)

    def _dictionary_config(self, project: Project, array: AntennaArray) -> DbfDictionaryConfig:
        settings = project.dbf_dictionary
        if settings.mode != DBF_DICT_CUSTOM:
            return DbfDictionaryConfig(mode=settings.mode)
        tables = {
            axis: (
                self._dictionary_table(asset, array, settings.channel_mode)
                if asset is not None
                else None
            )
            for axis, asset in (
                ("azimuth", settings.azimuth_asset),
                ("elevation", settings.elevation_asset),
            )
        }
        return DbfDictionaryConfig(
            mode=DBF_DICT_CUSTOM,
            custom_azimuth_table=tables["azimuth"],
            custom_elevation_table=tables["elevation"],
            custom_phase_reversed=settings.phase_reversed,
            custom_zero_phase_calibrated=settings.zero_phase_calibrated,
        )

    # ── Cache keys ───────────────────────────────────────────────────

    @staticmethod
    def _pattern_key(project: Project) -> str:
        return _digest(
            project.model_dump(include={"layout", "element_pattern", "channel_patterns"})
        )

    @staticmethod
    def _dbf_key(project: Project) -> str:
        return _digest(
            project.model_dump(include={"layout", "channel_patterns", "dbf_dictionary"})
        )

    # ── Evaluations ──────────────────────────────────────────────────

    def _array_metrics(self, context: StudyContext) -> tuple[np.ndarray, np.ndarray, np.ndarray, ArrayMetrics]:
        def build() -> tuple[np.ndarray, np.ndarray, np.ndarray, ArrayMetrics]:
            unique, counts = context.array.unique_virtual_xy(decimals=ROUND_DECIMALS)
            return calculate_metrics_and_psf(
                context.array,
                unique,
                counts,
                tx_pattern=context.element_pattern,
                rx_pattern=context.element_pattern,
                channel_patterns=context.channel_patterns,
            )

        return self._metrics.get_or_create(self._pattern_key(context.project), build)

    def _bank(self, context: StudyContext, axis: str) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        if axis not in AXES:
            raise ValueError(f"Unknown DBF axis: {axis!r}")
        bank_function = dbf_azimuth_spectrum_bank if axis == "azimuth" else dbf_elevation_spectrum_bank

        def build() -> tuple[np.ndarray, np.ndarray, np.ndarray]:
            try:
                return bank_function(
                    context.array,
                    tx_pattern=context.element_pattern,
                    rx_pattern=context.element_pattern,
                    channel_patterns=context.channel_patterns,
                    dbf_dictionary=context.dictionary,
                )
            except ValueError as exc:
                raise ProjectComputationError(str(exc)) from exc

        return self._banks.get_or_create((self._dbf_key(context.project), axis), build)

    def evaluate(self, project: Project) -> dict[str, Any]:
        context = self.context(project)
        array = context.array
        af_db, azimuths, elevations, metrics = self._array_metrics(context)
        _ = af_db, azimuths, elevations
        capability = axis_capability(metrics)
        half_wavelength_mm = project.wavelength_mm / 2.0

        angle: dict[str, Any] = {}
        for axis in AXES:
            if not capability[axis]:
                angle[axis] = None
                continue
            try:
                true_angles, scan_angles, spectra = self._bank(context, axis)
                angle[axis] = angle_metrics_payload(
                    dbf_angle_metrics_from_spectra(
                        true_angles,
                        scan_angles,
                        spectra,
                        ambiguity_margin_db=project.ambiguity_margin_db,
                    )
                )
            except ProjectComputationError as exc:
                angle[axis] = {"error": str(exc)}

        utilization = metrics.unique_count / metrics.virtual_count if metrics.virtual_count else 0.0
        return {
            "wavelength_mm": project.wavelength_mm,
            "half_wavelength_mm": half_wavelength_mm,
            "summary": {
                "tx_count": metrics.tx_count,
                "rx_count": metrics.rx_count,
                "virtual_count": metrics.virtual_count,
                "unique_count": metrics.unique_count,
                "duplicate_locations": metrics.duplicate_locations,
                "duplicate_excess": metrics.duplicate_excess,
                "utilization": utilization,
                "x_aperture_lambda": metrics.x_aperture * HALF_LAMBDA_TO_LAMBDA,
                "y_aperture_lambda": metrics.y_aperture * HALF_LAMBDA_TO_LAMBDA,
                "x_aperture_mm": metrics.x_aperture * half_wavelength_mm,
                "y_aperture_mm": metrics.y_aperture * half_wavelength_mm,
            },
            "metrics": array_metrics_payload(metrics),
            "capability": capability,
            "virtual_points": virtual_points_payload(array),
            "angle": angle,
            "pattern_status": pattern_status(project),
            "notes": note_codes(metrics),
        }

    def dbf_bank(self, project: Project, axis: str) -> dict[str, Any]:
        context = self.context(project)
        true_angles, scan_angles, spectra = self._bank(context, axis)
        series = dbf_angle_frame_series_from_spectra(true_angles, scan_angles, spectra)
        metrics = dbf_angle_metrics_from_spectra(
            true_angles,
            scan_angles,
            spectra,
            ambiguity_margin_db=project.ambiguity_margin_db,
        )
        return {
            "axis": axis,
            "true_angles": num_list(true_angles),
            "scan_angles": num_list(scan_angles),
            "spectra_db": encode_array(spectra),
            "frames": {
                "estimated": num_list(series.estimated_angles_deg),
                "errors": num_list(series.errors_deg, 6),
                "main_peak_db": num_list(series.main_peak_db, 4),
                "competitor_peak_db": num_list(series.competitor_peak_db, 4),
                "margins_db": num_list(series.peak_margins_db, 4),
                "quality": [CUT_REASON_CODES.get(flag, flag) for flag in series.quality_flags],
            },
            "metrics": angle_metrics_payload(metrics),
        }

    def _scanner(self, context: StudyContext) -> Dbf2dScanner:
        return self._scanners.get_or_create(
            self._dbf_key(context.project),
            lambda: Dbf2dScanner(
                context.array,
                channel_patterns=context.channel_patterns,
                dbf_dictionary=context.dictionary,
            ),
        )

    def dbf_2d(self, project: Project, frames: list[tuple[float, float]]) -> dict[str, Any]:
        context = self.context(project)
        scanner = self._scanner(context)
        results = []
        for true_az, true_el in frames:
            try:
                spectrum = scanner.spectrum_db(true_az, true_el)
            except ValueError as exc:
                raise ProjectComputationError(str(exc)) from exc
            peak_el_index, peak_az_index = np.unravel_index(int(np.argmax(spectrum)), spectrum.shape)
            results.append(
                {
                    "true_azimuth": float(true_az),
                    "true_elevation": float(true_el),
                    "peak_azimuth": float(scanner.scan_azimuths_deg[peak_az_index]),
                    "peak_elevation": float(scanner.scan_elevations_deg[peak_el_index]),
                    "peak_db": float(spectrum[peak_el_index, peak_az_index]),
                    "spectrum_db": encode_array(spectrum),
                }
            )
        return {
            "scan_azimuths": num_list(scanner.scan_azimuths_deg),
            "scan_elevations": num_list(scanner.scan_elevations_deg),
            "frames": results,
        }

    # ── Import helpers ───────────────────────────────────────────────

    def element_pattern_preview(self, asset: str, swap_axes: bool = False) -> dict[str, Any]:
        pattern = self.element_pattern(asset, swap_axes)
        horizontal = pattern.horizontal_gain_db
        elevation = pattern.elevation_gain_db
        return {
            "name": pattern.name,
            "angle_column": pattern.angle_column,
            "horizontal_column": pattern.horizontal_column,
            "elevation_column": pattern.elevation_column,
            "angles": num_list(pattern.angles_deg),
            "horizontal_gain_db": num_list(horizontal, 4),
            "elevation_gain_db": None if elevation is None else num_list(elevation, 4),
            "horizontal_metrics": asdict(pattern_cut_metrics(pattern.angles_deg, horizontal)),
            "elevation_metrics": (
                None
                if elevation is None
                else asdict(pattern_cut_metrics(pattern.angles_deg, elevation))
            ),
        }

    def resolve_channel_patterns(
        self,
        project: Project,
        asset: str,
        kind: str,
        plane: str,
        target: str,
        channel: str | None = None,
    ) -> list[ChannelPatternBinding]:
        """Map the data columns of an HFSS export onto channel names.

        ``channel`` set: the first data column is assigned to that one channel.
        Otherwise the file is a summary export whose columns map left-to-right
        (or by matching header names) onto the physical or virtual channels.
        """
        if kind not in {PATTERN_KIND_AMPLITUDE, PATTERN_KIND_PHASE}:
            raise ValueError(f"Unknown pattern kind: {kind!r}")
        series = self.pattern_columns(asset, kind)
        if channel is not None:
            known = {*project.physical_channel_names, *project.virtual_channel_names}
            if channel not in known:
                raise ValueError(f"Unknown channel: {channel}")
            return [
                ChannelPatternBinding(
                    channel=channel,
                    kind=kind,
                    plane=plane,
                    asset=asset,
                    column_index=0,
                    column=series[0].value_column,
                )
            ]
        channel_names = (
            project.virtual_channel_names if target == "virtual" else project.physical_channel_names
        )
        mapping = load_hfss_summary_pattern(
            self.assets.path(asset), channel_names, value_kind=kind
        )
        column_index = {item.value_column: index for index, item in enumerate(series)}
        return [
            ChannelPatternBinding(
                channel=channel_name,
                kind=kind,
                plane=plane,
                asset=asset,
                column_index=column_index[item.value_column],
                column=item.value_column,
            )
            for channel_name, item in mapping.items()
        ]

    def dictionary_preview(self, project: Project, axis: str) -> dict[str, Any]:
        if axis not in AXES:
            raise ValueError(f"Unknown DBF axis: {axis!r}")
        context = self.context(project)
        angles = np.linspace(DBF_SCAN_FOV[0], DBF_SCAN_FOV[1], DBF_SCAN_GRID_SIZE)
        try:
            matrix = context.dictionary.scan_matrix(
                context.array,
                angles,
                axis=axis,
                channel_patterns=context.channel_patterns,
            )
        except ValueError as exc:
            raise ProjectComputationError(str(exc)) from exc
        report = dictionary_quality_report(matrix, angles)
        settings = project.dbf_dictionary
        capability_limited = report.channel_count <= 1 or settings.mode != DBF_DICT_CUSTOM
        severity = report.severity
        if severity == DBF_DICTIONARY_QUALITY_DANGER and capability_limited:
            severity = DBF_DICTIONARY_QUALITY_WARNING
        if severity not in {
            DBF_DICTIONARY_QUALITY_OK,
            DBF_DICTIONARY_QUALITY_WARNING,
            DBF_DICTIONARY_QUALITY_DANGER,
        }:
            severity = DBF_DICTIONARY_QUALITY_WARNING
        tables = {
            "azimuth": context.dictionary.custom_azimuth_table,
            "elevation": context.dictionary.custom_elevation_table,
        }
        return {
            "axis": axis,
            "angles": num_list(angles),
            "phase_deg": encode_array(dictionary_phase_preview(matrix)),
            "channel_count": int(matrix.shape[1]),
            "quality": {**asdict(report), "severity": severity},
            "tables": {
                name: (
                    None
                    if table is None
                    else {
                        "channel_mode": table.channel_mode,
                        "value_format": table.value_format,
                        "rows": int(table.values.shape[0]),
                        "columns": list(table.column_names),
                        "is_2d": table.is_2d,
                    }
                )
                for name, table in tables.items()
            },
        }

    # ── Exports ──────────────────────────────────────────────────────

    def layout_document(self, project: Project) -> dict[str, Any]:
        """Desktop-compatible v1 layout JSON including the evaluation block."""
        context = self.context(project)
        _af, _az, _el, metrics = self._array_metrics(context)
        return layout_to_v1(project, layout_evaluation(project, metrics, self.assets))

    def report_snapshot(self, project: Project):  # noqa: ANN201
        from .performance_report import PerformanceReportSnapshot

        context = self.context(project)
        return PerformanceReportSnapshot(
            array=context.array,
            frequency_ghz=project.frequency_ghz,
            ambiguity_margin_db=project.ambiguity_margin_db,
            dbf_dictionary=context.dictionary,
            element_pattern=context.element_pattern,
            channel_patterns=context.channel_patterns,
            current_config=self.layout_document(project),
            app_version=APP_VERSION,
            created_at=datetime.now().astimezone(),
        )


# ── Payload helpers ──────────────────────────────────────────────────


def axis_capability(metrics: ArrayMetrics) -> dict[str, bool]:
    azimuth = metrics.azimuth_resolution is not None and metrics.x_aperture > 0
    elevation = metrics.elevation_resolution is not None and metrics.y_aperture > 0
    return {"azimuth": azimuth, "elevation": elevation, "two_d": azimuth and elevation}


def array_metrics_payload(metrics: ArrayMetrics) -> dict[str, Any]:
    payload: dict[str, Any] = {}
    for key, value in asdict(metrics).items():
        if isinstance(value, float):
            payload[key] = num(value)
        elif isinstance(value, tuple):
            payload[key] = list(value)
        else:
            payload[key] = value
    return payload


def angle_metrics_payload(metrics: DbfAngleMetrics) -> dict[str, Any]:
    return {
        "no_fold_left": num(metrics.no_fold_left),
        "no_fold_right": num(metrics.no_fold_right),
        "no_fold_width": num(metrics.no_fold_width),
        "no_fold_max_abs_error": num(metrics.no_fold_max_abs_error),
        "focus_max_abs_error": num(metrics.focus_max_abs_error),
        "center_error": num(metrics.center_error),
        "min_peak_margin_db": num(metrics.min_peak_margin_db),
        "center_peak_margin_db": num(metrics.center_peak_margin_db),
        "negative_cut_reason": CUT_REASON_CODES.get(
            metrics.negative_cut_reason, metrics.negative_cut_reason
        ),
        "positive_cut_reason": CUT_REASON_CODES.get(
            metrics.positive_cut_reason, metrics.positive_cut_reason
        ),
    }


def virtual_points_payload(array: AntennaArray) -> list[dict[str, Any]]:
    groups: dict[tuple[float, float], list[str]] = defaultdict(list)
    for point in array.virtual_points():
        key = (round(point.x, ROUND_DECIMALS), round(point.y, ROUND_DECIMALS))
        groups[key].append(f"{point.tx_name}-{point.rx_name}")
    return [
        {
            "x": x * HALF_LAMBDA_TO_LAMBDA,
            "y": y * HALF_LAMBDA_TO_LAMBDA,
            "count": len(pairs),
            "pairs": pairs,
        }
        for (x, y), pairs in sorted(groups.items())
    ]


def pattern_status(project: Project) -> dict[str, str]:
    """Amplitude/phase source state shown in the header: ideal, imported or mixed."""
    configured: dict[str, set[str]] = {PATTERN_KIND_AMPLITUDE: set(), PATTERN_KIND_PHASE: set()}
    for binding in project.channel_patterns:
        configured[binding.kind].add(binding.channel)
    physical = project.physical_channel_names
    virtual = project.virtual_channel_names
    status: dict[str, str] = {}
    for kind in (PATTERN_KIND_AMPLITUDE, PATTERN_KIND_PHASE):
        physical_count = len(configured[kind] & set(physical))
        virtual_count = len(configured[kind] & set(virtual))
        if physical_count == 0 and virtual_count == 0:
            imported = kind == PATTERN_KIND_AMPLITUDE and project.element_pattern is not None
            status[kind] = "imported" if imported else "ideal"
            continue
        physical_full = bool(physical) and physical_count == len(physical)
        virtual_full = bool(virtual) and virtual_count == len(virtual)
        physical_whole = physical_count in (0, len(physical))
        virtual_whole = virtual_count in (0, len(virtual))
        whole = (physical_full or virtual_full) and physical_whole and virtual_whole
        status[kind] = "imported" if whole else "mixed"
    return status


def note_codes(metrics: ArrayMetrics) -> list[str]:
    notes = []
    if metrics.duplicate_excess > 0:
        notes.append("duplicate_virtual")
    if metrics.azimuth_psl_db > -10.0:
        notes.append("windowing")
    if metrics.elevation_ambiguity_level == "High":
        notes.append("ambiguity_high")
    elif metrics.elevation_ambiguity_level == "Medium":
        notes.append("ambiguity_medium")
    return notes


_NOTE_TEXT_ZH = {
    "duplicate_virtual": "存在重复虚拟通道",
    "windowing": "建议加窗降低旁瓣",
    "ambiguity_high": "俯仰模糊风险高",
    "ambiguity_medium": "俯仰模糊风险中",
}


def layout_evaluation(project: Project, metrics: ArrayMetrics, assets: AssetStore) -> dict[str, Any]:
    """The ``evaluation`` block of the desktop layout JSON (kept field-compatible)."""
    half_wavelength_mm = project.wavelength_mm / 2.0
    utilization = metrics.unique_count / metrics.virtual_count if metrics.virtual_count else 0.0
    settings = project.dbf_dictionary

    def asset_name(asset: str | None) -> str | None:
        if asset is None:
            return None
        try:
            return assets.info(asset).filename
        except KeyError:
            return asset

    element_info: dict[str, Any] = {"mode": "isotropic"}
    if project.element_pattern is not None:
        element_info = {
            "mode": "loaded",
            "source": asset_name(project.element_pattern.asset),
            "swap_axes": project.element_pattern.swap_axes,
        }
    channels = sorted({binding.channel for binding in project.channel_patterns})
    return {
        "frequency_ghz": json_number(project.frequency_ghz, 6),
        "ambiguity_margin_db": json_number(project.ambiguity_margin_db, 3),
        "dbf_dictionary": {
            "mode": settings.mode,
            "custom_sources": {
                "azimuth": asset_name(settings.azimuth_asset),
                "elevation": asset_name(settings.elevation_asset),
            },
            "custom_phase_reversed": settings.phase_reversed,
            "custom_zero_phase_calibrated": settings.zero_phase_calibrated,
        },
        "virtual_utilization": {
            "unique_points": metrics.unique_count,
            "virtual_channels": metrics.virtual_count,
            "ratio": json_number(utilization, 6),
            "duplicate_points": metrics.duplicate_excess,
        },
        "az_aperture_mm": json_number(metrics.x_aperture * half_wavelength_mm, 3),
        "az_aperture_lambda": json_number(metrics.x_aperture * HALF_LAMBDA_TO_LAMBDA, 9),
        "az_resolution_deg": json_number(metrics.azimuth_resolution, 3),
        "az_3db_bw_deg": json_number(metrics.azimuth_3db_beamwidth, 3),
        "az_psl_db": json_number(metrics.azimuth_psl_db, 3),
        "first_sidelobe": {
            "level_db": json_number(metrics.azimuth_first_sidelobe_db, 3),
            "az_deg": json_number(metrics.azimuth_first_sidelobe_angle, 3),
        },
        "az_grating_lobe": {
            "level_db": json_number(metrics.azimuth_grating_lobe_db, 3),
            "az_deg": json_number(metrics.azimuth_grating_lobe_angle, 3),
        },
        "az_islr_db": json_number(metrics.azimuth_islr_db, 3),
        "el_3db_bw_deg": json_number(metrics.elevation_3db_beamwidth, 3),
        "el_psl_db": json_number(metrics.elevation_psl_db, 3),
        "psl_2d_worst_db": json_number(metrics.psl_db, 3),
        "psl_2d_location_deg": {
            "az": json_number(metrics.sidelobe_azimuth, 3),
            "el": json_number(metrics.sidelobe_elevation, 3),
        },
        "element_pattern": element_info,
        "channel_patterns": {
            "mode": "ideal" if not channels else "channel_patterns",
            "configured_channels": len(channels),
            "configured_series": len(project.channel_patterns),
        },
        "notes": [_NOTE_TEXT_ZH[code] for code in note_codes(metrics)],
    }
