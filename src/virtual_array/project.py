"""Project document: the complete, serializable state of one array study.

A project is what the web client edits and what every compute request sends.
It is deliberately self-contained so the server can stay stateless per
request: imported files (element patterns, channel patterns, DBF dictionaries)
are referenced by content-addressed asset IDs instead of local paths.

Coordinates are stored in wavelengths (λ), matching the layout JSON files of
the desktop tool.  The computation core works in λ/2 units; conversion happens
only in :func:`project_array`.
"""

from __future__ import annotations

import contextlib
import math
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from .dbf_dictionary import (
    CHANNEL_MODE_PHYSICAL,
    CHANNEL_MODE_VIRTUAL,
    DBF_DICT_CHANNEL_PATTERN,
    DBF_DICT_CHANNEL_PATTERN_ZERO_REF,
    DBF_DICT_CUSTOM,
    DBF_DICT_IDEAL,
    DBF_DICT_IDEAL_REVERSED,
)
from .element_pattern import virtual_channel_names
from .geometry import AntennaArray, ArrayPoint

PROJECT_SCHEMA_VERSION = 2
LAYOUT_V1_VERSION = 1
MAX_TX_COUNT = 16
MAX_RX_COUNT = 16
# Grid pitch of the layout editor: λ/2, i.e. one core-grid step.
GRID_STEP_LAMBDA = 0.5
HALF_LAMBDA_PER_LAMBDA = 2.0
DEFAULT_FREQUENCY_GHZ = 77.0
DEFAULT_AMBIGUITY_MARGIN_DB = 0.5
DEFAULT_SNR_DB = 10.0
AUTO_LAYOUT_SPACING_LAMBDA = 1.0
AUTO_LAYOUT_TX_Y_LAMBDA = 2.0
AUTO_LAYOUT_RX_Y_LAMBDA = -2.0
COORDINATE_LIMIT_LAMBDA = 500.0
LIGHT_SPEED_MM_PER_NS = 299.792458
GRID_STEPS_LAMBDA = (0.5, 0.25, 0.125, 0.0)
DEFAULT_AZIMUTH_FOV = (-75, 75)
DEFAULT_ELEVATION_FOV = (-15, 15)

# FMCW radar band presets: sweep range and the design (λ reference) frequency.
# 92 GHz has no single harmonised allocation; the 90–94 GHz default is a
# placeholder that projects should overwrite with their chip's sweep range.
BAND_PRESETS: dict[str, dict[str, float]] = {
    "60G": {"start_ghz": 57.0, "stop_ghz": 64.0, "design_ghz": 60.0},
    "77G": {"start_ghz": 76.0, "stop_ghz": 81.0, "design_ghz": 77.0},
    "92G": {"start_ghz": 90.0, "stop_ghz": 94.0, "design_ghz": 92.0},
}

LAYOUT_UNITS_LAMBDA = {"lambda", "λ"}
LEGACY_LAYOUT_UNITS_HALF_LAMBDA = {"lambda/2", "λ/2"}

DictionaryMode = Literal["ideal", "ideal_reversed", "channel_pattern", "custom"]
ChannelMode = Literal["virtual", "physical"]
PatternKind = Literal["amplitude", "phase"]
PatternPlane = Literal["horizontal", "elevation"]


class _Model(BaseModel):
    model_config = ConfigDict(extra="ignore")


class Point(_Model):
    x: float
    y: float

    @field_validator("x", "y")
    @classmethod
    def _finite(cls, value: float) -> float:
        if not math.isfinite(value) or abs(value) > COORDINATE_LIMIT_LAMBDA:
            raise ValueError(
                f"Coordinates must be finite and within ±{COORDINATE_LIMIT_LAMBDA:g} λ."
            )
        return float(value)


class Layout(_Model):
    tx: list[Point] = Field(min_length=1, max_length=MAX_TX_COUNT)
    rx: list[Point] = Field(min_length=1, max_length=MAX_RX_COUNT)


