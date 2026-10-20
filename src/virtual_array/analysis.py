from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

from .dbf_dictionary import DbfDictionaryConfig
from .element_pattern import ChannelPatternSet, ElementPattern, virtual_channel_names
from .geometry import AntennaArray
from .phasor import unit_phasor

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
MAINLOBE_MIN_DROP_DB = 3.0
GRATING_MIN_ABS_ANGLE_DEG = 20.0
DBF_SEARCH_GUARD_DEG = 10.0
DBF_REFINE_STAGES = ((1.0, 0.05), (0.05, 0.002))
DBF_CORRELATION_EPS = 1e-12


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
class DbfAngleFrameSeries:
    true_angles_deg: np.ndarray
    estimated_angles_deg: np.ndarray
    errors_deg: np.ndarray
    main_peak_db: np.ndarray
    competitor_peak_db: np.ndarray
    peak_margins_db: np.ndarray
    quality_flags: tuple[str, ...]


@dataclass(frozen=True)
class _DbfNoFoldResult:
    no_fold_left: float | None
    no_fold_right: float | None
    no_fold_max_abs_error: float | None
    negative_cut_reason: str | None
    positive_cut_reason: str | None


def dbf_peak_index(
    scan_angles_deg: np.ndarray,
    spectrum_db: np.ndarray,
    true_angle_deg: float | None = None,
    tolerance_db: float = 1e-6,
) -> int:
    """Return the strongest DBF bin using a deterministic tie policy.

    Without a true angle this is strict ``argmax`` behavior, which avoids using
    ground truth to improve performance estimates.  A caller that is only
    choosing a display marker may provide ``true_angle_deg``; in that case all
    bins within ``tolerance_db`` of the strongest value are treated as tied and
    the nearest one is returned.
    """
    scan_angles = np.asarray(scan_angles_deg, dtype=float)
    spectrum = np.asarray(spectrum_db, dtype=float)
    if scan_angles.ndim != 1:
        raise ValueError("scan_angles_deg must be one-dimensional.")
    if spectrum.ndim != 1:
        raise ValueError("spectrum_db must be one-dimensional.")
    if scan_angles.size == 0:
        raise ValueError("scan_angles_deg must not be empty.")
    if spectrum.shape != scan_angles.shape:
        raise ValueError("spectrum_db length must match scan_angles_deg.")
    if not np.all(np.isfinite(scan_angles)):
        raise ValueError("scan_angles_deg must contain only finite values.")
    if scan_angles.size > 1 and not np.all(np.diff(scan_angles) > 0.0):
        raise ValueError("scan_angles_deg must be strictly increasing.")
    if not np.all(np.isfinite(spectrum)):
        raise ValueError("spectrum_db must contain only finite values.")
    tolerance = float(tolerance_db)
    if not np.isfinite(tolerance) or tolerance < 0.0:
        raise ValueError("tolerance_db must be finite and non-negative.")

    if true_angle_deg is None:
        return int(np.argmax(spectrum))
    true_angle = float(true_angle_deg)
    if not np.isfinite(true_angle):
        raise ValueError("true_angle_deg must be finite.")
    peak_gain = float(np.max(spectrum))
    candidate_indices = np.flatnonzero(spectrum >= peak_gain - tolerance)
    return int(
        candidate_indices[
            int(np.argmin(np.abs(scan_angles[candidate_indices] - true_angle)))
        ]
    )


