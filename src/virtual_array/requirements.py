"""Pass/fail checks of array performance against project requirements.

Requirements replace the former fixed automotive "front radar" grading: a
60 GHz presence sensor, a 77 GHz corner radar and a 92 GHz imaging radar have
very different targets, so each project states its own.  Every requirement is
optional; unset requirements are not checked.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from .analysis import ArrayMetrics, DbfAngleMetrics

STATUS_PASS = "pass"
STATUS_FAIL = "fail"
STATUS_NOT_APPLICABLE = "na"


@dataclass(frozen=True)
class RequirementSpec:
    azimuth_resolution_deg: float | None = None
    elevation_resolution_deg: float | None = None
    azimuth_unambiguous_fov: bool = True
    elevation_unambiguous_fov: bool = True
    max_abs_error_deg: float | None = None
    min_peak_margin_db: float | None = None
    max_psl_db: float | None = None


@dataclass(frozen=True)
class RequirementCheck:
    key: str
    axis: str | None
    target: float | None
    actual: float | None
    status: str


def measured_resolution(metrics: ArrayMetrics, axis: str) -> float | None:
    """3 dB beamwidth of the actual array response, else the aperture estimate."""
    if axis == "azimuth":
        measured, estimate = metrics.azimuth_3db_beamwidth, metrics.azimuth_resolution
    else:
        measured, estimate = metrics.elevation_3db_beamwidth, metrics.elevation_resolution
    if estimate is None:
        return None
    return measured if measured is not None else estimate


def check_requirements(
    spec: RequirementSpec,
    metrics: ArrayMetrics,
    angle: dict[str, DbfAngleMetrics | None],
    fov: dict[str, tuple[float, float]],
) -> list[RequirementCheck]:
    checks: list[RequirementCheck] = []
    for axis, limit in (
        ("azimuth", spec.azimuth_resolution_deg),
        ("elevation", spec.elevation_resolution_deg),
    ):
        if limit is None:
            continue
        actual = measured_resolution(metrics, axis)
        status = STATUS_PASS if actual is not None and actual <= limit else STATUS_FAIL
        checks.append(RequirementCheck("resolution", axis, limit, actual, status))

    for axis, required in (
        ("azimuth", spec.azimuth_unambiguous_fov),
        ("elevation", spec.elevation_unambiguous_fov),
    ):
        if not required:
            continue
        axis_metrics = angle.get(axis)
        low, high = fov[axis]
        if axis_metrics is None:
            checks.append(RequirementCheck("unambiguous_fov", axis, high - low, None, STATUS_NOT_APPLICABLE))
            continue
        left, right = axis_metrics.no_fold_left, axis_metrics.no_fold_right
        covered = (
            left is not None
            and right is not None
            and left <= low + 1e-9
            and right >= high - 1e-9
        )
        width = axis_metrics.no_fold_width
        checks.append(
            RequirementCheck(
                "unambiguous_fov",
                axis,
                high - low,
                width,
                STATUS_PASS if covered else STATUS_FAIL,
            )
        )

    if spec.max_abs_error_deg is not None:
        for axis in ("azimuth", "elevation"):
            axis_metrics = angle.get(axis)
            if axis_metrics is None:
                continue
            actual = axis_metrics.focus_max_abs_error
            ok = actual is not None and math.isfinite(actual) and actual <= spec.max_abs_error_deg
            checks.append(
                RequirementCheck(
                    "max_error", axis, spec.max_abs_error_deg, actual, STATUS_PASS if ok else STATUS_FAIL
                )
            )

    if spec.min_peak_margin_db is not None:
        for axis in ("azimuth", "elevation"):
            axis_metrics = angle.get(axis)
            if axis_metrics is None:
                continue
            actual = axis_metrics.min_peak_margin_db
            ok = actual is not None and actual >= spec.min_peak_margin_db
            checks.append(
                RequirementCheck(
                    "peak_margin", axis, spec.min_peak_margin_db, actual, STATUS_PASS if ok else STATUS_FAIL
                )
            )

    if spec.max_psl_db is not None:
        actual = metrics.psl_db
        ok = not math.isfinite(actual) or actual <= spec.max_psl_db
        checks.append(
            RequirementCheck("psl", None, spec.max_psl_db, actual, STATUS_PASS if ok else STATUS_FAIL)
        )
    return checks