class DictionarySettings(_Model):
    mode: DictionaryMode = "ideal"
    azimuth_asset: str | None = None
    elevation_asset: str | None = None
    channel_mode: ChannelMode = "virtual"
    phase_reversed: bool = False
    zero_phase_calibrated: bool = False

    @field_validator("mode", mode="before")
    @classmethod
    def _legacy_mode(cls, value: Any) -> Any:
        return DBF_DICT_CHANNEL_PATTERN if value == DBF_DICT_CHANNEL_PATTERN_ZERO_REF else value

    @model_validator(mode="after")
    def _custom_needs_asset(self) -> DictionarySettings:
        if (
            self.mode == DBF_DICT_CUSTOM
            and self.azimuth_asset is None
            and self.elevation_asset is None
        ):
            raise ValueError(
                "An imported DBF dictionary needs at least one azimuth or elevation file."
            )
        return self


class ElementPatternSettings(_Model):
    asset: str
    swap_axes: bool = False


class ChannelPatternBinding(_Model):
    """One imported amplitude or phase cut assigned to one channel."""

    channel: str
    kind: PatternKind
    plane: PatternPlane
    asset: str
    # Index of the data column after the angle column in the source file.
    column_index: int = Field(ge=0)
    column: str = ""


class Band(_Model):
    """FMCW sweep range of the radar the array is designed for."""

    preset: Literal["60G", "77G", "92G", "custom"] = "77G"
    start_ghz: float = Field(default=76.0, gt=0.0, le=1000.0)
    stop_ghz: float = Field(default=81.0, gt=0.0, le=1000.0)
    # Frequency of the geometric DBF dictionary when evaluating across the band:
    # "operating" regenerates it for every operating frequency, "design" keeps
    # the design-frequency dictionary (firmware with one fixed steering table).
    dictionary_frequency: Literal["operating", "design"] = "operating"

    @model_validator(mode="after")
    def _ordered(self) -> Band:
        if self.start_ghz >= self.stop_ghz:
            raise ValueError("Band start frequency must be below the stop frequency.")
        return self


class FieldOfView(_Model):
    """Angular coverage the radar must serve; bounds all angle evaluations."""

    azimuth: tuple[int, int] = DEFAULT_AZIMUTH_FOV
    elevation: tuple[int, int] = DEFAULT_ELEVATION_FOV

    @field_validator("azimuth", "elevation")
    @classmethod
    def _contains_boresight(cls, value: tuple[int, int]) -> tuple[int, int]:
        low, high = value
        if not (-90 <= low < 0 < high <= 90):
            raise ValueError("FOV must satisfy -90 <= start < 0 < stop <= 90 degrees.")
        return value


class Requirements(_Model):
    """Optional pass/fail targets; ``None`` means not checked."""

    azimuth_resolution_deg: float | None = Field(default=None, gt=0.0, le=180.0)
    elevation_resolution_deg: float | None = Field(default=None, gt=0.0, le=180.0)
    azimuth_unambiguous_fov: bool = True
    elevation_unambiguous_fov: bool = True
    max_abs_error_deg: float | None = Field(default=None, gt=0.0, le=90.0)
    min_peak_margin_db: float | None = Field(default=None, ge=0.0, le=60.0)
    max_psl_db: float | None = Field(default=None, le=0.0, ge=-80.0)


class NoiseSettings(_Model):
    """Noise scenario for the angle-accuracy Monte Carlo."""

    # Per-virtual-channel SNR of a boresight target after the range/Doppler FFTs.
    snr_db: float = Field(default=DEFAULT_SNR_DB, ge=-20.0, le=40.0)


