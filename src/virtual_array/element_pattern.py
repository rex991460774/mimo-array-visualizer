from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import numpy as np


ANGLE_HEADER_KEYWORDS = ("theta", "angle", "azimuth", "az", "deg")
GAIN_HEADER_KEYWORDS = ("gain", "db", "dbi", "realized")


@dataclass(frozen=True)
class ElementPattern:
    name: str
    source_path: str
    angle_column: str
    horizontal_column: str
    elevation_column: str | None
    angles_deg: np.ndarray
    horizontal_gain_db: np.ndarray
    elevation_gain_db: np.ndarray | None = None

    def horizontal_gain_db_at(self, angles_deg: np.ndarray) -> np.ndarray:
        return np.interp(
            angles_deg,
            self.angles_deg,
            self.horizontal_gain_db,
            left=float(self.horizontal_gain_db[0]),
            right=float(self.horizontal_gain_db[-1]),
        )

    def elevation_gain_db_at(self, angles_deg: np.ndarray) -> np.ndarray:
        gain_db = (
            self.elevation_gain_db
            if self.elevation_gain_db is not None
            else self.horizontal_gain_db
        )
        return np.interp(
            angles_deg,
            self.angles_deg,
            gain_db,
            left=float(gain_db[0]),
            right=float(gain_db[-1]),
        )

    def normalized_horizontal_gain_db_at(self, angles_deg: np.ndarray) -> np.ndarray:
        return self.horizontal_gain_db_at(angles_deg) - float(np.max(self.horizontal_gain_db))

    def normalized_elevation_gain_db_at(self, angles_deg: np.ndarray) -> np.ndarray:
        gain_db = (
            self.elevation_gain_db
            if self.elevation_gain_db is not None
            else self.horizontal_gain_db
        )
        return self.elevation_gain_db_at(angles_deg) - float(np.max(gain_db))

    def amplitude_grid(
        self,
        azimuth_deg: np.ndarray,
        elevation_deg: np.ndarray,
    ) -> np.ndarray:
        horizontal = np.power(10.0, self.horizontal_gain_db_at(azimuth_deg) / 20.0)
        if self.elevation_gain_db is None:
            return horizontal
        elevation = np.power(10.0, self.elevation_gain_db_at(elevation_deg) / 20.0)
        return horizontal * elevation

    def display_name(self) -> str:
        if self.elevation_column is None:
            return f"{self.name} ({self.horizontal_column})"
        return f"{self.name} (H: {self.horizontal_column}; V: {self.elevation_column})"

    def swapped_axes(self) -> "ElementPattern":
        if self.elevation_column is None or self.elevation_gain_db is None:
            return self
        return ElementPattern(
            name=self.name,
            source_path=self.source_path,
            angle_column=self.angle_column,
            horizontal_column=self.elevation_column,
            elevation_column=self.horizontal_column,
            angles_deg=self.angles_deg,
            horizontal_gain_db=self.elevation_gain_db,
            elevation_gain_db=self.horizontal_gain_db,
        )


@dataclass(frozen=True)
class PatternCutMetrics:
    peak_angle_deg: float
    peak_gain_dbi: float
    beamwidth_3db_deg: float | None
    beamwidth_6db_deg: float | None


def load_element_pattern(path: str | Path) -> ElementPattern:
    source_path = Path(path)
    delimiter = _detect_delimiter(source_path)
    with source_path.open("r", encoding="utf-8-sig", newline="") as file:
        rows = [
            row
            for row in csv.reader(file, delimiter=delimiter)
            if row and not _is_comment_or_blank(row)
        ]

    if len(rows) < 2:
        raise ValueError("Pattern file must contain a header and at least one data row.")

    header = [cell.strip() for cell in rows[0]]
    angle_index = _find_angle_column(header)
    gain_indices = _find_gain_columns(header, exclude={angle_index})
    if not gain_indices:
        raise ValueError("Pattern file must contain at least one gain column.")
    horizontal_index, elevation_index = _default_pattern_axes(gain_indices)

    values = []
    for row_index, row in enumerate(rows[1:], start=2):
        required_columns = [angle_index, horizontal_index]
        if elevation_index is not None:
            required_columns.append(elevation_index)
        required_index = max(required_columns)
        if required_index >= len(row):
            continue
        try:
            angle = _parse_float(row[angle_index])
            horizontal_gain = _parse_float(row[horizontal_index])
            elevation_gain = (
                _parse_float(row[elevation_index])
                if elevation_index is not None
                else np.nan
            )
        except ValueError as exc:
            raise ValueError(f"Invalid numeric value on row {row_index}.") from exc
        if np.isfinite(angle) and np.isfinite(horizontal_gain):
            values.append((angle, horizontal_gain, elevation_gain))

    if len(values) < 2:
        raise ValueError("Pattern file must contain at least two valid data rows.")

    values_array = np.asarray(values, dtype=float)
    order = np.argsort(values_array[:, 0])
    angles = values_array[order, 0]
    horizontal_gains = values_array[order, 1]
    elevation_gains = values_array[order, 2]
    angles, horizontal_gains, elevation_gains = _merge_duplicate_angles(
        angles, horizontal_gains, elevation_gains
    )
    elevation_gain_db = elevation_gains if elevation_index is not None else None

    return ElementPattern(
        name=source_path.name,
        source_path=str(source_path),
        angle_column=header[angle_index],
        horizontal_column=header[horizontal_index],
        elevation_column=header[elevation_index] if elevation_index is not None else None,
        angles_deg=angles,
        horizontal_gain_db=horizontal_gains,
        elevation_gain_db=elevation_gain_db,
    )


