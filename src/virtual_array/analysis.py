from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

from .dbf_dictionary import DbfDictionaryConfig
from .element_pattern import ChannelPatternSet, ElementPattern
from .geometry import AntennaArray


AZIMUTH_FOV = (-75.0, 75.0)
ELEVATION_FOV = (-15.0, 15.0)
AF_GRID_SIZE = 181
DBF_SCAN_FOV = (-90.0, 90.0)
DBF_SCAN_STEP_DEG = 1.0
DBF_SCAN_GRID_SIZE = 181
DBF_DEFAULT_STEERING_SIGN = -1
DBF_SIGN_SELECTION_LIMIT_DEG = 70.0
DBF_ANGLE_FOCUS_DEG = 70.0
DBF_AMBIGUITY_MARGIN_DB = 0.5
DBF_ERROR_JUMP_LIMIT_DEG = 30.0
DBF_FLAT_TOP_TOLERANCE_DB = 0.1
DBF_FLAT_TOP_WIDTH_DEG = 60.0
DBF_CUT_REASON_COMPETITOR = "竞争峰模糊"
DBF_CUT_REASON_ERROR_JUMP = "误差跳变"
DBF_CUT_REASON_EDGE = "边界受限"
DBF_CUT_REASON_FLAT = "谱不可靠"
DBF_CUT_REASON_BOUNDARY = "到达数据边界"
DBF_QUALITY_OK = "正常"
MAINLOBE_GUARD_AZ = 2.0
MAINLOBE_GUARD_EL = 6.0


@dataclass(frozen=True)
class ArrayMetrics:
    tx_count: int
    rx_count: int
    virtual_count: int
    unique_count: int
    duplicate_locations: int
    duplicate_excess: int
    x_aperture: float
    y_aperture: float
    aperture_ratio: float | None
    azimuth_resolution: float | None
    azimuth_3db_beamwidth: float | None
    azimuth_null_beamwidth: float | None
    azimuth_islr_db: float | None
    azimuth_first_sidelobe_db: float | None
    azimuth_first_sidelobe_angle: float | None
    azimuth_grating_lobe_db: float | None
    azimuth_grating_lobe_angle: float | None
    elevation_resolution: float | None
    elevation_3db_beamwidth: float | None
    psl_db: float
    azimuth_psl_db: float
    elevation_psl_db: float
    front_radar_status: str
    elevation_ambiguity_level: str
    warning_messages: tuple[str, ...]
    mainlobe_azimuth: float
    mainlobe_elevation: float
    sidelobe_azimuth: float
    sidelobe_elevation: float
    psl_grade: str


@dataclass(frozen=True)
class DbfAngleMetrics:
    no_fold_left: float | None
    no_fold_right: float | None
    no_fold_max_abs_error: float | None
    focus_max_abs_error: float | None
    center_error: float | None
    min_peak_margin_db: float | None
    center_peak_margin_db: float | None
    negative_cut_reason: str | None
    positive_cut_reason: str | None

    @property
    def no_fold_width(self) -> float | None:
        if self.no_fold_left is None or self.no_fold_right is None:
            return None
        return self.no_fold_right - self.no_fold_left


@dataclass(frozen=True)
class _DbfNoFoldResult:
    no_fold_left: float | None
    no_fold_right: float | None
    no_fold_max_abs_error: float | None
    negative_cut_reason: str | None
    positive_cut_reason: str | None