class Project(_Model):
    version: int = PROJECT_SCHEMA_VERSION
    name: str = Field(default="未命名阵列", max_length=120)
    # Design frequency: the layout's λ is defined at this frequency.
    frequency_ghz: float = Field(default=DEFAULT_FREQUENCY_GHZ, gt=0.0, le=1000.0)
    ambiguity_margin_db: float = Field(default=DEFAULT_AMBIGUITY_MARGIN_DB, ge=0.0, le=60.0)
    band: Band = Field(default_factory=Band)
    fov: FieldOfView = Field(default_factory=FieldOfView)
    grid_step_lambda: float = 0.5
    requirements: Requirements = Field(default_factory=Requirements)
    noise: NoiseSettings = Field(default_factory=NoiseSettings)
    layout: Layout
    dbf_dictionary: DictionarySettings = Field(default_factory=DictionarySettings)
    element_pattern: ElementPatternSettings | None = None
    channel_patterns: list[ChannelPatternBinding] = Field(default_factory=list)

    @model_validator(mode="before")
    @classmethod
    def _infer_band(cls, data: Any) -> Any:
        # Documents written before bands existed: pick the preset containing
        # the design frequency instead of silently defaulting to 77 GHz.
        if isinstance(data, dict) and "band" not in data:
            frequency = data.get("frequency_ghz", DEFAULT_FREQUENCY_GHZ)
            with contextlib.suppress(TypeError, ValueError):
                data = {**data, "band": band_for_frequency(float(frequency)).model_dump()}
        return data

    @field_validator("grid_step_lambda")
    @classmethod
    def _known_grid(cls, value: float) -> float:
        if value not in GRID_STEPS_LAMBDA:
            raise ValueError(f"grid_step_lambda must be one of {GRID_STEPS_LAMBDA}.")
        return value

    @property
    def tx_names(self) -> list[str]:
        return [f"Tx{index}" for index in range(1, len(self.layout.tx) + 1)]

    @property
    def rx_names(self) -> list[str]:
        return [f"Rx{index}" for index in range(1, len(self.layout.rx) + 1)]

    @property
    def physical_channel_names(self) -> list[str]:
        return [*self.tx_names, *self.rx_names]

    @property
    def virtual_channel_names(self) -> list[str]:
        return virtual_channel_names(self.tx_names, self.rx_names)

    @property
    def wavelength_mm(self) -> float:
        return LIGHT_SPEED_MM_PER_NS / self.frequency_ghz

    def asset_ids(self) -> set[str]:
        ids = {binding.asset for binding in self.channel_patterns}
        if self.element_pattern is not None:
            ids.add(self.element_pattern.asset)
        for asset in (self.dbf_dictionary.azimuth_asset, self.dbf_dictionary.elevation_asset):
            if asset is not None:
                ids.add(asset)
        return ids


def band_for_frequency(frequency_ghz: float) -> Band:
    """The preset whose sweep contains the frequency, else a ±2.5% custom band."""
    for name, preset in BAND_PRESETS.items():
        if preset["start_ghz"] <= frequency_ghz <= preset["stop_ghz"]:
            return Band(preset=name, start_ghz=preset["start_ghz"], stop_ghz=preset["stop_ghz"])
    return Band(
        preset="custom",
        start_ghz=round(frequency_ghz * 0.975, 3),
        stop_ghz=round(frequency_ghz * 1.025, 3),
    )


def snap_lambda(value: float) -> float:
    """Snap a λ coordinate to the λ/2 editor grid."""
    return round(value / GRID_STEP_LAMBDA) * GRID_STEP_LAMBDA + 0.0


def project_array(project: Project, operating_frequency_ghz: float | None = None) -> AntennaArray:
    """Build the core array (λ/2 units) from a project.

    The layout is physical: its λ is defined at the design frequency.  At an
    operating frequency ``f`` the electrical positions scale by ``f / f_design``
    (the antennas do not move, the wavelength does).
    """
    scale = HALF_LAMBDA_PER_LAMBDA
    if operating_frequency_ghz is not None:
        scale *= float(operating_frequency_ghz) / project.frequency_ghz
    tx = [
        ArrayPoint(name=name, x=point.x * scale, y=point.y * scale)
        for name, point in zip(project.tx_names, project.layout.tx)
    ]
    rx = [
        ArrayPoint(name=name, x=point.x * scale, y=point.y * scale)
        for name, point in zip(project.rx_names, project.layout.rx)
    ]
    return AntennaArray(tx=tx, rx=rx)