def dbf_angle_frame_series_from_spectra(
    true_angles_deg: np.ndarray,
    scan_angles_deg: np.ndarray,
    spectra_db: np.ndarray,
    estimated_angles_deg: np.ndarray | None = None,
) -> DbfAngleFrameSeries:
    """Extract per-frame DBF estimates, errors, peak margins, and quality flags.

    ``estimated_angles_deg`` optionally replaces the scan-grid peak angles with
    refined estimates (see :func:`dbf_refine_peak_angles`); peak margins and
    quality flags are still taken from the scan-grid spectra.
    """
    true_angles = np.asarray(true_angles_deg, dtype=float)
    scan_angles = np.asarray(scan_angles_deg, dtype=float)
    spectra = np.asarray(spectra_db, dtype=float)
    if true_angles.ndim != 1:
        raise ValueError("true_angles_deg must be one-dimensional.")
    if scan_angles.ndim != 1:
        raise ValueError("scan_angles_deg must be one-dimensional.")
    if spectra.ndim != 2:
        raise ValueError("spectra_db must be two-dimensional.")
    if true_angles.size == 0:
        raise ValueError("true_angles_deg must not be empty.")
    if scan_angles.size == 0:
        raise ValueError("scan_angles_deg must not be empty.")
    expected_shape = (len(true_angles), len(scan_angles))
    if spectra.shape != expected_shape:
        raise ValueError(
            "spectra_db shape must be "
            f"{expected_shape}, got {spectra.shape}."
        )
    if not np.all(np.isfinite(true_angles)):
        raise ValueError("true_angles_deg must contain only finite values.")
    if not np.all(np.isfinite(scan_angles)):
        raise ValueError("scan_angles_deg must contain only finite values.")
    if scan_angles.size > 1 and not np.all(np.diff(scan_angles) > 0.0):
        raise ValueError("scan_angles_deg must be strictly increasing.")
    if not np.all(np.isfinite(spectra)):
        raise ValueError("spectra_db must contain only finite values.")

    estimates: list[float] = []
    main_peaks: list[float] = []
    competitor_peaks: list[float] = []
    peak_margins: list[float] = []
    quality_flags: list[str] = []
    for spectrum in spectra:
        estimate, main_peak, competitor_peak, margin, quality_flag = (
            _dbf_peak_details(scan_angles, spectrum)
        )
        estimates.append(estimate)
        main_peaks.append(main_peak)
        competitor_peaks.append(competitor_peak)
        peak_margins.append(margin)
        quality_flags.append(quality_flag)

    estimate_array = np.asarray(estimates, dtype=float)
    if estimated_angles_deg is not None:
        refined = np.asarray(estimated_angles_deg, dtype=float)
        if refined.shape != estimate_array.shape:
            raise ValueError("estimated_angles_deg must have one value per true angle.")
        estimate_array = refined.copy()
    return DbfAngleFrameSeries(
        true_angles_deg=true_angles.copy(),
        estimated_angles_deg=estimate_array,
        errors_deg=estimate_array - true_angles,
        main_peak_db=np.asarray(main_peaks, dtype=float),
        competitor_peak_db=np.asarray(competitor_peaks, dtype=float),
        peak_margins_db=np.asarray(peak_margins, dtype=float),
        quality_flags=tuple(quality_flags),
    )