def available_gain_columns(path: str | Path) -> list[str]:
    source_path = Path(path)
    delimiter = _detect_delimiter(source_path)
    with source_path.open("r", encoding="utf-8-sig", newline="") as file:
        rows = [
            row
            for row in csv.reader(file, delimiter=delimiter)
            if row and not _is_comment_or_blank(row)
        ]
    if not rows:
        return []
    header = [cell.strip() for cell in rows[0]]
    angle_index = _find_angle_column(header)
    return [header[index] for index in _find_gain_columns(header, exclude={angle_index})]


def pattern_cut_metrics(
    angles_deg: np.ndarray,
    gain_db: np.ndarray,
) -> PatternCutMetrics:
    if len(angles_deg) == 0 or len(gain_db) == 0:
        raise ValueError("Pattern cut must contain at least one point.")

    peak_index = int(np.argmax(gain_db))
    peak_angle = float(angles_deg[peak_index])
    peak_gain = float(gain_db[peak_index])
    return PatternCutMetrics(
        peak_angle_deg=peak_angle,
        peak_gain_dbi=peak_gain,
        beamwidth_3db_deg=_beamwidth_at_drop(angles_deg, gain_db, peak_index, 3.0),
        beamwidth_6db_deg=_beamwidth_at_drop(angles_deg, gain_db, peak_index, 6.0),
    )


def format_pattern_cut_metrics(metrics: PatternCutMetrics) -> str:
    bw_3db = _format_optional_degrees(metrics.beamwidth_3db_deg)
    bw_6db = _format_optional_degrees(metrics.beamwidth_6db_deg)
    return (
        f"Peak {metrics.peak_gain_dbi:.2f} dBi @ {metrics.peak_angle_deg:.1f}° | "
        f"3dB BW {bw_3db} | 6dB BW {bw_6db}"
    )


def _detect_delimiter(path: Path) -> str:
    if path.suffix.lower() == ".tsv":
        return "\t"

    sample = path.read_text(encoding="utf-8-sig", errors="ignore")[:4096]
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=",\t;")
    except csv.Error:
        return ","
    return dialect.delimiter


def _beamwidth_at_drop(
    angles_deg: np.ndarray,
    gain_db: np.ndarray,
    peak_index: int,
    drop_db: float,
) -> float | None:
    threshold = float(gain_db[peak_index]) - drop_db
    left = _threshold_angle(angles_deg, gain_db, peak_index, threshold, -1)
    right = _threshold_angle(angles_deg, gain_db, peak_index, threshold, 1)
    if left is None or right is None:
        return None
    return float(right - left)


def _threshold_angle(
    angles_deg: np.ndarray,
    gain_db: np.ndarray,
    peak_index: int,
    threshold_db: float,
    direction: int,
) -> float | None:
    index = peak_index + direction
    while 0 <= index < len(gain_db):
        if gain_db[index] <= threshold_db:
            prev_index = index - direction
            x0 = float(angles_deg[prev_index])
            x1 = float(angles_deg[index])
            y0 = float(gain_db[prev_index])
            y1 = float(gain_db[index])
            if y1 == y0:
                return x1
            fraction = (threshold_db - y0) / (y1 - y0)
            return x0 + fraction * (x1 - x0)
        index += direction
    return None


def _format_optional_degrees(value: float | None) -> str:
    if value is None or not np.isfinite(value):
        return "N/A"
    return f"{value:.1f}°"


def _find_angle_column(header: list[str]) -> int:
    for index, column in enumerate(header):
        text = column.lower()
        if "theta" in text:
            return index
    for index, column in enumerate(header):
        text = column.lower()
        if any(keyword in text for keyword in ANGLE_HEADER_KEYWORDS):
            return index
    return 0


def _find_gain_columns(header: list[str], exclude: set[int]) -> list[int]:
    preferred = [
        index
        for index, column in enumerate(header)
        if index not in exclude and _looks_like_gain_column(column)
    ]
    if preferred:
        return preferred
    return [index for index in range(len(header)) if index not in exclude]


def _default_pattern_axes(gain_indices: list[int]) -> tuple[int, int | None]:
    if len(gain_indices) < 2:
        return gain_indices[0], None
    return gain_indices[1], gain_indices[0]


def _looks_like_gain_column(column: str) -> bool:
    text = column.lower()
    return any(keyword in text for keyword in GAIN_HEADER_KEYWORDS)


def _parse_float(value: str) -> float:
    cleaned = value.strip()
    if not cleaned:
        raise ValueError("empty numeric value")
    return float(cleaned)


def _is_comment_or_blank(row: Iterable[str]) -> bool:
    stripped = [cell.strip() for cell in row]
    return not any(stripped) or stripped[0].startswith("#")


def _merge_duplicate_angles(
    angles: np.ndarray,
    horizontal_gains: np.ndarray,
    elevation_gains: np.ndarray,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    unique_angles, inverse = np.unique(angles, return_inverse=True)
    if len(unique_angles) == len(angles):
        return angles, horizontal_gains, elevation_gains

    merged_horizontal = np.zeros_like(unique_angles, dtype=float)
    merged_elevation = np.zeros_like(unique_angles, dtype=float)
    for index in range(len(unique_angles)):
        merged_horizontal[index] = float(np.mean(horizontal_gains[inverse == index]))
        merged_elevation[index] = float(np.mean(elevation_gains[inverse == index]))
    return unique_angles, merged_horizontal, merged_elevation