def centered_positions(count: int, spacing: float = AUTO_LAYOUT_SPACING_LAMBDA) -> list[float]:
    """Positions centred on 0 as far as the λ/2 grid allows (even counts sit ½ step left)."""
    offset = snap_lambda((count - 1) * spacing / 2.0)
    return [_clean(index * spacing - offset) for index in range(count)]


def auto_layout(tx_count: int, rx_count: int) -> Layout:
    """Standard TDM/DDM-MIMO azimuth layout: a filled λ/2 virtual ULA.

    Rx are spaced λ/2 and Tx are spaced ``rx_count · λ/2``, so the
    ``tx_count · rx_count`` virtual channels form a uniform λ/2 line without
    duplicates or grating lobes (e.g. 3T4R → 12-element virtual ULA).  Tx and
    Rx sit on separate rows only so they are distinguishable in the editor.
    """
    if not 1 <= tx_count <= MAX_TX_COUNT:
        raise ValueError(f"Tx count must be from 1 to {MAX_TX_COUNT}.")
    if not 1 <= rx_count <= MAX_RX_COUNT:
        raise ValueError(f"Rx count must be from 1 to {MAX_RX_COUNT}.")
    rx_spacing = GRID_STEP_LAMBDA
    tx_spacing = rx_count * GRID_STEP_LAMBDA
    return Layout(
        tx=[Point(x=x, y=AUTO_LAYOUT_TX_Y_LAMBDA) for x in centered_positions(tx_count, tx_spacing)],
        rx=[Point(x=x, y=AUTO_LAYOUT_RX_Y_LAMBDA) for x in centered_positions(rx_count, rx_spacing)],
    )


def default_project() -> Project:
    """The reference 8T8R layout (examples/case4) used as the starting point."""
    from .examples.case4_5tx7rx_sel import RX_X, RX_Y, TX_X, TX_Y

    scale = 1.0 / HALF_LAMBDA_PER_LAMBDA
    return Project(
        name="Case4 8T8R 77G",
        layout=Layout(
            tx=[Point(x=x * scale, y=y * scale) for x, y in zip(TX_X, TX_Y)],
            rx=[Point(x=x * scale, y=y * scale) for x, y in zip(RX_X, RX_Y)],
        ),
    )


def layout_from_v1(config: Any) -> Layout:
    """Parse a desktop-tool layout JSON (version 1) into a layout.

    Element names in the file are ignored: channels are numbered by list
    order, exactly as the desktop importer did.  Coordinates are kept as
    given (the desktop importer snapped them to λ/2, which silently moved
    off-grid antennas of real layouts).
    """
    if not isinstance(config, dict):
        raise ValueError("Layout config must be a JSON object.")
    if config.get("version") != LAYOUT_V1_VERSION:
        raise ValueError(f"Unsupported layout version: {config.get('version')!r}.")
    unit = config.get("unit")
    if unit not in LAYOUT_UNITS_LAMBDA | LEGACY_LAYOUT_UNITS_HALF_LAMBDA:
        raise ValueError("Layout unit must be 'lambda'.")
    scale = 1.0 if unit in LAYOUT_UNITS_LAMBDA else 1.0 / HALF_LAMBDA_PER_LAMBDA

    points: dict[str, list[Point]] = {}
    for kind, limit in (("tx", MAX_TX_COUNT), ("rx", MAX_RX_COUNT)):
        raw_points = config.get(kind)
        if not isinstance(raw_points, list) or not raw_points:
            raise ValueError(f"Layout field '{kind}' must be a non-empty list.")
        if len(raw_points) > limit:
            raise ValueError(
                f"Layout has {len(raw_points)} {kind.capitalize()} elements; maximum is {limit}."
            )
        parsed: list[Point] = []
        for index, raw_point in enumerate(raw_points):
            if not isinstance(raw_point, dict):
                raise ValueError(f"{kind}[{index}] must be an object.")
            try:
                x = _clean(float(raw_point["x"]) * scale)
                y = _clean(float(raw_point["y"]) * scale)
                parsed.append(Point(x=x, y=y))
            except KeyError as exc:
                raise ValueError(f"{kind}[{index}] is missing coordinate {exc}.") from exc
            except (TypeError, ValueError) as exc:
                raise ValueError(f"{kind}[{index}] has invalid coordinates.") from exc
        points[kind] = parsed
    return Layout(tx=points["tx"], rx=points["rx"])