def calculate_metrics_and_psf(
    array: AntennaArray,
    unique: np.ndarray | None = None,
    counts: np.ndarray | None = None,
    decimals: int = 9,
    tx_pattern: ElementPattern | None = None,
    rx_pattern: ElementPattern | None = None,
    channel_patterns: ChannelPatternSet | None = None,
    azimuth_fov: tuple[float, float] = AZIMUTH_FOV,
    elevation_fov: tuple[float, float] = ELEVATION_FOV,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, ArrayMetrics]:
    if unique is None or counts is None:
        unique, counts = array.unique_virtual_xy(decimals=decimals)

    virtual_xy = array.virtual_xy()
    x_aperture = float(np.ptp(unique[:, 0])) if len(unique) else 0.0
    y_aperture = float(np.ptp(unique[:, 1])) if len(unique) else 0.0
    aperture_ratio = x_aperture / y_aperture if y_aperture > 0 else None
    azimuth_resolution = estimate_resolution(x_aperture)
    elevation_resolution = estimate_resolution(y_aperture)

    azimuths = np.linspace(azimuth_fov[0], azimuth_fov[1], AF_GRID_SIZE)
    elevations = np.linspace(elevation_fov[0], elevation_fov[1], AF_GRID_SIZE)
    az_grid, el_grid = np.meshgrid(azimuths, elevations)
    az_rad = np.radians(az_grid)
    el_rad = np.radians(el_grid)
    u = np.sin(az_rad) * np.cos(el_rad)
    v = np.sin(el_rad)

    if _channel_pattern_has_any_phase(channel_patterns, array):
        # Imported phase cuts already carry the geometric phase progression of
        # their plane; multiplying the steering in again would count it twice.
        # Use the same channel response as the DBF signal model.
        phase_sign = _imported_phase_sign(
            array, channel_patterns, azimuths, elevations
        )
        flat_factor = _channel_response(
            array, az_grid.ravel(), el_grid.ravel(), channel_patterns, phase_sign
        ).sum(axis=0)
    else:
        # A (channels x grid) matrix product avoids the large broadcast
        # temporaries of the per-axis formulation; it is ~4x faster for 64+
        # virtual channels.
        uv = np.stack([u.ravel(), v.ravel()])
        steering = unit_phasor((np.pi * virtual_xy) @ uv)
        channel_weight = _channel_pattern_weight(
            channel_patterns, array, az_grid, el_grid
        )
        if np.ndim(channel_weight) == 0:
            flat_factor = complex(channel_weight) * (
                np.ones(len(virtual_xy), dtype=complex) @ steering
            )
        else:
            flat_weight = np.asarray(channel_weight, dtype=complex).reshape(
                len(virtual_xy), -1
            )
            flat_factor = np.einsum("ng,ng->g", steering, flat_weight)
    array_factor = flat_factor.reshape(az_grid.shape)
    pattern_weight = _element_pattern_weight(tx_pattern, az_grid, el_grid)
    pattern_weight *= _element_pattern_weight(rx_pattern, az_grid, el_grid)
    af = np.abs(array_factor * pattern_weight)
    af /= af.max() if af.max() else 1.0
    af_db = 20.0 * np.log10(np.maximum(af, 1e-6))

    main_index = np.unravel_index(np.argmax(af_db), af_db.shape)
    main_azimuth = float(az_grid[main_index])
    main_elevation = float(el_grid[main_index])
    # The main lobe extends to the first null on each principal cut through the
    # peak (at least 3 dB down).  A fixed angular guard misclassifies the main
    # lobe of small arrays (wide beams) as a sidelobe; an axis without aperture
    # has no sidelobes at all.
    az_bounds = (
        _mainlobe_bounds(azimuths, af_db[main_index[0], :], int(main_index[1]))
        if x_aperture > 0
        else (float(azimuths[0]), float(azimuths[-1]))
    )
    el_bounds = (
        _mainlobe_bounds(elevations, af_db[:, main_index[1]], int(main_index[0]))
        if y_aperture > 0
        else (float(elevations[0]), float(elevations[-1]))
    )
    main_lobe_mask = (
        (az_grid >= az_bounds[0])
        & (az_grid <= az_bounds[1])
        & (el_grid >= el_bounds[0])
        & (el_grid <= el_bounds[1])
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

    az_cut_bounds = (
        _mainlobe_bounds(azimuths, azimuth_cut, int(np.argmax(azimuth_cut)))
        if x_aperture > 0
        else (float(azimuths[0]), float(azimuths[-1]))
    )
    el_cut_bounds = (
        _mainlobe_bounds(elevations, elevation_cut, int(np.argmax(elevation_cut)))
        if y_aperture > 0
        else (float(elevations[0]), float(elevations[-1]))
    )
    az_cut_mask = (azimuths < az_cut_bounds[0]) | (azimuths > az_cut_bounds[1])
    el_cut_mask = (elevations < el_cut_bounds[0]) | (elevations > el_cut_bounds[1])
    azimuth_psl_db = float(np.max(np.where(az_cut_mask, azimuth_cut, -np.inf)))
    elevation_psl_db = float(np.max(np.where(el_cut_mask, elevation_cut, -np.inf)))

    azimuth_3db_beamwidth, azimuth_null_beamwidth, azimuth_islr_db = (
        azimuth_cut_metrics(azimuths, azimuth_cut)
    )
    azimuth_first_sidelobe_db, azimuth_first_sidelobe_angle = (
        azimuth_first_sidelobe(azimuths, azimuth_cut)
    )
    azimuth_grating_lobe_db, azimuth_grating_lobe_angle = azimuth_grating_lobe(
        azimuths, azimuth_cut, mainlobe_bounds=az_cut_bounds
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
    normalization_max: float | None = None,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Return one normalized-correlation 2D DBF spectrum for a true az/el angle."""
    _ = tx_pattern, rx_pattern, normalization_max
    scanner = Dbf2dScanner(
        array,
        scan_azimuths_deg=scan_azimuths_deg,
        scan_elevations_deg=scan_elevations_deg,
        channel_patterns=channel_patterns,
        dbf_dictionary=dbf_dictionary,
    )
    spectra_db = scanner.spectrum_db(true_azimuth_deg, true_elevation_deg)
    return scanner.scan_azimuths_deg, scanner.scan_elevations_deg, spectra_db


class Dbf2dScanner:
    """Evaluate 2D DBF spectra for many true angles with one scan dictionary.

    Building the (scan points x channels) dictionary dominates the cost of a
    2D spectrum.  The dictionary depends only on the array, channel patterns
    and dictionary configuration, so animation and batch callers reuse it
    across true angles.  Results are identical to :func:`dbf_2d_spectrum`.
    """

    def __init__(
        self,
        array: AntennaArray,
        scan_azimuths_deg: np.ndarray | None = None,
        scan_elevations_deg: np.ndarray | None = None,
        channel_patterns: ChannelPatternSet | None = None,
        dbf_dictionary: DbfDictionaryConfig | None = None,
    ) -> None:
        self.array = array
        self.scan_azimuths_deg = (
            _default_dbf_angles()
            if scan_azimuths_deg is None
            else np.asarray(scan_azimuths_deg, dtype=float)
        )
        self.scan_elevations_deg = (
            _default_dbf_angles()
            if scan_elevations_deg is None
            else np.asarray(scan_elevations_deg, dtype=float)
        )
        self.channel_patterns = channel_patterns
        self.dbf_dictionary = dbf_dictionary
        az_grid, el_grid = np.meshgrid(self.scan_azimuths_deg, self.scan_elevations_deg)
        self._flat_az = az_grid.ravel()
        self._flat_el = el_grid.ravel()
        self._uses_fixed_dictionary = (
            dbf_dictionary is not None and not dbf_dictionary.uses_auto_ideal_sign
        )
        self._has_phase = _channel_pattern_has_any_phase(channel_patterns, array)
        self._phase_sign = (
            _imported_phase_sign(
                array,
                channel_patterns,
                self.scan_azimuths_deg,
                self.scan_elevations_deg,
            )
            if self._has_phase
            else 1
        )
        self._dictionaries: dict[int, np.ndarray] = {}

    def _dictionary(self, steering_sign: int) -> np.ndarray:
        key = 0 if self._uses_fixed_dictionary else steering_sign
        cached = self._dictionaries.get(key)
        if cached is not None:
            return cached
        if self._uses_fixed_dictionary:
            assert self.dbf_dictionary is not None
            dictionary = self.dbf_dictionary.scan_matrix_2d(
                self.array,
                self._flat_az,
                self._flat_el,
                axis="azimuth",
                channel_patterns=self.channel_patterns,
            )
        else:
            dictionary = _dbf_2d_scan_matrix(
                self.array,
                self._flat_az,
                self._flat_el,
                steering_sign=steering_sign,
            )
        self._dictionaries[key] = dictionary
        return dictionary

    def _steering_sign(
        self,
        true_azimuth_deg: float,
        true_elevation_deg: float,
        signal: np.ndarray,
    ) -> int:
        if not self._has_phase:
            return DBF_DEFAULT_STEERING_SIGN
        candidates: list[tuple[float, int]] = []
        for steering_sign in (DBF_DEFAULT_STEERING_SIGN, 1):
            score = np.abs(self._dictionary(steering_sign) @ signal) ** 2
            peak = int(np.argmax(score))
            error = math.hypot(
                float(self._flat_az[peak]) - true_azimuth_deg,
                float(self._flat_el[peak]) - true_elevation_deg,
            )
            candidates.append((error, steering_sign))
        return min(
            candidates,
            key=lambda item: (
                item[0],
                0 if item[1] == DBF_DEFAULT_STEERING_SIGN else 1,
            ),
        )[1]

    def spectrum_db(
        self,
        true_azimuth_deg: float,
        true_elevation_deg: float,
    ) -> np.ndarray:
        """Return the (elevation x azimuth) correlation spectrum in dB."""
        true_az = float(true_azimuth_deg)
        true_el = float(true_elevation_deg)
        signal = _dbf_2d_signal_vector(
            self.array,
            true_az,
            true_el,
            channel_patterns=self.channel_patterns,
            phase_sign=self._phase_sign,
        )
        if self._uses_fixed_dictionary:
            dictionary = self._dictionary(0)
        else:
            dictionary = self._dictionary(self._steering_sign(true_az, true_el, signal))
        spectra = _dbf_correlation_response(dictionary, signal)[:, 0]
        spectra = spectra.reshape(len(self.scan_elevations_deg), len(self.scan_azimuths_deg))
        return 20.0 * np.log10(np.maximum(spectra, 1e-6))


def dbf_2d_normalization_reference(
    array: AntennaArray,
    scan_azimuths_deg: np.ndarray | None = None,
    scan_elevations_deg: np.ndarray | None = None,
    true_azimuths_deg: np.ndarray | None = None,
    true_elevations_deg: np.ndarray | None = None,
    tx_pattern: ElementPattern | None = None,
    rx_pattern: ElementPattern | None = None,
    channel_patterns: ChannelPatternSet | None = None,
    dbf_dictionary: DbfDictionaryConfig | None = None,
) -> float:
    """Return the legacy 2D reference value.

    DBF spectra are now normalized by correlation coefficient per frame, so the
    amplitude reference no longer changes the displayed result.
    """
    _ = (
        array,
        scan_azimuths_deg,
        scan_elevations_deg,
        true_azimuths_deg,
        true_elevations_deg,
        tx_pattern,
        rx_pattern,
        channel_patterns,
        dbf_dictionary,
    )
    return 1.0


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
    estimated_angles_deg: np.ndarray | None = None,
    focus_range_deg: tuple[float, float] | None = None,
) -> DbfAngleMetrics:
    true_angles = np.asarray(true_angles_deg, dtype=float)
    scan_angles = np.asarray(scan_angles_deg, dtype=float)
    spectra = np.asarray(spectra_db, dtype=float)
    if true_angles.size == 0 or scan_angles.size == 0 or spectra.size == 0:
        return DbfAngleMetrics(None, None, None, None, None, None, None, None, None)

    frame_series = dbf_angle_frame_series_from_spectra(
        true_angles,
        scan_angles,
        spectra,
        estimated_angles_deg=estimated_angles_deg,
    )
    true_angles = frame_series.true_angles_deg
    error_array = frame_series.errors_deg
    margin_array = frame_series.peak_margins_db
    no_fold = _dbf_no_fold_interval(
        true_angles,
        error_array,
        margin_array,
        list(frame_series.quality_flags),
        ambiguity_margin_db=ambiguity_margin_db,
    )

    if focus_range_deg is not None:
        focus_mask = (true_angles >= focus_range_deg[0]) & (true_angles <= focus_range_deg[1])
    else:
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


def _dbf_peak_details(
    scan_angles_deg: np.ndarray,
    spectrum_db: np.ndarray,
) -> tuple[float, float, float, float, str]:
    values = np.asarray(spectrum_db, dtype=float)
    main_index = dbf_peak_index(scan_angles_deg, values)
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
    return (
        float(scan_angles_deg[main_index]),
        main_peak,
        competitor_peak,
        peak_margin,
        quality_flag,
    )


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
    if axis not in {"azimuth", "elevation"}:
        raise ValueError(f"Unknown DBF axis: {axis!r}")
    true_angles_deg, scan_angles_deg, signal_phase, dictionary_for = _dbf_axis_model(
        array,
        axis,
        true_angles_deg,
        scan_angles_deg,
        channel_patterns=channel_patterns,
        dbf_dictionary=dbf_dictionary,
    )
    response = _dbf_correlation_response(dictionary_for(scan_angles_deg), signal_phase)
    _ = tx_pattern, rx_pattern
    spectra = response.T
    spectra_db = 20.0 * np.log10(np.maximum(spectra, 1e-6))
    return true_angles_deg, scan_angles_deg, spectra_db


def _dbf_axis_model(
    array: AntennaArray,
    axis: str,
    true_angles_deg: np.ndarray | None,
    scan_angles_deg: np.ndarray | None,
    channel_patterns: ChannelPatternSet | None,
    dbf_dictionary: DbfDictionaryConfig | None,
):  # noqa: ANN202 - returns (true, scan, signals, dictionary builder)
    """Signals for each true angle plus a dictionary builder for arbitrary angles.

    The steering sign of the automatic ideal dictionary is chosen once on the
    scan grid, so refined searches use exactly the same dictionary.
    """
    true_angles = (
        _default_dbf_angles() if true_angles_deg is None else np.asarray(true_angles_deg, dtype=float)
    )
    scan_angles = (
        _default_dbf_angles() if scan_angles_deg is None else np.asarray(scan_angles_deg, dtype=float)
    )
    signal_phase = _dbf_signal_matrix(
        array,
        true_angles,
        axis=axis,
        channel_patterns=channel_patterns,
    )
    if dbf_dictionary is not None and not dbf_dictionary.uses_auto_ideal_sign:
        def dictionary_for(angles: np.ndarray) -> np.ndarray:
            return dbf_dictionary.scan_matrix(
                array,
                np.asarray(angles, dtype=float),
                axis=axis,
                channel_patterns=channel_patterns,
            )
    else:
        steering_sign = _select_dbf_steering_sign(
            array,
            true_angles,
            scan_angles,
            signal_phase,
            axis=axis,
            channel_patterns=channel_patterns,
        )

        def dictionary_for(angles: np.ndarray) -> np.ndarray:
            return _dbf_scan_matrix(
                array,
                np.asarray(angles, dtype=float),
                axis=axis,
                steering_sign=steering_sign,
            )

    return true_angles, scan_angles, signal_phase, dictionary_for


def dbf_refine_peak_angles(
    array: AntennaArray,
    axis: str,
    true_angles_deg: np.ndarray,
    scan_angles_deg: np.ndarray,
    spectra_db: np.ndarray,
    channel_patterns: ChannelPatternSet | None = None,
    dbf_dictionary: DbfDictionaryConfig | None = None,
    stages: tuple[tuple[float, float], ...] = DBF_REFINE_STAGES,
) -> np.ndarray:
    """Refine each frame's scan-grid peak by re-evaluating the correlation finely.

    The coarse peak is the same strict ``argmax`` used for the performance
    metrics.  Each stage searches ``±span`` around the current estimate with
    ``step`` resolution (default 1°/0.05° then 0.05°/0.002°), using the exact
    signal and dictionary of the spectrum bank, so the refinement adds no
    interpolation bias.  Searches stay inside the scan range.
    """
    true_angles = np.asarray(true_angles_deg, dtype=float)
    scan_angles = np.asarray(scan_angles_deg, dtype=float)
    spectra = np.asarray(spectra_db, dtype=float)
    estimates = scan_angles[np.argmax(spectra, axis=1)].astype(float)
    if _dictionary_is_nearest_neighbour(dbf_dictionary, axis):
        return estimates
    _true, _scan, signals, dictionary_for = _dbf_axis_model(
        array,
        axis,
        true_angles,
        scan_angles,
        channel_patterns=channel_patterns,
        dbf_dictionary=dbf_dictionary,
    )
    low, high = float(scan_angles[0]), float(scan_angles[-1])
    signal_norms = np.linalg.norm(signals, axis=0)
    for span, step in stages:
        offsets = np.arange(-span, span + step / 2.0, step)
        for start in range(0, len(true_angles), 32):
            stop = min(start + 32, len(true_angles))
            candidates = np.clip(estimates[start:stop, None] + offsets[None, :], low, high)
            dictionary = dictionary_for(candidates.ravel()).reshape(
                stop - start, len(offsets), -1
            )
            response = np.abs(np.einsum("fkn,nf->fk", dictionary, signals[:, start:stop]))
            norms = np.linalg.norm(dictionary, axis=2) * signal_norms[None, start:stop].T
            correlation = np.divide(
                response,
                norms,
                out=np.zeros_like(response),
                where=norms > DBF_CORRELATION_EPS,
            )
            best = np.argmax(correlation, axis=1)
            estimates[start:stop] = candidates[np.arange(stop - start), best]
    return estimates


def _dictionary_is_nearest_neighbour(
    dbf_dictionary: DbfDictionaryConfig | None,
    axis: str,
) -> bool:
    if dbf_dictionary is None or dbf_dictionary.mode != "custom":
        return False
    table = dbf_dictionary.custom_table_for_axis(axis)
    return table is not None and table.is_2d


@dataclass(frozen=True)
class EvaluationSettings:
    """Field of view and search settings for one radar evaluation.

    True angles are swept across the FOV in 1° steps.  The DBF search (scan)
    range extends ``search_guard_deg`` beyond the FOV so a target at the FOV
    edge is not flagged as an edge peak; real radars likewise only search
    the directions they serve, which keeps grating lobes outside the FOV from
    being counted as in-FOV ambiguity.
    """

    azimuth_fov_deg: tuple[float, float] = AZIMUTH_FOV
    elevation_fov_deg: tuple[float, float] = ELEVATION_FOV
    search_guard_deg: float = DBF_SEARCH_GUARD_DEG
    refine_peaks: bool = True

    def __post_init__(self) -> None:
        for name in ("azimuth_fov_deg", "elevation_fov_deg"):
            low, high = (float(value) for value in getattr(self, name))
            if not (DBF_SCAN_FOV[0] <= low < 0.0 < high <= DBF_SCAN_FOV[1]):
                raise ValueError(f"{name} must satisfy -90 <= low < 0 < high <= 90.")
            object.__setattr__(self, name, (low, high))
        guard = float(self.search_guard_deg)
        if not math.isfinite(guard) or guard < 0.0:
            raise ValueError("search_guard_deg must be finite and non-negative.")
        object.__setattr__(self, "search_guard_deg", guard)

    def fov(self, axis: str) -> tuple[float, float]:
        if axis == "azimuth":
            return self.azimuth_fov_deg
        if axis == "elevation":
            return self.elevation_fov_deg
        raise ValueError(f"Unknown DBF axis: {axis!r}")

    def true_angles(self, axis: str) -> np.ndarray:
        low, high = self.fov(axis)
        return np.arange(math.ceil(low), math.floor(high) + DBF_SCAN_STEP_DEG / 2.0, DBF_SCAN_STEP_DEG)

    def scan_angles(self, axis: str) -> np.ndarray:
        low, high = self.fov(axis)
        start = max(DBF_SCAN_FOV[0], math.ceil(low) - self.search_guard_deg)
        stop = min(DBF_SCAN_FOV[1], math.floor(high) + self.search_guard_deg)
        return np.arange(start, stop + DBF_SCAN_STEP_DEG / 2.0, DBF_SCAN_STEP_DEG)


@dataclass(frozen=True)
class DbfAxisEvaluation:
    axis: str
    true_angles_deg: np.ndarray
    scan_angles_deg: np.ndarray
    spectra_db: np.ndarray
    frame_series: DbfAngleFrameSeries
    metrics: DbfAngleMetrics


def evaluate_dbf_axis(
    array: AntennaArray,
    axis: str,
    settings: EvaluationSettings,
    channel_patterns: ChannelPatternSet | None = None,
    dbf_dictionary: DbfDictionaryConfig | None = None,
    ambiguity_margin_db: float = DBF_AMBIGUITY_MARGIN_DB,
) -> DbfAxisEvaluation:
    """FOV-bounded DBF evaluation of one axis with optional peak refinement."""
    bank = dbf_azimuth_spectrum_bank if axis == "azimuth" else dbf_elevation_spectrum_bank
    if axis not in {"azimuth", "elevation"}:
        raise ValueError(f"Unknown DBF axis: {axis!r}")
    true_angles, scan_angles, spectra = bank(
        array,
        true_angles_deg=settings.true_angles(axis),
        scan_angles_deg=settings.scan_angles(axis),
        channel_patterns=channel_patterns,
        dbf_dictionary=dbf_dictionary,
    )
    estimates = (
        dbf_refine_peak_angles(
            array,
            axis,
            true_angles,
            scan_angles,
            spectra,
            channel_patterns=channel_patterns,
            dbf_dictionary=dbf_dictionary,
        )
        if settings.refine_peaks
        else None
    )
    frame_series = dbf_angle_frame_series_from_spectra(
        true_angles, scan_angles, spectra, estimated_angles_deg=estimates
    )
    metrics = dbf_angle_metrics_from_spectra(
        true_angles,
        scan_angles,
        spectra,
        ambiguity_margin_db=ambiguity_margin_db,
        estimated_angles_deg=estimates,
        focus_range_deg=settings.fov(axis),
    )
    return DbfAxisEvaluation(axis, true_angles, scan_angles, spectra, frame_series, metrics)


def _dbf_correlation_response(
    dictionary: np.ndarray,
    signals: np.ndarray,
) -> np.ndarray:
    dictionary_matrix = np.asarray(dictionary, dtype=complex)
    signal_matrix = np.asarray(signals, dtype=complex)
    if signal_matrix.ndim == 1:
        signal_matrix = signal_matrix[:, None]
    response = np.abs(dictionary_matrix @ signal_matrix)
    dictionary_norms = np.linalg.norm(dictionary_matrix, axis=1)
    signal_norms = np.linalg.norm(signal_matrix, axis=0)
    denominator = dictionary_norms[:, None] * signal_norms[None, :]
    correlation = np.divide(
        response,
        denominator,
        out=np.zeros_like(response, dtype=float),
        where=denominator > DBF_CORRELATION_EPS,
    )
    return np.clip(correlation, 0.0, 1.0)


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
    return unit_phasor(phase)


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
    return unit_phasor(phase)


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
    uv = np.column_stack([np.ravel(u), np.ravel(v)])
    phase = uv @ (steering_sign * np.pi * virtual_xy.T)
    return unit_phasor(phase.reshape(*np.shape(u), len(virtual_xy)))


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
    return unit_phasor(phase)


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
    phase_sign: int = 1,
) -> np.ndarray:
    if _channel_pattern_has_any_phase(channel_patterns, array):
        return _channel_response(
            array,
            np.asarray([true_azimuth_deg], dtype=float),
            np.asarray([true_elevation_deg], dtype=float),
            channel_patterns,
            phase_sign,
        )[:, 0]
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
    return _dbf_2d_steering_vector(
        array, true_azimuth_deg, true_elevation_deg
    ) * channel_weight


def _channel_response(
    array: AntennaArray,
    azimuth_deg: np.ndarray,
    elevation_deg: np.ndarray,
    channel_patterns: ChannelPatternSet | None,
    phase_sign: int = 1,
) -> np.ndarray:
    """Per-virtual-channel response (channels x directions) with imported phase.

    Imported phase cuts already contain the geometric phase progression of
    their plane, so the channel weight alone is the response along that axis.
    The geometric steering is kept only for an axis without imported phase,
    with the phase sign of the imported data (see :func:`_imported_phase_sign`)
    so both axes follow one convention.
    """
    flat_az = np.asarray(azimuth_deg, dtype=float).ravel()
    flat_el = np.asarray(elevation_deg, dtype=float).ravel()
    u, v = _direction_uv(flat_az, flat_el)
    virtual_count = len(array.tx) * len(array.rx)
    channel_weight = _channel_pattern_weight(channel_patterns, array, flat_az, flat_el)
    has_azimuth_phase = _channel_pattern_has_phase(channel_patterns, array, "azimuth")
    has_elevation_phase = _channel_pattern_has_phase(
        channel_patterns, array, "elevation"
    )
    if has_azimuth_phase:
        # The horizontal cut samples the phase at el = 0, where u = sin(az).
        # Off the cut, read it at the same direction cosine u so its geometric
        # part stays pi*x*u (the elevation cut already follows v = sin(el)).
        # Amplitudes stay at (az, el).
        cut_azimuth = np.degrees(np.arcsin(np.clip(u, -1.0, 1.0)))
        phase_weight = np.asarray(
            _channel_pattern_weight(channel_patterns, array, cut_azimuth, flat_el),
            dtype=complex,
        )
        channel_weight = np.abs(channel_weight) * phase_weight / np.abs(phase_weight)
    response = np.asarray(channel_weight, dtype=complex) * np.ones(
        (virtual_count, len(flat_az)), dtype=complex
    )
    if has_azimuth_phase and has_elevation_phase:
        return response
    virtual_xy = array.virtual_xy()
    phase = np.zeros_like(response, dtype=float)
    if not has_azimuth_phase:
        phase += np.outer(virtual_xy[:, 0], u)
    if not has_elevation_phase:
        phase += np.outer(virtual_xy[:, 1], v)
    return response * unit_phasor(phase_sign * np.pi * phase)


def _imported_phase_sign(
    array: AntennaArray,
    channel_patterns: ChannelPatternSet | None,
    azimuth_angles_deg: np.ndarray,
    elevation_angles_deg: np.ndarray,
) -> int:
    """Sign of the phase progression in imported phase cuts (+1: exp(+j*pi*x*u)).

    Only matters when one plane has imported phase and the other keeps the
    geometric steering.  It is the opposite of the ideal-dictionary sign that
    :func:`_select_dbf_steering_sign` picks for the imported axis.
    """
    has_azimuth_phase = _channel_pattern_has_phase(channel_patterns, array, "azimuth")
    has_elevation_phase = _channel_pattern_has_phase(
        channel_patterns, array, "elevation"
    )
    if has_azimuth_phase == has_elevation_phase:
        return 1
    axis, angles = (
        ("azimuth", np.asarray(azimuth_angles_deg, dtype=float))
        if has_azimuth_phase
        else ("elevation", np.asarray(elevation_angles_deg, dtype=float))
    )
    signal_phase = _dbf_signal_matrix(array, angles, axis, channel_patterns)
    return -_select_dbf_steering_sign(
        array, angles, angles, signal_phase, axis, channel_patterns
    )


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
    combined = virtual_weights.reshape(
        len(tx_names) * len(rx_names), *tx_weights.shape[1:]
    )
    virtual_names = virtual_channel_names(tx_names, rx_names)
    direct_virtual_weights = patterns.complex_weights(
        virtual_names, azimuth_deg, elevation_deg
    )
    return combined * direct_virtual_weights


def _channel_pattern_has_phase(
    patterns: ChannelPatternSet | None,
    array: AntennaArray,
    axis: str,
) -> bool:
    if patterns is None or patterns.is_empty():
        return False
    tx_names = [point.name for point in array.tx]
    rx_names = [point.name for point in array.rx]
    channel_names = [*tx_names, *rx_names, *virtual_channel_names(tx_names, rx_names)]
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
    tx_names = [point.name for point in array.tx]
    rx_names = [point.name for point in array.rx]
    channel_names = [*tx_names, *rx_names, *virtual_channel_names(tx_names, rx_names)]
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
    min_abs_angle: float = GRATING_MIN_ABS_ANGLE_DEG,
    mainlobe_bounds: tuple[float, float] | None = None,
) -> tuple[float | None, float | None]:
    far = np.abs(azimuths) > min_abs_angle
    if mainlobe_bounds is not None:
        far &= (azimuths < mainlobe_bounds[0]) | (azimuths > mainlobe_bounds[1])
    far_indices = np.flatnonzero(far)
    if len(far_indices) == 0:
        return None, None
    peak_indices = local_peak_indices(azimuth_cut_db)
    far_peak_indices = peak_indices[far[peak_indices]]
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


def _mainlobe_bounds(
    angles: np.ndarray,
    cut_db: np.ndarray,
    peak_index: int,
    min_drop_db: float = MAINLOBE_MIN_DROP_DB,
) -> tuple[float, float]:
    """Angles of the first nulls around a peak, at least ``min_drop_db`` down.

    If the cut never drops by ``min_drop_db`` on one side, the main lobe is
    taken to extend to the end of the cut on that side.
    """
    values = np.asarray(cut_db, dtype=float)
    peak = float(values[peak_index])
    bounds = []
    for direction in (-1, 1):
        index = peak_index
        while 0 <= index + direction < len(values) and peak - values[index] < min_drop_db:
            index += direction
        if peak - values[index] < min_drop_db:
            bounds.append(float(angles[index]))
            continue
        while (
            0 <= index + direction < len(values)
            and values[index + direction] <= values[index]
        ):
            index += direction
        bounds.append(float(angles[index]))
    return bounds[0], bounds[1]


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
