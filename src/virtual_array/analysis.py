from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .element_pattern import ElementPattern
from .geometry import AntennaArray


AZIMUTH_FOV = (-75.0, 75.0)
ELEVATION_FOV = (-15.0, 15.0)
AF_GRID_SIZE = 181
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


def calculate_metrics_and_psf(
    array: AntennaArray,
    unique: np.ndarray | None = None,
    counts: np.ndarray | None = None,
    decimals: int = 9,
    tx_pattern: ElementPattern | None = None,
    rx_pattern: ElementPattern | None = None,
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
    array_factor = np.exp(1j * phase).sum(axis=0)
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