def calculate_metrics_and_psf(
    array: AntennaArray,
    unique: np.ndarray | None = None,
    counts: np.ndarray | None = None,
    decimals: int = 9,
    tx_pattern: ElementPattern | None = None,
    rx_pattern: ElementPattern | None = None,
    channel_patterns: ChannelPatternSet | None = None,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, ArrayMetrics]:
    if unique is None or counts is None:
        unique, counts = array.unique_virtual_xy(decimals=decimals)

    virtual_xy = array.virtual_xy()
    x_aperture = float(np.ptp(unique[:, 0])) if len(unique) else 0.0
    y_aperture = float(np.ptp(unique[:, 1])) if len(unique) else 0.0
    aperture_ratio = x_aperture / y_aperture if y_aperture > 0 else None
    azimuth_resolution = estimate_resolution(x_aperture)
    elevation_resolution = estimate_resolution(y_aperture)

    azimuths = np.linspace(AZIMUTH_FOV[0], AZIMUTH_FOV[1], AF_GRID_SIZE)
    elevations = np.linspace(ELEVATION_FOV[0], ELEVATION_FOV[1], AF_GRID_SIZE)
    az_grid, el_grid = np.meshgrid(azimuths, elevations)
    az_rad = np.radians(az_grid)
    el_rad = np.radians(el_grid)
    u = np.sin(az_rad) * np.cos(el_rad)
    v = np.sin(el_rad)

    phase = np.pi * (
        virtual_xy[:, 0, None, None] * u[None, :, :]
        + virtual_xy[:, 1, None, None] * v[None, :, :]
    )
    steering = np.exp(1j * phase)
    channel_weight = _channel_pattern_weight(
        channel_patterns, array, az_grid, el_grid
    )
    array_factor = (steering * channel_weight).sum(axis=0)
    pattern_weight = _element_pattern_weight(tx_pattern, az_grid, el_grid)
    pattern_weight *= _element_pattern_weight(rx_pattern, az_grid, el_grid)
    af = np.abs(array_factor * pattern_weight)
    af /= af.max() if af.max() else 1.0
    af_db = 20.0 * np.log10(np.maximum(af, 1e-6))

    main_index = np.unravel_index(np.argmax(af_db), af_db.shape)
    main_azimuth = float(az_grid[main_index])
    main_elevation = float(el_grid[main_index])
    main_lobe_mask = (
        (np.abs(az_grid - main_azimuth) <= MAINLOBE_GUARD_AZ)
        & (np.abs(el_grid - main_elevation) <= MAINLOBE_GUARD_EL)
    )
    sidelobe_values = np.where(~main_lobe_mask, af_db, -np.inf)
    sidelobe_index = np.unravel_index(
        np.argmax(sidelobe_values), sidelobe_values.shape
    )
    psl_db = float(sidelobe_values[sidelobe_index])
    az0_index = int(np.argmin(np.abs(azimuths)))
    el0_index = int(np.argmin(np.abs(elevations)))
    azimuth_cut = af_db[el0_index, :]
    elevation_cut = af_db[:, az0_index]

    az_cut_mask = np.abs(azimuths) > MAINLOBE_GUARD_AZ
    el_cut_mask = np.abs(elevations) > MAINLOBE_GUARD_EL
    azimuth_psl_db = float(np.max(np.where(az_cut_mask, azimuth_cut, -np.inf)))
    elevation_psl_db = float(np.max(np.where(el_cut_mask, elevation_cut, -np.inf)))

    azimuth_3db_beamwidth, azimuth_null_beamwidth, azimuth_islr_db = (
        azimuth_cut_metrics(azimuths, azimuth_cut)
    )
    azimuth_first_sidelobe_db, azimuth_first_sidelobe_angle = (
        azimuth_first_sidelobe(azimuths, azimuth_cut)
    )
    azimuth_grating_lobe_db, azimuth_grating_lobe_angle = azimuth_grating_lobe(
        azimuths, azimuth_cut
    )
    elevation_3db_beamwidth = cut_3db_beamwidth(elevations, elevation_cut)

    unique_ratio = len(unique) / len(virtual_xy) if len(virtual_xy) else 0.0
    front_status, warnings = evaluate_front_radar(
        azimuth_resolution, azimuth_psl_db, unique_ratio, psl_db
    )

    metrics = ArrayMetrics(
        tx_count=len(array.tx),
        rx_count=len(array.rx),
        virtual_count=len(virtual_xy),
        unique_count=len(unique),
        duplicate_locations=int(np.count_nonzero(counts > 1)),
        duplicate_excess=int(len(virtual_xy) - len(unique)),
        x_aperture=x_aperture,
        y_aperture=y_aperture,
        aperture_ratio=aperture_ratio,
        azimuth_resolution=azimuth_resolution,
        azimuth_3db_beamwidth=azimuth_3db_beamwidth,
        azimuth_null_beamwidth=azimuth_null_beamwidth,
        azimuth_islr_db=azimuth_islr_db,
        azimuth_first_sidelobe_db=azimuth_first_sidelobe_db,
        azimuth_first_sidelobe_angle=azimuth_first_sidelobe_angle,
        azimuth_grating_lobe_db=azimuth_grating_lobe_db,
        azimuth_grating_lobe_angle=azimuth_grating_lobe_angle,
        elevation_resolution=elevation_resolution,
        elevation_3db_beamwidth=elevation_3db_beamwidth,
        psl_db=psl_db,
        azimuth_psl_db=azimuth_psl_db,
        elevation_psl_db=elevation_psl_db,
        front_radar_status=front_status,
        elevation_ambiguity_level=ambiguity_level(psl_db),
        warning_messages=warnings,
        mainlobe_azimuth=main_azimuth,
        mainlobe_elevation=main_elevation,
        sidelobe_azimuth=float(az_grid[sidelobe_index]),
        sidelobe_elevation=float(el_grid[sidelobe_index]),
        psl_grade=psl_grade(psl_db),
    )
    return af_db, azimuths, elevations, metrics


def dbf_azimuth_spectrum(
    array: AntennaArray,
    true_angle_deg: float = 0.0,
    angles_deg: np.ndarray | None = None,
    tx_pattern: ElementPattern | None = None,
    rx_pattern: ElementPattern | None = None,
    channel_patterns: ChannelPatternSet | None = None,
    dbf_dictionary: DbfDictionaryConfig | None = None,
) -> tuple[np.ndarray, np.ndarray]:
    """Return one conventional DBF azimuth spectrum for a true source angle."""
    true_angles, scan_angles, spectra_db = dbf_azimuth_spectrum_bank(
        array,
        true_angles_deg=np.asarray([true_angle_deg], dtype=float),
        scan_angles_deg=angles_deg,
        tx_pattern=tx_pattern,
        rx_pattern=rx_pattern,
        channel_patterns=channel_patterns,
        dbf_dictionary=dbf_dictionary,
    )
    _ = true_angles
    return scan_angles, spectra_db[0]


def dbf_elevation_spectrum(
    array: AntennaArray,
    true_angle_deg: float = 0.0,
    angles_deg: np.ndarray | None = None,
    tx_pattern: ElementPattern | None = None,
    rx_pattern: ElementPattern | None = None,
    channel_patterns: ChannelPatternSet | None = None,
    dbf_dictionary: DbfDictionaryConfig | None = None,
) -> tuple[np.ndarray, np.ndarray]:
    """Return one conventional DBF elevation spectrum for a true source angle."""
    true_angles, scan_angles, spectra_db = dbf_elevation_spectrum_bank(
        array,
        true_angles_deg=np.asarray([true_angle_deg], dtype=float),
        scan_angles_deg=angles_deg,
        tx_pattern=tx_pattern,
        rx_pattern=rx_pattern,
        channel_patterns=channel_patterns,
        dbf_dictionary=dbf_dictionary,
    )
    _ = true_angles
    return scan_angles, spectra_db[0]