def project_from_document(document: Any) -> Project:
    """Accept either a v2 project document or a v1 layout file."""
    if not isinstance(document, dict):
        raise ValueError("Project file must be a JSON object.")
    if document.get("version") == LAYOUT_V1_VERSION:
        layout = layout_from_v1(document)
        project = Project(layout=layout)
        evaluation = document.get("evaluation")
        if isinstance(evaluation, dict):
            frequency = _parse_number(evaluation.get("frequency_ghz") or evaluation.get("frequency_mode"))
            margin = _parse_number(evaluation.get("ambiguity_margin_db"))
            updates: dict[str, Any] = {}
            if frequency is not None and frequency > 0:
                updates["frequency_ghz"] = frequency
                updates["band"] = band_for_frequency(frequency)
            if margin is not None and margin >= 0:
                updates["ambiguity_margin_db"] = margin
            if updates:
                project = project.model_copy(update=updates)
        return project
    if document.get("version") == PROJECT_SCHEMA_VERSION:
        return Project.model_validate(document)
    raise ValueError(f"Unsupported project version: {document.get('version')!r}.")


def layout_to_v1(project: Project, evaluation: dict[str, Any] | None = None) -> dict[str, Any]:
    """Export a desktop-compatible layout JSON (version 1)."""
    document: dict[str, Any] = {
        "version": LAYOUT_V1_VERSION,
        "unit": "lambda",
        "tx": [
            {"name": name, "x": json_number(point.x, 9), "y": json_number(point.y, 9)}
            for name, point in zip(project.tx_names, project.layout.tx)
        ],
        "rx": [
            {"name": name, "x": json_number(point.x, 9), "y": json_number(point.y, 9)}
            for name, point in zip(project.rx_names, project.layout.rx)
        ],
    }
    if evaluation is not None:
        document["evaluation"] = evaluation
    return document


def _clean(value: float) -> float:
    rounded = round(value, 9)
    return 0.0 if rounded == 0 else rounded


def json_number(value: float | None, digits: int = 6) -> float | int | None:
    if value is None or not math.isfinite(value):
        return None
    rounded = round(float(value), digits)
    if abs(rounded - round(rounded)) < 10**-digits:
        return int(round(rounded))
    return rounded


def _parse_number(value: Any) -> float | None:
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, (int, float)):
        number = float(value)
    else:
        text = str(value).strip().lower().replace(",", ".")
        for suffix in ("ghz", "db", "g"):
            if text.endswith(suffix):
                text = text[: -len(suffix)].strip()
                break
        try:
            number = float(text)
        except ValueError:
            return None
    return number if math.isfinite(number) else None


__all__ = [
    "CHANNEL_MODE_PHYSICAL",
    "CHANNEL_MODE_VIRTUAL",
    "DBF_DICT_CHANNEL_PATTERN",
    "DBF_DICT_CUSTOM",
    "DBF_DICT_IDEAL",
    "DBF_DICT_IDEAL_REVERSED",
    "BAND_PRESETS",
    "Band",
    "ChannelPatternBinding",
    "FieldOfView",
    "Requirements",
    "DictionarySettings",
    "ElementPatternSettings",
    "Layout",
    "Point",
    "Project",
    "auto_layout",
    "default_project",
    "layout_from_v1",
    "layout_to_v1",
    "project_array",
    "project_from_document",
    "snap_lambda",
]