def dbf_azimuth_spectrum_bank(
    array: AntennaArray,
    true_angles_deg: np.ndarray | None = None,
    scan_angles_deg: np.ndarray | None = None,
    tx_pattern: ElementPattern | None = None,
    rx_pattern: ElementPattern | None = None,
    channel_patterns: ChannelPatternSet | None = None,
    dbf_dictionary: DbfDictionaryConfig | None = None,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Return DBF spectra for many true azimuth angles.

    The returned matrix has shape ``(len(true_angles), len(scan_angles))``.
    Each row is computed as ``A(scan).H @ a(true)``, where ``A`` is the
    beamforming dictionary and ``a(true)`` is the simulated channel phase vector.
    Coordinates are stored in lambda/2 units, so the azimuth phase is
    ``pi * x * sin(theta)``.
    """
    return _dbf_spectrum_bank(
        array,
        axis="azimuth",
        true_angles_deg=true_angles_deg,
        scan_angles_deg=scan_angles_deg,
        tx_pattern=tx_pattern,
        rx_pattern=rx_pattern,
        channel_patterns=channel_patterns,
        dbf_dictionary=dbf_dictionary,
    )


def dbf_elevation_spectrum_bank(
    array: AntennaArray,
    true_angles_deg: np.ndarray | None = None,
    scan_angles_deg: np.ndarray | None = None,
    tx_pattern: ElementPattern | None = None,
    rx_pattern: ElementPattern | None = None,
    channel_patterns: ChannelPatternSet | None = None,
    dbf_dictionary: DbfDictionaryConfig | None = None,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Return DBF spectra for many true elevation angles.

    The returned matrix has shape ``(len(true_angles), len(scan_angles))``.
    Each row is computed as ``A(scan).H @ a(true)`` with the elevation steering
    phase ``pi * y * sin(theta)``.
    """
    return _dbf_spectrum_bank(
        array,
        axis="elevation",
        true_angles_deg=true_angles_deg,
        scan_angles_deg=scan_angles_deg,
        tx_pattern=tx_pattern,
        rx_pattern=rx_pattern,
        channel_patterns=channel_patterns,
        dbf_dictionary=dbf_dictionary,
    )


def dbf_2d_spectrum(
    array: AntennaArray,
    true_azimuth_deg: float = 0.0,
    true_elevation_deg: float = 0.0,
    scan_azimuths_deg: np.ndarray | None = None,
    scan_elevations_deg: np.ndarray | None = None,
    tx_pattern: ElementPattern | None = None,
    rx_pattern: ElementPattern | None = None,
    channel_patterns: ChannelPatternSet | None = None,
    dbf_dictionary: DbfDictionaryConfig | None = None,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Return one conventional 2D DBF spectrum for a true az/el source angle."""
    if scan_azimuths_deg is None:
        scan_azimuths_deg = _default_dbf_angles()
    else:
        scan_azimuths_deg = np.asarray(scan_azimuths_deg, dtype=float)

    if scan_elevations_deg is None:
        scan_elevations_deg = _default_dbf_angles()
    else:
        scan_elevations_deg = np.asarray(scan_elevations_deg, dtype=float)

    signal = _dbf_2d_signal_vector(
        array,
        true_azimuth_deg,
        true_elevation_deg,
        channel_patterns=channel_patterns,
    )
    az_grid, el_grid = np.meshgrid(scan_azimuths_deg, scan_elevations_deg)
    if dbf_dictionary is not None and not dbf_dictionary.uses_auto_ideal_sign:
        dictionary = dbf_dictionary.scan_matrix_2d(
            array,
            az_grid.ravel(),
            el_grid.ravel(),
            axis="azimuth",
            channel_patterns=channel_patterns,
        )
    else:
        steering_sign = _select_dbf_2d_steering_sign(
            array,
            float(true_azimuth_deg),
            float(true_elevation_deg),
            scan_azimuths_deg,
            scan_elevations_deg,
            signal,
            channel_patterns=channel_patterns,
        )
        dictionary = _dbf_2d_scan_matrix(
            array,
            az_grid.ravel(),
            el_grid.ravel(),
            steering_sign=steering_sign,
        )
    response = dictionary @ signal
    response = response.reshape(len(scan_elevations_deg), len(scan_azimuths_deg))

    pattern_weight = _element_pattern_weight(tx_pattern, az_grid, el_grid)
    pattern_weight *= _element_pattern_weight(rx_pattern, az_grid, el_grid)
    spectra = np.abs(response * pattern_weight)
    maximum = float(np.max(spectra)) if spectra.size else 0.0
    if maximum > 0.0:
        spectra = spectra / maximum
    spectra_db = 20.0 * np.log10(np.maximum(spectra, 1e-6))
    return scan_azimuths_deg, scan_elevations_deg, spectra_db


def dbf_azimuth_angle_metrics(
    array: AntennaArray,
    tx_pattern: ElementPattern | None = None,
    rx_pattern: ElementPattern | None = None,
    channel_patterns: ChannelPatternSet | None = None,
    ambiguity_margin_db: float = DBF_AMBIGUITY_MARGIN_DB,
    dbf_dictionary: DbfDictionaryConfig | None = None,
) -> DbfAngleMetrics:
    true_angles, scan_angles, spectra_db = dbf_azimuth_spectrum_bank(
        array,
        tx_pattern=tx_pattern,
        rx_pattern=rx_pattern,
        channel_patterns=channel_patterns,
        dbf_dictionary=dbf_dictionary,
    )
    return dbf_angle_metrics_from_spectra(
        true_angles,
        scan_angles,
        spectra_db,
        ambiguity_margin_db=ambiguity_margin_db,
    )


def dbf_elevation_angle_metrics(
    array: AntennaArray,
    tx_pattern: ElementPattern | None = None,
    rx_pattern: ElementPattern | None = None,
    channel_patterns: ChannelPatternSet | None = None,
    ambiguity_margin_db: float = DBF_AMBIGUITY_MARGIN_DB,
    dbf_dictionary: DbfDictionaryConfig | None = None,
) -> DbfAngleMetrics:
    true_angles, scan_angles, spectra_db = dbf_elevation_spectrum_bank(
        array,
        tx_pattern=tx_pattern,
        rx_pattern=rx_pattern,
        channel_patterns=channel_patterns,
        dbf_dictionary=dbf_dictionary,
    )
    return dbf_angle_metrics_from_spectra(
        true_angles,
        scan_angles,
        spectra_db,
        ambiguity_margin_db=ambiguity_margin_db,
    )


def dbf_angle_metrics_from_spectra(
    true_angles_deg: np.ndarray,
    scan_angles_deg: np.ndarray,
    spectra_db: np.ndarray,
    focus_limit_deg: float = DBF_ANGLE_FOCUS_DEG,
    ambiguity_margin_db: float = DBF_AMBIGUITY_MARGIN_DB,
) -> DbfAngleMetrics:
    true_angles = np.asarray(true_angles_deg, dtype=float)
    scan_angles = np.asarray(scan_angles_deg, dtype=float)
    spectra = np.asarray(spectra_db, dtype=float)
    if true_angles.size == 0 or scan_angles.size == 0 or spectra.size == 0:
        return DbfAngleMetrics(None, None, None, None, None, None, None, None, None)

    estimates: list[float] = []
    peak_margins: list[float] = []
    quality_flags: list[str] = []
    for spectrum in spectra:
        estimate, margin, quality_flag = _dbf_peak_quality(scan_angles, spectrum)
        estimates.append(estimate)
        peak_margins.append(margin)
        quality_flags.append(quality_flag)

    estimate_array = np.asarray(estimates, dtype=float)
    error_array = estimate_array - true_angles
    margin_array = np.asarray(peak_margins, dtype=float)
    no_fold = _dbf_no_fold_interval(
        true_angles,
        error_array,
        margin_array,
        quality_flags,
        ambiguity_margin_db=ambiguity_margin_db,
    )

    focus_mask = np.abs(true_angles) <= focus_limit_deg
    focus_errors = np.abs(error_array[focus_mask])
    focus_max = float(np.max(focus_errors)) if focus_errors.size else None
    center_index = int(np.argmin(np.abs(true_angles)))
    center_error = float(error_array[center_index])
    center_margin = float(margin_array[center_index])

    if no_fold.no_fold_left is None or no_fold.no_fold_right is None:
        selected_margins = np.empty(0, dtype=float)
    else:
        selected = (
            (true_angles >= no_fold.no_fold_left)
            & (true_angles <= no_fold.no_fold_right)
        )
        selected_margins = margin_array[selected]
    min_margin = _finite_or_infinite_min(selected_margins)

    return DbfAngleMetrics(
        no_fold_left=no_fold.no_fold_left,
        no_fold_right=no_fold.no_fold_right,
        no_fold_max_abs_error=no_fold.no_fold_max_abs_error,
        focus_max_abs_error=focus_max,
        center_error=center_error,
        min_peak_margin_db=min_margin,
        center_peak_margin_db=center_margin,
        negative_cut_reason=no_fold.negative_cut_reason,
        positive_cut_reason=no_fold.positive_cut_reason,
    )


def _dbf_peak_quality(
    scan_angles_deg: np.ndarray,
    spectrum_db: np.ndarray,
) -> tuple[float, float, str]:
    values = np.asarray(spectrum_db, dtype=float)
    main_index = int(np.argmax(values))
    main_peak = float(values[main_index])
    left_bound, right_bound = _dbf_main_lobe_bounds(values, main_index)
    local_peaks = _dbf_local_peak_indices(values)
    competitor_indices = [
        index for index in local_peaks if index < left_bound or index > right_bound
    ]
    if competitor_indices:
        competitor_index = max(competitor_indices, key=lambda index: float(values[index]))
        competitor_peak = float(values[competitor_index])
    else:
        competitor_peak = float("-inf")
    peak_margin = main_peak - competitor_peak
    quality_flag = _dbf_quality_flag(scan_angles_deg, values, main_index)
    return float(scan_angles_deg[main_index]), peak_margin, quality_flag


def _dbf_no_fold_interval(
    true_angles_deg: np.ndarray,
    error_deg: np.ndarray,
    peak_margin_db: np.ndarray,
    quality_flags: list[str],
    ambiguity_margin_db: float = DBF_AMBIGUITY_MARGIN_DB,
) -> _DbfNoFoldResult:
    theta_array = np.asarray(true_angles_deg, dtype=float)
    error_array = np.asarray(error_deg, dtype=float)
    if theta_array.size == 0 or error_array.size == 0:
        return _DbfNoFoldResult(None, None, None, None, None)

    order = np.argsort(theta_array)
    theta_array = theta_array[order]
    error_array = error_array[order]
    margin_array = np.asarray(peak_margin_db, dtype=float)[order]
    ordered_quality = np.asarray(quality_flags, dtype=object)[order]

    resolvable = margin_array > ambiguity_margin_db
    resolvable &= np.isfinite(margin_array) | np.isposinf(margin_array)
    quality_reasons: list[str | None] = [
        None if bool(ok) else DBF_CUT_REASON_COMPETITOR for ok in resolvable
    ]
    for index, flag in enumerate(ordered_quality):
        reason = _dbf_quality_cut_reason(str(flag))
        if reason:
            resolvable[index] = False
            quality_reasons[index] = reason

    center = int(np.argmin(np.abs(theta_array)))
    if not bool(resolvable[center]):
        reason = quality_reasons[center] or DBF_CUT_REASON_COMPETITOR
        return _DbfNoFoldResult(0.0, 0.0, 0.0, reason, reason)

    left = right = center
    negative_reason: str | None = None
    positive_reason: str | None = None
    while left > 0:
        if not bool(resolvable[left - 1]):
            negative_reason = quality_reasons[left - 1] or DBF_CUT_REASON_COMPETITOR
            break
        if (
            abs(float(error_array[left]) - float(error_array[left - 1]))
            > DBF_ERROR_JUMP_LIMIT_DEG
        ):
            negative_reason = DBF_CUT_REASON_ERROR_JUMP
            break
        left -= 1
    while right < len(theta_array) - 1:
        if not bool(resolvable[right + 1]):
            positive_reason = quality_reasons[right + 1] or DBF_CUT_REASON_COMPETITOR
            break
        if (
            abs(float(error_array[right + 1]) - float(error_array[right]))
            > DBF_ERROR_JUMP_LIMIT_DEG
        ):
            positive_reason = DBF_CUT_REASON_ERROR_JUMP
            break
        right += 1

    if negative_reason is None and left == 0:
        negative_reason = DBF_CUT_REASON_BOUNDARY
    if positive_reason is None and right == len(theta_array) - 1:
        positive_reason = DBF_CUT_REASON_BOUNDARY

    selected_errors = error_array[left : right + 1]
    max_abs = float(np.max(np.abs(selected_errors))) if selected_errors.size else None
    return _DbfNoFoldResult(
        float(theta_array[left]),
        float(theta_array[right]),
        max_abs,
        negative_reason,
        positive_reason,
    )


def _dbf_main_lobe_bounds(values_db: np.ndarray, main_index: int) -> tuple[int, int]:
    left = main_index
    while left > 0:
        current = float(values_db[left])
        prev_value = float(values_db[left - 1])
        next_value = float(values_db[left + 1]) if left + 1 < len(values_db) else current
        if (
            left < main_index
            and current <= prev_value
            and current <= next_value
            and (current < prev_value or current < next_value)
        ):
            break
        left -= 1

    right = main_index
    while right < len(values_db) - 1:
        current = float(values_db[right])
        prev_value = float(values_db[right - 1]) if right > 0 else current
        next_value = float(values_db[right + 1])
        if (
            right > main_index
            and current <= prev_value
            and current <= next_value
            and (current < prev_value or current < next_value)
        ):
            break
        right += 1
    return left, right


def _dbf_local_peak_indices(values_db: np.ndarray) -> list[int]:
    if len(values_db) == 0:
        return []
    peaks: list[int] = []
    index = 0
    while index < len(values_db):
        start = index
        while (
            index + 1 < len(values_db)
            and abs(float(values_db[index + 1]) - float(values_db[start])) <= 1e-9
        ):
            index += 1
        end = index
        value = float(values_db[start])
        left = float(values_db[start - 1]) if start > 0 else float("-inf")
        right = float(values_db[end + 1]) if end + 1 < len(values_db) else float("-inf")
        if value >= left and value >= right and (value > left or value > right):
            peaks.append((start + end) // 2)
        index += 1
    return peaks


def _dbf_quality_flag(
    scan_angles_deg: np.ndarray,
    values_db: np.ndarray,
    main_index: int,
) -> str:
    if main_index == 0 or main_index == len(scan_angles_deg) - 1:
        return DBF_CUT_REASON_EDGE
    main_peak = float(values_db[main_index])
    left = main_index
    while (
        left > 0
        and main_peak - float(values_db[left - 1]) <= DBF_FLAT_TOP_TOLERANCE_DB
    ):
        left -= 1
    right = main_index
    while (
        right < len(scan_angles_deg) - 1
        and main_peak - float(values_db[right + 1]) <= DBF_FLAT_TOP_TOLERANCE_DB
    ):
        right += 1
    if float(scan_angles_deg[right]) - float(scan_angles_deg[left]) >= DBF_FLAT_TOP_WIDTH_DEG:
        return DBF_CUT_REASON_FLAT
    return DBF_QUALITY_OK


def _dbf_quality_cut_reason(flag: str) -> str | None:
    normalized = flag.strip().lower()
    if normalized in {"", DBF_QUALITY_OK.lower(), "ok", "normal", "0", "nan", "none"}:
        return None
    if normalized in {DBF_CUT_REASON_EDGE.lower(), "edge_limited", "boundary_limited"}:
        return DBF_CUT_REASON_EDGE
    if normalized in {DBF_CUT_REASON_FLAT.lower(), "flat_spectrum", "flat"}:
        return DBF_CUT_REASON_FLAT
    try:
        code = float(normalized)
    except ValueError:
        return None
    if np.isclose(code, 1.0):
        return DBF_CUT_REASON_EDGE
    if np.isclose(code, 2.0):
        return DBF_CUT_REASON_FLAT
    return None


def _finite_or_infinite_min(values: np.ndarray) -> float | None:
    if values.size == 0:
        return None
    finite = values[np.isfinite(values)]
    if finite.size:
        return float(np.min(finite))
    if np.any(np.isposinf(values)):
        return float("inf")
    return None


def _dbf_spectrum_bank(
    array: AntennaArray,
    axis: str,
    true_angles_deg: np.ndarray | None = None,
    scan_angles_deg: np.ndarray | None = None,
    tx_pattern: ElementPattern | None = None,
    rx_pattern: ElementPattern | None = None,
    channel_patterns: ChannelPatternSet | None = None,
    dbf_dictionary: DbfDictionaryConfig | None = None,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    if true_angles_deg is None:
        true_angles_deg = _default_dbf_angles()
    else:
        true_angles_deg = np.asarray(true_angles_deg, dtype=float)

    if scan_angles_deg is None:
        scan_angles_deg = _default_dbf_angles()
    else:
        scan_angles_deg = np.asarray(scan_angles_deg, dtype=float)

    signal_phase = _dbf_signal_matrix(
        array,
        true_angles_deg,
        axis=axis,
        channel_patterns=channel_patterns,
    )
    if dbf_dictionary is not None and not dbf_dictionary.uses_auto_ideal_sign:
        dictionary = dbf_dictionary.scan_matrix(
            array,
            scan_angles_deg,
            axis=axis,
            channel_patterns=channel_patterns,
        )
    else:
        steering_sign = _select_dbf_steering_sign(
            array,
            true_angles_deg,
            scan_angles_deg,
            signal_phase,
            axis=axis,
            channel_patterns=channel_patterns,
        )
        dictionary = _dbf_scan_matrix(
            array,
            scan_angles_deg,
            axis=axis,
            steering_sign=steering_sign,
        )
    response = dictionary @ signal_phase

    zeros = np.zeros_like(scan_angles_deg, dtype=float)
    if axis == "azimuth":
        pattern_azimuths = scan_angles_deg
        pattern_elevations = zeros
    elif axis == "elevation":
        pattern_azimuths = zeros
        pattern_elevations = scan_angles_deg
    else:
        raise ValueError(f"Unknown DBF axis: {axis!r}")

    pattern_weight = _element_pattern_weight(
        tx_pattern, pattern_azimuths, pattern_elevations
    )
    pattern_weight *= _element_pattern_weight(
        rx_pattern, pattern_azimuths, pattern_elevations
    )
    pattern_weight = np.asarray(pattern_weight, dtype=float)
    if pattern_weight.ndim == 0:
        pattern_weight = np.full_like(scan_angles_deg, float(pattern_weight))

    spectra = np.abs(response.T * pattern_weight[None, :])
    maxima = np.max(spectra, axis=1, keepdims=True)
    spectra = np.divide(spectra, maxima, out=np.zeros_like(spectra), where=maxima > 0)
    spectra_db = 20.0 * np.log10(np.maximum(spectra, 1e-6))
    return true_angles_deg, scan_angles_deg, spectra_db


def _default_dbf_angles() -> np.ndarray:
    return np.arange(
        DBF_SCAN_FOV[0],
        DBF_SCAN_FOV[1] + DBF_SCAN_STEP_DEG / 2.0,
        DBF_SCAN_STEP_DEG,
        dtype=float,
    )


def _steering_matrix(
    array: AntennaArray,
    angles_deg: np.ndarray,
    axis: str,
) -> np.ndarray:
    virtual_xy = array.virtual_xy()
    if axis == "azimuth":
        positions = virtual_xy[:, 0]
    elif axis == "elevation":
        positions = virtual_xy[:, 1]
    else:
        raise ValueError(f"Unknown DBF axis: {axis!r}")
    u = np.sin(np.radians(angles_deg))
    phase = np.pi * positions[:, None] * u[None, :]
    return np.exp(1j * phase)


def _dbf_scan_matrix(
    array: AntennaArray,
    angles_deg: np.ndarray,
    axis: str,
    steering_sign: int = DBF_DEFAULT_STEERING_SIGN,
) -> np.ndarray:
    virtual_xy = array.virtual_xy()
    if axis == "azimuth":
        positions = virtual_xy[:, 0]
    elif axis == "elevation":
        positions = virtual_xy[:, 1]
    else:
        raise ValueError(f"Unknown DBF axis: {axis!r}")
    u = np.sin(np.radians(angles_deg))
    phase = steering_sign * np.pi * u[:, None] * positions[None, :]
    return np.exp(1j * phase)


def _direction_uv(
    azimuth_deg: np.ndarray,
    elevation_deg: np.ndarray,
) -> tuple[np.ndarray, np.ndarray]:
    azimuth_rad = np.radians(azimuth_deg)
    elevation_rad = np.radians(elevation_deg)
    u = np.sin(azimuth_rad) * np.cos(elevation_rad)
    v = np.sin(elevation_rad)
    return u, v


def _dbf_2d_scan_matrix(
    array: AntennaArray,
    azimuth_deg: np.ndarray,
    elevation_deg: np.ndarray,
    steering_sign: int = DBF_DEFAULT_STEERING_SIGN,
) -> np.ndarray:
    virtual_xy = array.virtual_xy()
    u, v = _direction_uv(
        np.asarray(azimuth_deg, dtype=float),
        np.asarray(elevation_deg, dtype=float),
    )
    phase = steering_sign * np.pi * (
        u[:, None] * virtual_xy[None, :, 0]
        + v[:, None] * virtual_xy[None, :, 1]
    )
    return np.exp(1j * phase)


def _dbf_2d_steering_vector(
    array: AntennaArray,
    azimuth_deg: float,
    elevation_deg: float,
) -> np.ndarray:
    virtual_xy = array.virtual_xy()
    u, v = _direction_uv(
        np.asarray([azimuth_deg], dtype=float),
        np.asarray([elevation_deg], dtype=float),
    )
    phase = np.pi * (virtual_xy[:, 0] * float(u[0]) + virtual_xy[:, 1] * float(v[0]))
    return np.exp(1j * phase)


def _axis_pattern_angles(
    axis: str,
    angles_deg: np.ndarray,
) -> tuple[np.ndarray, np.ndarray]:
    zeros = np.zeros_like(angles_deg, dtype=float)
    if axis == "azimuth":
        return angles_deg, zeros
    if axis == "elevation":
        return zeros, angles_deg
    raise ValueError(f"Unknown DBF axis: {axis!r}")


def _dbf_signal_matrix(
    array: AntennaArray,
    true_angles_deg: np.ndarray,
    axis: str,
    channel_patterns: ChannelPatternSet | None,
) -> np.ndarray:
    true_azimuths, true_elevations = _axis_pattern_angles(axis, true_angles_deg)
    channel_weight = _channel_pattern_weight(
        channel_patterns, array, true_azimuths, true_elevations
    )
    if _channel_pattern_has_phase(channel_patterns, array, axis):
        return np.asarray(channel_weight, dtype=complex)
    return _steering_matrix(array, true_angles_deg, axis=axis) * channel_weight


def _dbf_2d_signal_vector(
    array: AntennaArray,
    true_azimuth_deg: float,
    true_elevation_deg: float,
    channel_patterns: ChannelPatternSet | None,
) -> np.ndarray:
    azimuths = np.asarray([true_azimuth_deg], dtype=float)
    elevations = np.asarray([true_elevation_deg], dtype=float)
    channel_weight = _channel_pattern_weight(
        channel_patterns, array, azimuths, elevations
    )
    virtual_count = len(array.tx) * len(array.rx)
    if np.isscalar(channel_weight):
        channel_weight = np.ones(virtual_count, dtype=complex) * complex(channel_weight)
    else:
        channel_weight = np.asarray(channel_weight, dtype=complex).reshape(virtual_count)
    if _channel_pattern_has_any_phase(channel_patterns, array):
        return np.asarray(channel_weight, dtype=complex)
    return _dbf_2d_steering_vector(
        array, true_azimuth_deg, true_elevation_deg
    ) * channel_weight


def _select_dbf_steering_sign(
    array: AntennaArray,
    true_angles_deg: np.ndarray,
    scan_angles_deg: np.ndarray,
    signal_phase: np.ndarray,
    axis: str,
    channel_patterns: ChannelPatternSet | None,
) -> int:
    if not _channel_pattern_has_phase(channel_patterns, array, axis):
        return DBF_DEFAULT_STEERING_SIGN

    selected = np.abs(true_angles_deg) <= DBF_SIGN_SELECTION_LIMIT_DEG
    if not np.any(selected):
        selected = np.ones_like(true_angles_deg, dtype=bool)

    candidates: list[tuple[float, int]] = []
    for steering_sign in (DBF_DEFAULT_STEERING_SIGN, 1):
        dictionary = _dbf_scan_matrix(
            array,
            scan_angles_deg,
            axis=axis,
            steering_sign=steering_sign,
        )
        score = np.abs(dictionary @ signal_phase) ** 2
        estimates = scan_angles_deg[np.argmax(score, axis=0)]
        error = estimates[selected] - true_angles_deg[selected]
        rms = float(np.sqrt(np.mean(error**2))) if len(error) else float("inf")
        candidates.append((rms, steering_sign))
    return min(candidates, key=lambda item: (item[0], 0 if item[1] == DBF_DEFAULT_STEERING_SIGN else 1))[1]


def _select_dbf_2d_steering_sign(
    array: AntennaArray,
    true_azimuth_deg: float,
    true_elevation_deg: float,
    scan_azimuths_deg: np.ndarray,
    scan_elevations_deg: np.ndarray,
    signal: np.ndarray,
    channel_patterns: ChannelPatternSet | None,
) -> int:
    if not _channel_pattern_has_any_phase(channel_patterns, array):
        return DBF_DEFAULT_STEERING_SIGN

    az_grid, el_grid = np.meshgrid(scan_azimuths_deg, scan_elevations_deg)
    candidates: list[tuple[float, int]] = []
    for steering_sign in (DBF_DEFAULT_STEERING_SIGN, 1):
        dictionary = _dbf_2d_scan_matrix(
            array,
            az_grid.ravel(),
            el_grid.ravel(),
            steering_sign=steering_sign,
        )
        score = np.abs(dictionary @ signal) ** 2
        peak = int(np.argmax(score))
        estimate_az = float(az_grid.ravel()[peak])
        estimate_el = float(el_grid.ravel()[peak])
        error = math.hypot(
            estimate_az - true_azimuth_deg,
            estimate_el - true_elevation_deg,
        )
        candidates.append((error, steering_sign))
    return min(candidates, key=lambda item: (item[0], 0 if item[1] == DBF_DEFAULT_STEERING_SIGN else 1))[1]


def _channel_pattern_weight(
    patterns: ChannelPatternSet | None,
    array: AntennaArray,
    azimuth_deg: np.ndarray,
    elevation_deg: np.ndarray,
) -> np.ndarray | float:
    if patterns is None or patterns.is_empty():
        return 1.0
    tx_names = [point.name for point in array.tx]
    rx_names = [point.name for point in array.rx]
    tx_weights = patterns.complex_weights(tx_names, azimuth_deg, elevation_deg)
    rx_weights = patterns.complex_weights(rx_names, azimuth_deg, elevation_deg)
    virtual_weights = tx_weights[:, None, ...] * rx_weights[None, :, ...]
    return virtual_weights.reshape(len(tx_names) * len(rx_names), *tx_weights.shape[1:])


def _channel_pattern_has_phase(
    patterns: ChannelPatternSet | None,
    array: AntennaArray,
    axis: str,
) -> bool:
    if patterns is None or patterns.is_empty():
        return False
    channel_names = [point.name for point in array.tx] + [point.name for point in array.rx]
    for channel_name in channel_names:
        pattern = patterns.pattern_for(channel_name)
        if axis == "azimuth" and pattern.phase_horizontal is not None:
            return True
        if axis == "elevation" and pattern.phase_elevation is not None:
            return True
    return False


def _channel_pattern_has_any_phase(
    patterns: ChannelPatternSet | None,
    array: AntennaArray,
) -> bool:
    if patterns is None or patterns.is_empty():
        return False
    channel_names = [point.name for point in array.tx] + [point.name for point in array.rx]
    for channel_name in channel_names:
        pattern = patterns.pattern_for(channel_name)
        if pattern.phase_horizontal is not None or pattern.phase_elevation is not None:
            return True
    return False


def _element_pattern_weight(
    pattern: ElementPattern | None,
    azimuth_deg: np.ndarray,
    elevation_deg: np.ndarray,
) -> np.ndarray | float:
    if pattern is None:
        return 1.0
    return pattern.amplitude_grid(azimuth_deg, elevation_deg)


def estimate_resolution(aperture_half_lambda: float) -> float | None:
    if aperture_half_lambda <= 0:
        return None
    aperture_lambda = aperture_half_lambda / 2.0
    if aperture_lambda <= 0:
        return None
    return float(np.degrees(0.886 / aperture_lambda))


def cut_3db_beamwidth(angles: np.ndarray, cut_db: np.ndarray) -> float | None:
    peak_index = int(np.argmin(np.abs(angles)))
    peak_db = float(cut_db[peak_index])
    left_3db = threshold_crossing_angle(angles, cut_db, peak_index, peak_db - 3.0, -1)
    right_3db = threshold_crossing_angle(angles, cut_db, peak_index, peak_db - 3.0, 1)
    return right_3db - left_3db if left_3db is not None and right_3db is not None else None


def azimuth_cut_metrics(
    azimuths: np.ndarray,
    azimuth_cut_db: np.ndarray,
) -> tuple[float | None, float | None, float | None]:
    peak_index = int(np.argmin(np.abs(azimuths)))

    beamwidth_3db = cut_3db_beamwidth(azimuths, azimuth_cut_db)

    left_null_index = first_null_index(azimuth_cut_db, peak_index, -1)
    right_null_index = first_null_index(azimuth_cut_db, peak_index, 1)
    null_beamwidth = None
    if left_null_index is not None and right_null_index is not None:
        null_beamwidth = float(azimuths[right_null_index] - azimuths[left_null_index])
        main_mask = np.zeros_like(azimuth_cut_db, dtype=bool)
        main_mask[left_null_index : right_null_index + 1] = True
    else:
        main_mask = np.abs(azimuths - float(azimuths[peak_index])) <= MAINLOBE_GUARD_AZ

    power = np.power(10.0, azimuth_cut_db / 10.0)
    main_power = float(np.sum(power[main_mask]))
    sidelobe_power = float(np.sum(power[~main_mask]))
    islr_db = (
        float(10.0 * np.log10(sidelobe_power / main_power))
        if main_power > 0 and sidelobe_power > 0
        else None
    )
    return beamwidth_3db, null_beamwidth, islr_db


def azimuth_first_sidelobe(
    azimuths: np.ndarray,
    azimuth_cut_db: np.ndarray,
) -> tuple[float | None, float | None]:
    peak_angle = 0.0
    peak_indices = local_peak_indices(azimuth_cut_db)
    left_index = nearest_sidelobe_peak(
        azimuths, azimuth_cut_db, peak_indices,
        azimuths < -MAINLOBE_GUARD_AZ, peak_angle,
    )
    right_index = nearest_sidelobe_peak(
        azimuths, azimuth_cut_db, peak_indices,
        azimuths > MAINLOBE_GUARD_AZ, peak_angle,
    )
    candidates = [index for index in (left_index, right_index) if index is not None]
    if not candidates:
        return None, None
    best_index = max(candidates, key=lambda index: azimuth_cut_db[index])
    return float(azimuth_cut_db[best_index]), float(azimuths[best_index])


def azimuth_grating_lobe(
    azimuths: np.ndarray,
    azimuth_cut_db: np.ndarray,
    min_abs_angle: float = 20.0,
) -> tuple[float | None, float | None]:
    far_indices = np.flatnonzero(np.abs(azimuths) > min_abs_angle)
    if len(far_indices) == 0:
        return None, None
    peak_indices = local_peak_indices(azimuth_cut_db)
    far_peak_indices = peak_indices[np.abs(azimuths[peak_indices]) > min_abs_angle]
    candidates = far_peak_indices if len(far_peak_indices) else far_indices
    best_index = int(candidates[np.argmax(azimuth_cut_db[candidates])])
    return float(azimuth_cut_db[best_index]), float(azimuths[best_index])


def psl_grade(psl_db: float) -> str:
    if psl_db < -15.0:
        return "Good"
    if psl_db < -10.0:
        return "Acceptable"
    if psl_db < -6.0:
        return "Risky"
    return "Bad"


def evaluate_front_radar(
    azimuth_resolution: float | None,
    azimuth_psl_db: float,
    unique_ratio: float,
    psl_2d_db: float,
) -> tuple[str, tuple[str, ...]]:
    warnings = []
    az_res = azimuth_resolution if azimuth_resolution is not None else float("inf")

    if psl_2d_db >= -6.0:
        warnings.append("High elevation ambiguity")
    if azimuth_psl_db >= -10.0:
        warnings.append("Windowing recommended")
    if unique_ratio < 0.85:
        warnings.append("Low virtual utilization")

    if az_res <= 1.5 and azimuth_psl_db < -10.0 and unique_ratio >= 0.95:
        status = "Good"
    elif az_res <= 2.5 and azimuth_psl_db < -6.0 and unique_ratio >= 0.85:
        status = "Acceptable"
    elif az_res <= 3.5 and azimuth_psl_db < -6.0:
        status = "Risky"
    else:
        status = "Bad"

    return status, tuple(warnings)


def ambiguity_level(psl_2d_db: float) -> str:
    if psl_2d_db >= -6.0:
        return "High"
    if psl_2d_db >= -10.0:
        return "Medium"
    return "Low"


def threshold_crossing_angle(
    angles: np.ndarray,
    values_db: np.ndarray,
    peak_index: int,
    threshold_db: float,
    direction: int,
) -> float | None:
    index = peak_index + direction
    while 0 <= index < len(values_db):
        if values_db[index] <= threshold_db:
            prev_index = index - direction
            x0 = float(angles[prev_index])
            x1 = float(angles[index])
            y0 = float(values_db[prev_index])
            y1 = float(values_db[index])
            if y1 == y0:
                return x1
            fraction = (threshold_db - y0) / (y1 - y0)
            return x0 + fraction * (x1 - x0)
        index += direction
    return None


def first_null_index(values_db: np.ndarray, peak_index: int, direction: int) -> int | None:
    index = peak_index + direction
    while 0 < index < len(values_db) - 1:
        if values_db[index] <= values_db[index - 1] and values_db[index] <= values_db[index + 1]:
            return index
        index += direction
    return None


def local_peak_indices(values_db: np.ndarray) -> np.ndarray:
    if len(values_db) < 3:
        return np.empty(0, dtype=int)
    return np.flatnonzero(
        (values_db[1:-1] >= values_db[:-2]) & (values_db[1:-1] >= values_db[2:])
    ) + 1


def nearest_sidelobe_peak(
    angles: np.ndarray,
    values_db: np.ndarray,
    peak_indices: np.ndarray,
    side_mask: np.ndarray,
    peak_angle: float,
) -> int | None:
    candidates = peak_indices[side_mask[peak_indices]]
    if len(candidates):
        return int(candidates[np.argmin(np.abs(angles[candidates] - peak_angle))])
    fallback = np.flatnonzero(side_mask)
    if len(fallback):
        return int(fallback[np.argmax(values_db[fallback])])
    return None
