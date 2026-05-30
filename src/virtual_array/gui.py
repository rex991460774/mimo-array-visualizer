from __future__ import annotations

import tkinter as tk
import json
import logging
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

import numpy as np
from matplotlib import rcParams
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure
from matplotlib.patches import Rectangle
from matplotlib.widgets import Button as MplButton

from .app_state import load_state, save_state, state_path
from .analysis import (
    AZIMUTH_FOV,
    ELEVATION_FOV,
    MAINLOBE_GUARD_AZ,
    MAINLOBE_GUARD_EL,
    ArrayMetrics,
    calculate_metrics_and_psf,
    local_peak_indices,
)
from .element_pattern import (
    ElementPattern,
    format_pattern_cut_metrics,
    load_element_pattern,
    pattern_cut_metrics,
)
from .examples.case4_5tx7rx_sel import build_array
from .geometry import AntennaArray, ArrayPoint
from .grid import GRID_STEP, snap_to_grid
from .logging_config import configure_logging, current_log_path, install_excepthook
from .version import APP_VERSION


LOGGER = logging.getLogger(__name__)

rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei", "SimSun", "DejaVu Sans"]
rcParams["axes.unicode_minus"] = False

# ── Global constants ──────────────────────────────────────────────────
ROUND_DECIMALS = 9
LAYOUT_CONFIG_VERSION = 1
LOCAL_STATE_VERSION = 1
LAYOUT_UNIT = "lambda"
LAYOUT_UNITS_LAMBDA = {"lambda", "λ"}
LEGACY_LAYOUT_UNITS_HALF_LAMBDA = {"lambda/2", "λ/2"}
MAX_TX_COUNT = 16
MAX_RX_COUNT = 16
TITLE_SIZE = 13
RESPONSE_MODE_AZIMUTH = "az"
RESPONSE_MODE_ELEVATION = "el"
RESPONSE_SIDELOBE_PROMINENCE_DB = 0.5
RESPONSE_SIDELOBE_GUARD_CLEARANCE_DB = 0.5

DEFAULT_FREQUENCY_MODE = "77 GHz"
FREQUENCY_MODES_MM = {
    "77 GHz": 3.896,
    "92 GHz": 3.259,
    "60 GHz": 4.997,
}

DISPLAY_SCALE_LAMBDA = 0.5
DISPLAY_GRID_STEP_LAMBDA = 0.5

# Window geometry
WINDOW_WIDTH = 1600
WINDOW_HEIGHT = 1000
WINDOW_MIN_WIDTH = 1200
WINDOW_MIN_HEIGHT = 800

# Figure DPI (fixed for consistent rendering across displays)
FIG_DPI = 100

# Figure sizes (inches → pixels at FIG_DPI)
PHYS_FIG_W = 6.8
PHYS_FIG_H = 3.2
VIRT_FIG_W = 6.8
VIRT_FIG_H = 3.2
RESPONSE_FIG_W = 6.8
RESPONSE_FIG_H = 2.8

PSL_COLORS = {
    "Good": "#2e7d32",
    "Acceptable": "#b58900",
    "Risky": "#ef6c00",
    "Bad": "#c62828",
}

NOTE_STYLES = {
    "duplicate": ("⚠️", "#ef6c00"),
    "windowing": ("📉", "#b58900"),
    "ambiguity high": ("🚨", "#c62828"),
    "ambiguity medium": ("⚠️", "#b58900"),
    "none": ("✅", "#2e7d32"),
}

# ── Theme ─────────────────────────────────────────────────────────────
THEME = {
    # Base
    "bg": "#f5f3f0",
    "card_bg": "#ffffff",
    "card_border": "#e2dfdb",
    "status_bar_bg": "#eae8e4",
    # Accent
    "accent": "#3b6e8f",
    "accent_hover": "#2d5a78",
    "accent_light": "#dce8f0",
    # Text
    "text_primary": "#2c2c2c",
    "text_secondary": "#6b6b6b",
    "text_muted": "#999999",
    # Typography
    "font_family": "Segoe UI",
    "font_family_mono": "Cascadia Code",
    "font_size_sm": 9,
    "font_size_base": 10,
    "font_size_lg": 13,
    # Matplotlib
    "fig_facecolor": "#fafaf8",
    "grid_color": "#c0bdb8",
    "grid_alpha": 0.15,
    # MplButton
    "mpl_btn_bg": "#f0eeeb",
    "mpl_btn_hover": "#dce8f0",
    "mpl_btn_text": "#3b6e8f",
}


# ── Data classes ──────────────────────────────────────────────────────
@dataclass
class EditableElement:
    kind: str
    index: int
    name: str
    x: float
    y: float


@dataclass(frozen=True)
class ResponseCut:
    mode: str
    label: str
    angles: np.ndarray
    gains_db: np.ndarray
    fov: tuple[float, float]
    mainlobe_guard: float
    x_label: str
    pattern_label: str


@dataclass
class ResponseChart:
    """Encapsulates per-axis response chart state (fig, axes, canvas, hover, buttons)."""

    fig: Figure
    ax: any  # matplotlib Axes
    canvas: FigureCanvasTkAgg
    hover_annotation: any = None  # matplotlib Annotation
    hover_db: np.ndarray = None
    hover_angles: np.ndarray = None
    buttons: list = None
    button_callbacks: list = None

    def __post_init__(self) -> None:
        if self.hover_db is None:
            self.hover_db = np.empty(0, dtype=float)
        if self.hover_angles is None:
            self.hover_angles = np.empty(0, dtype=float)
        if self.buttons is None:
            self.buttons = []
        if self.button_callbacks is None:
            self.button_callbacks = []


def _response_cut_for_mode(
    af_db: np.ndarray,
    azimuths: np.ndarray,
    elevations: np.ndarray,
    mode: str,
) -> ResponseCut:
    if mode == RESPONSE_MODE_ELEVATION:
        az0_index = int(np.argmin(np.abs(azimuths)))
        return ResponseCut(
            mode=RESPONSE_MODE_ELEVATION,
            label="El",
            angles=elevations,
            gains_db=af_db[:, az0_index],
            fov=ELEVATION_FOV,
            mainlobe_guard=MAINLOBE_GUARD_EL,
            x_label="Elevation angle (deg)",
            pattern_label="Element pattern (V)",
        )

    el0_index = int(np.argmin(np.abs(elevations)))
    return ResponseCut(
        mode=RESPONSE_MODE_AZIMUTH,
        label="Az",
        angles=azimuths,
        gains_db=af_db[el0_index, :],
        fov=AZIMUTH_FOV,
        mainlobe_guard=MAINLOBE_GUARD_AZ,
        x_label="Azimuth angle (deg)",
        pattern_label="Element pattern (H)",
    )


def _response_sidelobe_marker(
    angles: np.ndarray,
    gains_db: np.ndarray,
    guard: float,
    min_prominence_db: float = RESPONSE_SIDELOBE_PROMINENCE_DB,
    min_guard_clearance_db: float = RESPONSE_SIDELOBE_GUARD_CLEARANCE_DB,
) -> tuple[int, bool]:
    peak_indices = local_peak_indices(gains_db)
    sidelobe_mask = np.abs(angles) > guard
    sidelobe_peak_indices = np.array(
        [
            index
            for index in peak_indices[sidelobe_mask[peak_indices]]
            if _peak_prominence_db(gains_db, int(index)) >= min_prominence_db
            and _peak_guard_clearance_db(angles, gains_db, guard, int(index))
            >= min_guard_clearance_db
        ],
        dtype=int,
    )
    if len(sidelobe_peak_indices):
        index = int(sidelobe_peak_indices[np.argmax(gains_db[sidelobe_peak_indices])])
        return index, True
    if np.any(sidelobe_mask):
        return int(np.argmax(np.where(sidelobe_mask, gains_db, -np.inf))), False
    return int(np.argmax(gains_db)), False


def _peak_prominence_db(values_db: np.ndarray, peak_index: int) -> float:
    peak_db = float(values_db[peak_index])
    left_min = peak_db
    for index in range(peak_index - 1, -1, -1):
        value = float(values_db[index])
        if value > peak_db:
            break
        left_min = min(left_min, value)

    right_min = peak_db
    for index in range(peak_index + 1, len(values_db)):
        value = float(values_db[index])
        if value > peak_db:
            break
        right_min = min(right_min, value)

    return peak_db - max(left_min, right_min)


def _peak_guard_clearance_db(
    angles: np.ndarray,
    gains_db: np.ndarray,
    guard: float,
    peak_index: int,
) -> float:
    peak_angle = float(angles[peak_index])
    if peak_angle < 0.0:
        side_indices = np.flatnonzero(angles < -guard)
        if len(side_indices) == 0:
            return 0.0
        guard_index = int(side_indices[np.argmax(angles[side_indices])])
    else:
        side_indices = np.flatnonzero(angles > guard)
        if len(side_indices) == 0:
            return 0.0
        guard_index = int(side_indices[np.argmin(angles[side_indices])])
    return float(gains_db[peak_index] - gains_db[guard_index])


# ── Formatting helpers ────────────────────────────────────────────────
def _format_float(value: float | None, unit: str = "") -> str:
    if value is None or not np.isfinite(value):
        return "N/A"
    return f"{value:.2f}{unit}"


def _format_db(value: float | None) -> str:
    if value is None or not np.isfinite(value):
        return "N/A"
    return f"{value:.2f} dB"


def _format_db_at_az(value: float | None, angle: float | None) -> str:
    if value is None or angle is None or not np.isfinite(value) or not np.isfinite(angle):
        return "N/A"
    return f"{value:.2f} dB @ Az {angle:.1f}°"


def _format_mm(value: float) -> str:
    return f"{value:.1f} mm"


def _json_number(value: float | None, digits: int = 6) -> float | int | None:
    if value is None or not np.isfinite(value):
        return None
    rounded = round(float(value), digits)
    if abs(rounded - round(rounded)) < 10 ** -digits:
        return int(round(rounded))
    return rounded


def _layout_config_to_json(config: dict[str, object]) -> str:
    lines = [
        "{",
        f'  "version": {json.dumps(config["version"], ensure_ascii=False)},',
        f'  "unit": {json.dumps(config["unit"], ensure_ascii=False)},',
        '  "tx": [',
    ]
    tx_points = config["tx"]
    rx_points = config["rx"]
    if not isinstance(tx_points, list) or not isinstance(rx_points, list):
        raise ValueError("Layout config tx/rx must be lists.")

    for index, point in enumerate(tx_points):
        suffix = "," if index < len(tx_points) - 1 else ""
        lines.append(
            "    "
            + json.dumps(point, ensure_ascii=False, separators=(", ", ": "))
            + suffix
        )
    lines.extend(['  ],', '  "rx": ['])
    for index, point in enumerate(rx_points):
        suffix = "," if index < len(rx_points) - 1 else ""
        lines.append(
            "    "
            + json.dumps(point, ensure_ascii=False, separators=(", ", ": "))
            + suffix
        )
    lines.append("  ],")

    evaluation = json.dumps(config["evaluation"], ensure_ascii=False, indent=2)
    evaluation_lines = evaluation.splitlines()
    lines.append('  "evaluation": ' + evaluation_lines[0])
    lines.extend("  " + line for line in evaluation_lines[1:])
    lines.append("}")
    return "\n".join(lines) + "\n"


def _show_unhandled_tk_exception(
    exc_type: type[BaseException],
    exc_value: BaseException,
    exc_traceback,
) -> None:  # noqa: ANN001
    LOGGER.critical(
        "Unhandled Tk callback exception",
        exc_info=(exc_type, exc_value, exc_traceback),
    )
    log_path = current_log_path()
    details = f"{exc_value}"
    if log_path is not None:
        details += f"\n\nDetails were saved to:\n{log_path}"
    try:
        messagebox.showerror("Application error", details)
    except Exception:
        LOGGER.exception("Failed to show Tk exception dialog")


def _to_display_lambda(values):  # noqa: ANN001
    return np.asarray(values, dtype=float) * DISPLAY_SCALE_LAMBDA


def _to_internal_half_lambda(value: float) -> float:
    return value / DISPLAY_SCALE_LAMBDA


def _clip_to_bounds(value: float, low: float, high: float) -> float:
    return float(min(max(value, low), high))


def _axes_boxes_overlap(
    first: tuple[float, float, float, float],
    second: tuple[float, float, float, float],
    margin: float = 0.015,
) -> bool:
    first_left, first_bottom, first_right, first_top = first
    second_left, second_bottom, second_right, second_top = second
    return not (
        first_right + margin < second_left
        or second_right + margin < first_left
        or first_top + margin < second_bottom
        or second_top + margin < first_bottom
    )


def _note_display(note: str) -> tuple[str, str]:
    note_lower = note.lower()
    if "duplicate" in note_lower:
        icon, color = NOTE_STYLES["duplicate"]
    elif "windowing" in note_lower:
        icon, color = NOTE_STYLES["windowing"]
    elif "ambiguity high" in note_lower:
        icon, color = NOTE_STYLES["ambiguity high"]
    elif "ambiguity medium" in note_lower:
        icon, color = NOTE_STYLES["ambiguity medium"]
    else:
        icon, color = NOTE_STYLES["none"]
    return f"{icon} {note}", color


def _configure_pattern_preview_axis(ax) -> None:  # noqa: ANN001
    ax.set_xlim(-180.0, 180.0)
    ax.set_xticks(np.arange(-180.0, 181.0, 30.0))
    ax.set_xticks(np.arange(-180.0, 181.0, 10.0), minor=True)
    ax.grid(True, which="major", alpha=0.32)
    ax.grid(True, which="minor", alpha=0.12)


def _element_prefix(kind: str) -> str:
    if kind == "tx":
        return "Tx"
    if kind == "rx":
        return "Rx"
    raise ValueError(f"Unknown element kind: {kind!r}")


def _max_elements_for_kind(kind: str) -> int:
    if kind == "tx":
        return MAX_TX_COUNT
    if kind == "rx":
        return MAX_RX_COUNT
    raise ValueError(f"Unknown element kind: {kind!r}")


def _snap_to_grid_inside(value: float, low: float, high: float) -> float:
    snapped = snap_to_grid(value)
    if snapped < low:
        snapped = np.ceil(low / GRID_STEP) * GRID_STEP
    elif snapped > high:
        snapped = np.floor(high / GRID_STEP) * GRID_STEP
    return _clip_to_bounds(float(snapped), low, high)


def _axis_limits(
    values: list[float] | np.ndarray,
    minimum_span: float = 20.0,
    padding: float = 6.0,
) -> tuple[float, float]:
    value_array = np.asarray(values, dtype=float)
    low = float(value_array.min())
    high = float(value_array.max())
    if high - low < minimum_span:
        center = (low + high) / 2.0
        low = center - minimum_span / 2.0
        high = center + minimum_span / 2.0
    return low - padding, high + padding


def _fixed_box_equal_limits(
    x_values: list[float] | np.ndarray,
    y_values: list[float] | np.ndarray,
    fig_width_in: float,
    fig_height_in: float,
    x_padding: float = 6.0,
    y_padding: float = 6.0,
    minimum_span: float = 20.0,
) -> tuple[tuple[float, float], tuple[float, float]]:
    """Compute equal-aspect axis limits given a standalone Figure size."""
    x_low, x_high = _axis_limits(x_values, minimum_span=minimum_span, padding=x_padding)
    y_low, y_high = _axis_limits(y_values, minimum_span=minimum_span, padding=y_padding)
    x_span = x_high - x_low
    y_span = y_high - y_low
    box_ratio = fig_width_in / fig_height_in
    data_ratio = x_span / y_span if y_span else box_ratio

    if data_ratio < box_ratio:
        target_x_span = y_span * box_ratio
        center = (x_low + x_high) / 2.0
        x_low = center - target_x_span / 2.0
        x_high = center + target_x_span / 2.0
    elif data_ratio > box_ratio:
        target_y_span = x_span / box_ratio
        center = (y_low + y_high) / 2.0
        y_low = center - target_y_span / 2.0
        y_high = center + target_y_span / 2.0

    return (x_low, x_high), (y_low, y_high)


def _azimuth_status_label(metrics: ArrayMetrics) -> str:
    if metrics.front_radar_status == "Acceptable":
        return "Az Accept"
    return f"Az {metrics.front_radar_status}"


# ═══════════════════════════════════════════════════════════════════════
#  Main GUI class
# ═══════════════════════════════════════════════════════════════════════
class VirtualArrayGui:
    """MIMO antenna virtual-array visualizer.

    Layout (Tkinter grid):
      ┌─────────────┬──────────────┬────────────────┐
      │  Physical   │  Virtual     │                │
      │  Array      │  Array       │  Array         │
      │  (Mpl Fig)  │  (Mpl Fig)   │  Evaluation    │
      ├─────────────┼──────────────┤  (Tkinter)     │
      │  Azimuth    │  Elevation   │                │
      │  Response   │  Response    │                │
      │  (Mpl Fig)  │  (Mpl Fig)   │                │
      ├─────────────┴──────────────┴────────────────┤
      │              Controls (buttons)             │
      └─────────────────────────────────────────────┘
    """

    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title(f"MIMO Array Visualizer v{APP_VERSION}")
        self.root.configure(bg=THEME["bg"])

        # Data state
        self.elements = self._build_elements()
        self.dragging: EditableElement | None = None
        self.drag_bounds: tuple[float, float, float, float] | None = None
        self.drag_axis_limits: tuple[tuple[float, float], tuple[float, float]] | None = None
        self.selected_element: EditableElement | None = None

        # Hover state
        self.physical_hover_annotation = None
        self.virtual_hover_annotation = None
        self.virtual_hover_xy = np.empty((0, 2), dtype=float)
        self.virtual_hover_text: list[str] = []
        self.physical_buttons: list[MplButton] = []
        self.physical_button_callbacks: list[int] = []

        self.element_pattern: ElementPattern | None = None
        self.frequency_mode = tk.StringVar(value=DEFAULT_FREQUENCY_MODE)
        self.pattern_status = tk.StringVar(value="Pattern: isotropic")
        self.status = tk.StringVar(
            value="Drag Tx/Rx points in Physical Array. Release to refresh Virtual Array and Responses."
        )
        self.last_layout_dir = Path("outputs").resolve()
        self.last_pattern_dir = Path.home()
        self._load_local_state()

        # ── Build the grid layout ─────────────────────────────────
        root.grid_rowconfigure(0, weight=1)  # Physical + Virtual
        root.grid_rowconfigure(1, weight=1)  # Az Response + El Response
        root.grid_rowconfigure(2, weight=0)  # Controls
        root.grid_columnconfigure(0, weight=1)
        root.grid_columnconfigure(1, weight=1)
        root.grid_columnconfigure(2, weight=0)  # Evaluation panel
        style = ttk.Style(self.root)
        style.theme_use("clam")

        # ── Refined ttk styles ─────────────────────────────────────
        _f = THEME["font_family"]
        _fm = THEME["font_family_mono"]

        style.configure("TFrame", background=THEME["bg"])
        style.configure("Card.TFrame", background=THEME["card_bg"])
        style.configure("TLabel", background=THEME["bg"], foreground=THEME["text_primary"],
                         font=(_f, THEME["font_size_base"]))
        style.configure("Status.TLabel", background=THEME["status_bar_bg"],
                         foreground=THEME["text_secondary"], font=(_f, THEME["font_size_sm"]))
        style.configure("Muted.TLabel", background=THEME["status_bar_bg"],
                         foreground=THEME["text_muted"], font=(_f, THEME["font_size_sm"]))
        style.configure("Card.TLabel", background=THEME["card_bg"],
                         foreground=THEME["text_primary"], font=(_f, THEME["font_size_base"]))
        style.configure("CardMono.TLabel", background=THEME["card_bg"],
                         foreground=THEME["text_primary"], font=(_fm, THEME["font_size_base"]))
        style.configure("CardHeader.TLabel", background=THEME["card_bg"],
                         foreground=THEME["text_primary"], font=(_fm, THEME["font_size_base"]))
        style.configure("SectionTitle.TLabel", background=THEME["card_bg"],
                         foreground=THEME["text_secondary"], font=(_f, THEME["font_size_sm"]))
        style.configure("Badge.TLabel", background=THEME["card_bg"],
                         foreground=THEME["text_primary"], font=(_f, THEME["font_size_lg"], "bold"))

        style.configure("Accent.TButton", font=(_f, THEME["font_size_base"], "bold"),
                         padding=(12, 6), background=THEME["accent"], foreground="#ffffff")
        style.map("Accent.TButton",
                   background=[("active", THEME["accent_hover"]), ("pressed", THEME["accent_hover"])],
                   foreground=[("active", "#ffffff"), ("pressed", "#ffffff")])
        style.configure("Large.TButton", font=(_f, THEME["font_size_base"]),
                         padding=(10, 5), background=THEME["card_bg"])
        style.map("Large.TButton",
                   background=[("active", THEME["accent_light"]), ("pressed", THEME["accent_light"])])

        style.configure("TLabelframe", background=THEME["card_bg"],
                         foreground=THEME["text_secondary"], font=(_f, THEME["font_size_sm"], "bold"))
        style.configure("TLabelframe.Label", background=THEME["card_bg"],
                         foreground=THEME["text_secondary"], font=(_f, THEME["font_size_sm"], "bold"))

        style.configure("TCombobox", font=(_f, THEME["font_size_base"]))
        style.configure("Status.TFrame", background=THEME["status_bar_bg"])
        style.configure("StatusInner.TFrame", background=THEME["status_bar_bg"])

        # ── Row 0: Physical Array + Virtual Array ─────────────────
        left_frame = ttk.Frame(root, padding=(6, 6, 3, 3))
        left_frame.grid(row=0, column=0, sticky="nsew")
        left_frame.grid_rowconfigure(0, weight=1)
        left_frame.grid_columnconfigure(0, weight=1)

        right_frame = ttk.Frame(root, padding=(3, 6, 3, 3))
        right_frame.grid(row=0, column=1, sticky="nsew")
        right_frame.grid_rowconfigure(0, weight=1)
        right_frame.grid_columnconfigure(0, weight=1)

        # ── Column 2: Array Evaluation (narrow) ──────────────────
        eval_info_frame = ttk.Frame(root, padding=(3, 6, 6, 3))
        eval_info_frame.grid(row=0, column=2, rowspan=2, sticky="nsew")
        eval_info_frame.grid_rowconfigure(0, weight=1)
        eval_info_frame.grid_columnconfigure(0, weight=1)
        self._build_evaluation_panel(eval_info_frame)

        # Physical Array figure
        self.phys_fig = Figure(figsize=(PHYS_FIG_W, PHYS_FIG_H), dpi=FIG_DPI)
        self.phys_fig.set_facecolor(THEME["fig_facecolor"])
        self.physical_ax = self.phys_fig.add_subplot(111)
        self.physical_ax.set_facecolor(THEME["fig_facecolor"])
        self.phys_fig.subplots_adjust(top=0.81, left=0.10, right=0.97, bottom=0.17)
        self._build_physical_figure_controls()
        self.phys_canvas = FigureCanvasTkAgg(self.phys_fig, master=left_frame)
        phys_widget = self.phys_canvas.get_tk_widget()
        phys_widget.grid(row=0, column=0, sticky="nsew")

        # Virtual Array figure
        self.virt_fig = Figure(figsize=(VIRT_FIG_W, VIRT_FIG_H), dpi=FIG_DPI)
        self.virt_fig.set_facecolor(THEME["fig_facecolor"])
        self.virtual_ax = self.virt_fig.add_subplot(111)
        self.virtual_ax.set_facecolor(THEME["fig_facecolor"])
        self.virt_canvas = FigureCanvasTkAgg(self.virt_fig, master=right_frame)
        virt_widget = self.virt_canvas.get_tk_widget()
        virt_widget.grid(row=0, column=0, sticky="nsew")

        # ── Row 1: Azimuth Response + Elevation Response ──────────
        self.az_chart = self._build_response_chart(
            row=1, col=0, padding=(6, 3, 3, 6)
        )
        self.el_chart = self._build_response_chart(
            row=1, col=1, padding=(3, 3, 6, 6)
        )

        # ── Row 2: Controls ───────────────────────────────────────
        controls_outer = ttk.Frame(root, style="Status.TFrame")
        controls_outer.grid(row=2, column=0, columnspan=3, sticky="ew")
        controls = ttk.Frame(controls_outer, style="Status.TFrame", padding=(10, 8))
        controls.pack(fill=tk.X)

        ttk.Button(
            controls,
            text="📥 Import Layout",
            command=self.import_layout_config,
            style="Accent.TButton",
        ).pack(side=tk.LEFT)
        ttk.Button(
            controls,
            text="📤 Export Layout",
            command=self.export_layout_config,
            style="Large.TButton",
        ).pack(side=tk.LEFT, padx=(6, 0))

        ttk.Separator(controls, orient="vertical").pack(side=tk.LEFT, fill=tk.Y, padx=12)

        ttk.Label(
            controls, text="Frequency:", style="Status.TLabel"
        ).pack(side=tk.LEFT, padx=(0, 4))
        frequency_combo = ttk.Combobox(
            controls,
            textvariable=self.frequency_mode,
            values=list(FREQUENCY_MODES_MM),
            width=8,
            state="readonly",
        )
        frequency_combo.pack(side=tk.LEFT)
        frequency_combo.bind("<<ComboboxSelected>>", self.on_frequency_changed)

        ttk.Separator(controls, orient="vertical").pack(side=tk.LEFT, fill=tk.Y, padx=12)

        ttk.Label(
            controls,
            textvariable=self.pattern_status,
            style="Muted.TLabel",
        ).pack(side=tk.LEFT)
        ttk.Label(
            controls,
            textvariable=self.status,
            style="Status.TLabel",
        ).pack(side=tk.LEFT, padx=(12, 0))

        # ── Event bindings ────────────────────────────────────────
        # Physical array: press, motion, release (drag + hover)
        self.phys_canvas.mpl_connect("button_press_event", self.on_press)
        self.phys_canvas.mpl_connect("motion_notify_event", self.on_motion)
        self.phys_canvas.mpl_connect("button_release_event", self.on_release)
        # Virtual array: hover only
        self.virt_canvas.mpl_connect("motion_notify_event", self.on_motion)
        # Az/El response: hover only
        for chart in (self.az_chart, self.el_chart):
            chart.canvas.mpl_connect("motion_notify_event", self.on_motion)

        self.root.bind("<Left>", self.on_arrow_key)
        self.root.bind("<Right>", self.on_arrow_key)
        self.root.bind("<Up>", self.on_arrow_key)
        self.root.bind("<Down>", self.on_arrow_key)
        self.root.bind("<Delete>", self.on_delete_key)

        self.generate_virtual_array()

    # ── Response chart helpers ──────────────────────────────────────────

    def _build_response_chart(
        self, row: int, col: int, padding: tuple[int, int, int, int]
    ) -> ResponseChart:
        """Create a response chart (Az or El) and embed it in the grid."""
        frame = ttk.Frame(self.root, padding=padding)
        frame.grid(row=row, column=col, sticky="nsew")
        frame.grid_rowconfigure(0, weight=1)
        frame.grid_columnconfigure(0, weight=1)

        fig = Figure(figsize=(RESPONSE_FIG_W, RESPONSE_FIG_H), dpi=FIG_DPI)
        fig.set_facecolor(THEME["fig_facecolor"])
        ax = fig.add_subplot(111)
        ax.set_facecolor(THEME["fig_facecolor"])
        fig.subplots_adjust(top=0.82, left=0.13, right=0.97, bottom=0.18)
        canvas = FigureCanvasTkAgg(fig, master=frame)
        canvas.get_tk_widget().grid(row=0, column=0, sticky="nsew")

        chart = ResponseChart(fig=fig, ax=ax, canvas=canvas)
        self._build_figure_buttons(
            fig,
            (
                ("Load", [0.62, 0.84, 0.12, 0.055], self.import_element_pattern),
                ("Clear", [0.76, 0.84, 0.12, 0.055], self.clear_element_pattern),
            ),
            chart.buttons,
            chart.button_callbacks,
        )
        return chart

    def _build_figure_buttons(
        self,
        fig: Figure,
        button_specs: tuple[tuple[str, list[float], callable], ...],
        buttons_list: list[MplButton],
        callbacks_list: list[int],
    ) -> None:
        """Add MplButton widgets to *fig* from *button_specs*."""
        for label, rect, callback in button_specs:
            button_ax = fig.add_axes(rect)
            button = MplButton(
                button_ax, label,
                color=THEME["mpl_btn_bg"],
                hovercolor=THEME["mpl_btn_hover"],
            )
            button.label.set_fontsize(8.5)
            button.label.set_color(THEME["mpl_btn_text"])
            button.label.set_fontweight("bold")
            button.label.set_horizontalalignment("center")
            button.label.set_verticalalignment("center")
            cid = button.on_clicked(lambda _event, action=callback: action())
            buttons_list.append(button)
            callbacks_list.append(cid)

    # ── Tkinter Evaluation Panel ──────────────────────────────────────

    def _build_evaluation_panel(self, parent: ttk.Frame) -> None:
        """Build the Array Evaluation card using Tkinter native widgets."""
        _f = THEME["font_family"]
        _fm = THEME["font_family_mono"]
        _sm = THEME["font_size_sm"]
        _base = THEME["font_size_base"]

        self.eval_frame = ttk.LabelFrame(
            parent, text="  ARRAY EVALUATION  ", padding=(8, 6)
        )
        self.eval_frame.configure(style="TLabelframe")
        self.eval_frame.grid(row=0, column=0, sticky="nsew")

        # Header row: application + frequency
        header = ttk.Frame(self.eval_frame, style="Card.TFrame")
        header.pack(fill=tk.X, pady=(0, 6))
        self.eval_app_label = ttk.Label(
            header, text="Front Radar", style="CardHeader.TLabel"
        )
        self.eval_app_label.pack(side=tk.LEFT)
        self.eval_freq_label = ttk.Label(
            header, text=DEFAULT_FREQUENCY_MODE, style="CardHeader.TLabel"
        )
        self.eval_freq_label.pack(side=tk.RIGHT)

        # Status badge row
        badge_row = ttk.Frame(self.eval_frame, style="Card.TFrame")
        badge_row.pack(fill=tk.X, pady=(0, 6))
        self.status_canvas = tk.Canvas(
            badge_row, width=16, height=16, highlightthickness=0,
            bg=THEME["card_bg"]
        )
        self.status_canvas.pack(side=tk.LEFT, padx=(0, 6))
        self.status_dot = self.status_canvas.create_oval(
            1, 1, 15, 15, fill="#2e7d32", outline=""
        )
        self.status_text = ttk.Label(
            badge_row, text="Az Good", style="Badge.TLabel"
        )
        self.status_text.pack(side=tk.LEFT)

        # Compact summary line
        summary_frame = ttk.Frame(self.eval_frame, style="Card.TFrame")
        summary_frame.pack(fill=tk.X, pady=(0, 6))
        self.summary_label = ttk.Label(
            summary_frame, text="", style="Card.TLabel",
            font=(_fm, _sm), foreground=THEME["text_secondary"],
        )
        self.summary_label.pack(fill=tk.X)

        # PRIMARY section
        primary_frame = ttk.LabelFrame(
            self.eval_frame, text="  PRIMARY  ", padding=(6, 4), style="TLabelframe"
        )
        primary_frame.pack(fill=tk.X, pady=(0, 4))
        primary_frame.grid_columnconfigure(0, weight=1)

        primary_labels = [
            "Az aperture", "Az resolution", "Az -3dB BW", "Az null BW",
            "Az PSL", "First sidelobe", "Az grating lobe", "Az ISLR",
            "Virtual util.",
        ]
        secondary_labels = [
            "El aperture", "El resolution", "El -3dB BW", "El PSL",
            "2D worst PSL", "2D PSL loc", "El ambiguity",
        ]

        self.primary_value_labels: dict[str, ttk.Label] = {}
        self.secondary_value_labels: dict[str, ttk.Label] = {}

        for i, key in enumerate(primary_labels):
            row_bg = THEME["card_bg"] if i % 2 == 0 else "#f8f7f5"
            row_frame = tk.Frame(primary_frame, bg=row_bg)
            row_frame.grid(row=i, column=0, sticky="ew")
            ttk.Label(
                row_frame, text=key, font=(_fm, _sm), background=row_bg,
                foreground=THEME["text_secondary"],
            ).pack(side=tk.LEFT, padx=(2, 8))
            val = ttk.Label(
                row_frame, text="", font=(_fm, _sm), background=row_bg,
                foreground=THEME["text_primary"], anchor="e",
            )
            val.pack(side=tk.RIGHT, padx=(8, 2))
            self.primary_value_labels[key] = val

        # SECONDARY section
        secondary_frame = ttk.LabelFrame(
            self.eval_frame, text="  SECONDARY  ", padding=(6, 4), style="TLabelframe"
        )
        secondary_frame.pack(fill=tk.X, pady=(0, 4))
        secondary_frame.grid_columnconfigure(0, weight=1)

        for i, key in enumerate(secondary_labels):
            row_bg = THEME["card_bg"] if i % 2 == 0 else "#f8f7f5"
            row_frame = tk.Frame(secondary_frame, bg=row_bg)
            row_frame.grid(row=i, column=0, sticky="ew")
            ttk.Label(
                row_frame, text=key, font=(_fm, _sm), background=row_bg,
                foreground=THEME["text_secondary"],
            ).pack(side=tk.LEFT, padx=(2, 8))
            val = ttk.Label(
                row_frame, text="", font=(_fm, _sm), background=row_bg,
                foreground=THEME["text_primary"], anchor="e",
            )
            val.pack(side=tk.RIGHT, padx=(8, 2))
            self.secondary_value_labels[key] = val

        # NOTES section
        self.notes_frame = ttk.Frame(self.eval_frame, style="Card.TFrame")
        self.notes_frame.pack(fill=tk.X, pady=(4, 0))
        ttk.Label(
            self.notes_frame, text="NOTES", style="SectionTitle.TLabel"
        ).pack(anchor="w")
        self.notes_items_frame = ttk.Frame(self.notes_frame, style="Card.TFrame")
        self.notes_items_frame.pack(fill=tk.X, pady=(2, 0))

    def _update_evaluation_panel(self, metrics: ArrayMetrics) -> None:
        """Update the Tkinter evaluation panel with current metrics."""
        utilization = (
            metrics.unique_count / metrics.virtual_count if metrics.virtual_count else 0.0
        )
        grade_color = PSL_COLORS[metrics.front_radar_status]
        status_text = _azimuth_status_label(metrics)

        # Update status badge
        self.status_canvas.itemconfig(self.status_dot, fill=grade_color)
        self.status_text.configure(text=status_text, foreground=grade_color)

        # Update header
        self.eval_freq_label.configure(text=f"Frequency: {self.frequency_mode.get()}")

        # PRIMARY values
        values = {
            "Az aperture": _format_mm(self.aperture_mm(metrics.x_aperture)),
            "Az resolution": _format_float(metrics.azimuth_resolution, "°"),
            "Az -3dB BW": _format_float(metrics.azimuth_3db_beamwidth, "°"),
            "Az null BW": _format_float(metrics.azimuth_null_beamwidth, "°"),
            "Az PSL": f"{metrics.azimuth_psl_db:.2f} dB",
            "First sidelobe": _format_db_at_az(
                metrics.azimuth_first_sidelobe_db, metrics.azimuth_first_sidelobe_angle
            ),
            "Az grating lobe": _format_db_at_az(
                metrics.azimuth_grating_lobe_db, metrics.azimuth_grating_lobe_angle
            ),
            "Az ISLR": _format_db(metrics.azimuth_islr_db),
            "Virtual util.": f"{metrics.unique_count}/{metrics.virtual_count} ({utilization:.0%})",
        }
        for key, val in values.items():
            if key in self.primary_value_labels:
                self.primary_value_labels[key].configure(text=val)

        # SECONDARY values
        sec_values = {
            "El aperture": _format_mm(self.aperture_mm(metrics.y_aperture)),
            "El resolution": _format_float(metrics.elevation_resolution, "°"),
            "El -3dB BW": _format_float(metrics.elevation_3db_beamwidth, "°"),
            "El PSL": f"{metrics.elevation_psl_db:.2f} dB",
            "2D worst PSL": f"{metrics.psl_db:.2f} dB",
            "2D PSL loc": f"{metrics.sidelobe_azimuth:.1f}°, {metrics.sidelobe_elevation:.1f}°",
            "El ambiguity": metrics.elevation_ambiguity_level,
        }
        for key, val in sec_values.items():
            if key in self.secondary_value_labels:
                self.secondary_value_labels[key].configure(text=val)

        # NOTES
        self._update_notes_panel(self._notes_parts(metrics))

        # Compact summary: Tx/Rx | frequency | aperture
        freq_label = self.frequency_mode.get()
        wavelength_mm = FREQUENCY_MODES_MM.get(freq_label, 0.0)
        x_mm = self.aperture_mm(metrics.x_aperture)
        y_mm = self.aperture_mm(metrics.y_aperture)
        self.summary_label.configure(
            text=(
                f"{metrics.tx_count}Tx × {metrics.rx_count}Rx  ·  "
                f"{freq_label} (λ={wavelength_mm:.3f} mm)  ·  "
                f"{_format_mm(x_mm)} × {_format_mm(y_mm)}"
            )
        )

    # ── Array data ────────────────────────────────────────────────────

    def wavelength_mm(self) -> float:
        mode = self.frequency_mode.get()
        return FREQUENCY_MODES_MM.get(mode, FREQUENCY_MODES_MM[DEFAULT_FREQUENCY_MODE])

    def half_wavelength_mm(self) -> float:
        return self.wavelength_mm() / 2.0

    def aperture_mm(self, aperture_half_lambda: float) -> float:
        return aperture_half_lambda * self.half_wavelength_mm()

    def _build_elements(self) -> list[EditableElement]:
        array = build_array()
        elements: list[EditableElement] = []
        elements.extend(
            EditableElement(kind="tx", index=i, name=point.name, x=point.x, y=point.y)
            for i, point in enumerate(array.tx)
        )
        elements.extend(
            EditableElement(kind="rx", index=i, name=point.name, x=point.x, y=point.y)
            for i, point in enumerate(array.rx)
        )
        return elements

    def current_array(self) -> AntennaArray:
        tx = [
            ArrayPoint(name=element.name, x=element.x, y=element.y)
            for element in self.elements
            if element.kind == "tx"
        ]
        rx = [
            ArrayPoint(name=element.name, x=element.x, y=element.y)
            for element in self.elements
            if element.kind == "rx"
        ]
        return AntennaArray(tx=tx, rx=rx)

    def _elements_of_kind(self, kind: str) -> list[EditableElement]:
        return [element for element in self.elements if element.kind == kind]

    def _renumber_elements(self) -> None:
        selected = self.selected_element
        renumbered: list[EditableElement] = []
        for kind in ("tx", "rx"):
            prefix = _element_prefix(kind)
            for index, element in enumerate(self._elements_of_kind(kind)):
                element.index = index
                element.name = f"{prefix}{index + 1}"
                renumbered.append(element)
        self.elements = renumbered
        if any(element is selected for element in self.elements):
            self.selected_element = selected
        else:
            self.selected_element = None

    def _next_element_position(self, kind: str) -> tuple[float, float]:
        same_kind = self._elements_of_kind(kind)
        if not same_kind:
            return (0.0, 0.0 if kind == "tx" else -10.0)

        anchor = (
            self.selected_element
            if self.selected_element is not None and self.selected_element.kind == kind
            else max(same_kind, key=lambda element: (element.x, element.y))
        )
        occupied = {(element.x, element.y) for element in self.elements}
        x = snap_to_grid(anchor.x + 2 * GRID_STEP)
        y = snap_to_grid(anchor.y)
        while (x, y) in occupied:
            x = snap_to_grid(x + 2 * GRID_STEP)
        return x, y

    def add_tx_element(self) -> None:
        self._add_element("tx")

    def add_rx_element(self) -> None:
        self._add_element("rx")

    def _add_element(self, kind: str) -> None:
        current_count = len(self._elements_of_kind(kind))
        max_count = _max_elements_for_kind(kind)
        prefix = _element_prefix(kind)
        if current_count >= max_count:
            self.status.set(f"{prefix} limit reached ({max_count}).")
            messagebox.showinfo("Antenna limit", f"{prefix} count is limited to {max_count}.")
            return

        x, y = self._next_element_position(kind)
        element = EditableElement(
            kind=kind,
            index=current_count,
            name=f"{prefix}{current_count + 1}",
            x=x,
            y=y,
        )
        self.elements.append(element)
        self.selected_element = element
        self._renumber_elements()
        self.dragging = None
        self.drag_bounds = None
        self.drag_axis_limits = None
        self.generate_virtual_array()
        self.status.set(
            f"Added {element.name} | "
            f"x={element.x * DISPLAY_SCALE_LAMBDA:g} λ | "
            f"y={element.y * DISPLAY_SCALE_LAMBDA:g} λ"
        )

    def _build_physical_figure_controls(self) -> None:
        self._build_figure_buttons(
            self.phys_fig,
            (
                ("+Tx", [0.70, 0.838, 0.07, 0.055], self.add_tx_element),
                ("+Rx", [0.775, 0.838, 0.07, 0.055], self.add_rx_element),
                ("Delete", [0.85, 0.838, 0.105, 0.055], self.delete_selected_element),
            ),
            self.physical_buttons,
            self.physical_button_callbacks,
        )

    def delete_selected_element(self) -> None:
        if self.selected_element is None:
            self.status.set("No antenna selected. Click a Tx/Rx element first.")
            return

        element = self.selected_element
        same_kind_count = len(self._elements_of_kind(element.kind))
        if same_kind_count <= 1:
            prefix = _element_prefix(element.kind)
            self.status.set(f"Cannot delete the last {prefix} element.")
            messagebox.showinfo(
                "Antenna limit",
                f"At least one {prefix} element is required for analysis.",
            )
            return

        deleted_name = element.name
        self.elements = [candidate for candidate in self.elements if candidate is not element]
        self.selected_element = None
        self.dragging = None
        self.drag_bounds = None
        self.drag_axis_limits = None
        self._renumber_elements()
        self.generate_virtual_array()
        self.status.set(f"Deleted {deleted_name}. Antenna numbering updated.")

    # ── Button handlers ───────────────────────────────────────────────

    def on_frequency_changed(self, _event=None) -> None:  # noqa: ANN001
        self.generate_virtual_array()

    def import_element_pattern(self) -> None:
        filename = filedialog.askopenfilename(
            title="Import element pattern",
            initialdir=str(self.last_pattern_dir),
            filetypes=[
                ("Pattern CSV/TSV", "*.csv *.tsv"),
                ("CSV files", "*.csv"),
                ("TSV files", "*.tsv"),
                ("All files", "*.*"),
            ],
        )
        if not filename:
            return
        self.last_pattern_dir = Path(filename).parent

        try:
            pattern = load_element_pattern(filename)
        except Exception as exc:
            LOGGER.exception("Import element pattern failed: %s", filename)
            messagebox.showerror("Import element pattern failed", str(exc))
            return

        confirmed_pattern = self._confirm_element_pattern_import(pattern)
        if confirmed_pattern is None:
            self.status.set("Element pattern import canceled.")
            return

        pattern = confirmed_pattern
        self.element_pattern = pattern
        self.pattern_status.set(f"Pattern: {pattern.name}")
        LOGGER.info("Imported element pattern from %s", filename)
        self.generate_virtual_array()
        self.status.set(f"Element pattern loaded: {pattern.name}")

    def clear_element_pattern(self) -> None:
        if self.element_pattern is None:
            self.status.set("Element pattern already isotropic.")
            return
        LOGGER.info("Cleared element pattern: %s", self.element_pattern.source_path)
        self.element_pattern = None
        self.pattern_status.set("Pattern: isotropic")
        self.generate_virtual_array()
        self.status.set("Element pattern cleared. Using isotropic elements.")

    def _confirm_element_pattern_import(
        self, pattern: ElementPattern
    ) -> ElementPattern | None:
        dialog = tk.Toplevel(self.root)
        dialog.title("Confirm Element Pattern")
        dialog.transient(self.root)
        dialog.grab_set()

        title = ttk.Label(
            dialog,
            text=f"{pattern.name}",
            font=("Segoe UI", 10, "bold"),
        )
        title.pack(fill=tk.X, padx=10, pady=(8, 2))
        subtitle = ttk.Label(
            dialog,
            text="",
            font=("Segoe UI", 9),
        )
        subtitle.pack(fill=tk.X, padx=10, pady=(0, 6))
        metrics_frame = ttk.Frame(dialog)
        metrics_frame.pack(fill=tk.X, padx=10, pady=(0, 6))
        horizontal_metrics_label = ttk.Label(
            metrics_frame,
            text="",
            font=("Consolas", 9),
            foreground="#2f6fbb",
        )
        horizontal_metrics_label.pack(anchor="w")
        elevation_metrics_label = ttk.Label(
            metrics_frame,
            text="",
            font=("Consolas", 9),
            foreground="#7b1fa2",
        )
        elevation_metrics_label.pack(anchor="w")

        fig = Figure(figsize=(7.8, 5.0), dpi=FIG_DPI)
        horizontal_ax = fig.add_subplot(211)
        elevation_ax = fig.add_subplot(212)

        canvas = FigureCanvasTkAgg(fig, master=dialog)
        canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 8))

        state: dict[str, ElementPattern | None] = {"pattern": pattern, "confirmed": None}

        def redraw_preview() -> None:
            current = state["pattern"]
            if current is None:
                return
            subtitle.configure(
                text=f"Angle: {current.angle_column} | H: {current.horizontal_column}"
                + (f" | V: {current.elevation_column}" if current.elevation_column else "")
            )

            horizontal_ax.clear()
            elevation_ax.clear()
            horizontal_ax.plot(
                current.angles_deg,
                current.horizontal_gain_db,
                color="#2f6fbb",
                linewidth=1.6,
            )
            horizontal_metrics = format_pattern_cut_metrics(
                pattern_cut_metrics(current.angles_deg, current.horizontal_gain_db)
            )
            horizontal_metrics_label.configure(text=f"Horizontal: {horizontal_metrics}")
            horizontal_ax.set_title("Horizontal pattern", loc="left")
            horizontal_ax.set_ylabel("Gain (dB)")
            _configure_pattern_preview_axis(horizontal_ax)
            horizontal_ax.grid(True, alpha=0.3)

            if current.elevation_gain_db is not None:
                elevation_ax.plot(
                    current.angles_deg,
                    current.elevation_gain_db,
                    color="#7b1fa2",
                    linewidth=1.6,
                )
                elevation_metrics = format_pattern_cut_metrics(
                    pattern_cut_metrics(current.angles_deg, current.elevation_gain_db)
                )
                elevation_metrics_label.configure(text=f"Elevation: {elevation_metrics}")
            else:
                elevation_ax.text(
                    0.5,
                    0.5,
                    "No separate elevation column. Horizontal pattern will be reused.",
                    transform=elevation_ax.transAxes,
                    ha="center",
                    va="center",
                    fontsize=10,
                )
                elevation_metrics_label.configure(
                    text="Elevation: reuses horizontal pattern"
                )
            elevation_ax.set_title("Elevation pattern", loc="left")
            elevation_ax.set_xlabel("Angle (deg)")
            elevation_ax.set_ylabel("Gain (dB)")
            _configure_pattern_preview_axis(elevation_ax)
            elevation_ax.grid(True, alpha=0.3)
            fig.tight_layout()
            canvas.draw_idle()

        redraw_preview()

        def confirm() -> None:
            state["confirmed"] = state["pattern"]
            dialog.destroy()

        def cancel() -> None:
            state["confirmed"] = None
            dialog.destroy()

        def swap_axes() -> None:
            current = state["pattern"]
            if current is None:
                return
            state["pattern"] = current.swapped_axes()
            redraw_preview()

        button_row = ttk.Frame(dialog)
        button_row.pack(fill=tk.X, padx=10, pady=(0, 10))
        ttk.Button(button_row, text="Import", command=confirm).pack(side=tk.RIGHT)
        ttk.Button(button_row, text="Cancel", command=cancel).pack(
            side=tk.RIGHT, padx=(0, 8)
        )
        swap_button = ttk.Button(button_row, text="Swap H/V", command=swap_axes)
        swap_button.pack(side=tk.LEFT)
        if pattern.elevation_gain_db is None:
            swap_button.configure(state=tk.DISABLED)
        dialog.protocol("WM_DELETE_WINDOW", cancel)
        dialog.wait_window()
        return state["confirmed"]

    def export_layout_config(self) -> None:
        default_path = Path("outputs") / "antenna_layout.json"
        default_path.parent.mkdir(exist_ok=True)
        filename = filedialog.asksaveasfilename(
            title="Export antenna layout",
            initialdir=str(self.last_layout_dir),
            initialfile=default_path.name,
            defaultextension=".json",
            filetypes=[("Antenna layout JSON", "*.json")],
        )
        if not filename:
            return
        self.last_layout_dir = Path(filename).parent
        config = self._layout_config()
        with open(filename, "w", encoding="utf-8") as file:
            file.write(_layout_config_to_json(config))
        LOGGER.info("Exported layout config to %s", filename)
        self.status.set(f"Exported layout: {filename}")

    def import_layout_config(self) -> None:
        filename = filedialog.askopenfilename(
            title="Import antenna layout",
            initialdir=str(self.last_layout_dir),
            filetypes=[("Antenna layout JSON", "*.json"), ("All files", "*.*")],
        )
        if not filename:
            return
        self.last_layout_dir = Path(filename).parent
        try:
            with open(filename, "r", encoding="utf-8") as file:
                config = json.load(file)
            self.elements = self._elements_from_layout_config(config)
        except Exception as exc:
            LOGGER.exception("Import layout failed: %s", filename)
            messagebox.showerror("Import layout failed", str(exc))
            return

        self.dragging = None
        self.drag_bounds = None
        self.drag_axis_limits = None
        self.selected_element = None
        self.generate_virtual_array()
        tx = [element for element in self.elements if element.kind == "tx"]
        rx = [element for element in self.elements if element.kind == "rx"]
        x_values = [element.x * DISPLAY_SCALE_LAMBDA for element in self.elements]
        y_values = [element.y * DISPLAY_SCALE_LAMBDA for element in self.elements]
        self.status.set(
            f"Imported: {Path(filename).name} | "
            f"{tx[0].name}=({tx[0].x * DISPLAY_SCALE_LAMBDA:g},{tx[0].y * DISPLAY_SCALE_LAMBDA:g}) λ | "
            f"{rx[0].name}=({rx[0].x * DISPLAY_SCALE_LAMBDA:g},{rx[0].y * DISPLAY_SCALE_LAMBDA:g}) λ | "
            f"x {min(x_values):g}..{max(x_values):g} λ, y {min(y_values):g}..{max(y_values):g} λ"
        )
        LOGGER.info("Imported layout config from %s", filename)

    # ── Layout config I/O ─────────────────────────────────────────────

    def _layout_config(self) -> dict[str, object]:
        config = self._layout_coordinates_config()
        metrics = self._metrics_for_export()
        config["evaluation"] = self._layout_evaluation(metrics)
        return config

    def _layout_coordinates_config(self) -> dict[str, object]:
        tx = [element for element in self.elements if element.kind == "tx"]
        rx = [element for element in self.elements if element.kind == "rx"]
        return {
            "version": LAYOUT_CONFIG_VERSION,
            "unit": LAYOUT_UNIT,
            "tx": [
                {
                    "name": element.name,
                    "x": _json_number(element.x * DISPLAY_SCALE_LAMBDA, digits=9),
                    "y": _json_number(element.y * DISPLAY_SCALE_LAMBDA, digits=9),
                }
                for element in tx
            ],
            "rx": [
                {
                    "name": element.name,
                    "x": _json_number(element.x * DISPLAY_SCALE_LAMBDA, digits=9),
                    "y": _json_number(element.y * DISPLAY_SCALE_LAMBDA, digits=9),
                }
                for element in rx
            ],
        }

    def _elements_from_layout_config(self, config: object) -> list[EditableElement]:
        if not isinstance(config, dict):
            raise ValueError("Layout config must be a JSON object.")
        if config.get("version") != LAYOUT_CONFIG_VERSION:
            raise ValueError(f"Unsupported layout version: {config.get('version')!r}.")
        unit = config.get("unit")
        if unit not in LAYOUT_UNITS_LAMBDA | LEGACY_LAYOUT_UNITS_HALF_LAMBDA:
            raise ValueError("Layout unit must be 'lambda'.")
        coordinates_are_lambda = unit in LAYOUT_UNITS_LAMBDA

        elements: list[EditableElement] = []
        for kind in ("tx", "rx"):
            raw_points = config.get(kind)
            if not isinstance(raw_points, list) or not raw_points:
                raise ValueError(f"Layout field '{kind}' must be a non-empty list.")
            max_count = _max_elements_for_kind(kind)
            if len(raw_points) > max_count:
                prefix = _element_prefix(kind)
                raise ValueError(f"Layout has {len(raw_points)} {prefix} elements; maximum is {max_count}.")
            for index, raw_point in enumerate(raw_points):
                if not isinstance(raw_point, dict):
                    raise ValueError(f"{kind}[{index}] must be an object.")
                try:
                    name = f"{_element_prefix(kind)}{index + 1}"
                    raw_x = float(raw_point["x"])
                    raw_y = float(raw_point["y"])
                    if coordinates_are_lambda:
                        raw_x = _to_internal_half_lambda(raw_x)
                        raw_y = _to_internal_half_lambda(raw_y)
                    x = snap_to_grid(raw_x)
                    y = snap_to_grid(raw_y)
                except KeyError as exc:
                    raise ValueError(f"{kind}[{index}] is missing coordinate {exc}.") from exc
                except (TypeError, ValueError) as exc:
                    raise ValueError(f"{kind}[{index}] has invalid coordinates.") from exc
                elements.append(EditableElement(kind=kind, index=index, name=name, x=x, y=y))
        return elements

    def _metrics_for_export(self) -> ArrayMetrics:
        array = self.current_array()
        unique, counts = array.unique_virtual_xy(decimals=ROUND_DECIMALS)
        _af_db, _azimuths, _elevations, metrics = calculate_metrics_and_psf(
            array,
            unique,
            counts,
            tx_pattern=self.element_pattern,
            rx_pattern=self.element_pattern,
        )
        return metrics

    def _layout_evaluation(self, metrics: ArrayMetrics) -> dict[str, object]:
        utilization = metrics.unique_count / metrics.virtual_count if metrics.virtual_count else 0.0
        return {
            "frequency_mode": self.frequency_mode.get(),
            "virtual_utilization": {
                "unique_points": metrics.unique_count,
                "virtual_channels": metrics.virtual_count,
                "ratio": _json_number(utilization, digits=6),
                "duplicate_points": metrics.duplicate_excess,
            },
            "az_aperture_mm": _json_number(self.aperture_mm(metrics.x_aperture), digits=3),
            "az_aperture_lambda": _json_number(metrics.x_aperture * DISPLAY_SCALE_LAMBDA, digits=9),
            "az_resolution_deg": _json_number(metrics.azimuth_resolution, digits=3),
            "az_3db_bw_deg": _json_number(metrics.azimuth_3db_beamwidth, digits=3),
            "az_psl_db": _json_number(metrics.azimuth_psl_db, digits=3),
            "first_sidelobe": {
                "level_db": _json_number(metrics.azimuth_first_sidelobe_db, digits=3),
                "az_deg": _json_number(metrics.azimuth_first_sidelobe_angle, digits=3),
            },
            "az_grating_lobe": {
                "level_db": _json_number(metrics.azimuth_grating_lobe_db, digits=3),
                "az_deg": _json_number(metrics.azimuth_grating_lobe_angle, digits=3),
            },
            "az_islr_db": _json_number(metrics.azimuth_islr_db, digits=3),
            "el_3db_bw_deg": _json_number(metrics.elevation_3db_beamwidth, digits=3),
            "el_psl_db": _json_number(metrics.elevation_psl_db, digits=3),
            "psl_2d_worst_db": _json_number(metrics.psl_db, digits=3),
            "psl_2d_location_deg": {
                "az": _json_number(metrics.sidelobe_azimuth, digits=3),
                "el": _json_number(metrics.sidelobe_elevation, digits=3),
            },
            "element_pattern": self._element_pattern_export_info(),
            "notes": self._notes_parts(metrics),
        }

    # ── Main generation pipeline ──────────────────────────────────────

    def generate_virtual_array(self) -> None:
        array = self.current_array()
        unique, counts = array.unique_virtual_xy(decimals=ROUND_DECIMALS)
        pair_map = self._build_virtual_pair_map(array)
        af_db, azimuths, elevations, metrics = calculate_metrics_and_psf(
            array,
            unique,
            counts,
            tx_pattern=self.element_pattern,
            rx_pattern=self.element_pattern,
        )

        self._draw_physical_array()
        self._draw_virtual_array(unique, counts, pair_map, metrics)
        self._update_evaluation_panel(metrics)
        self._draw_response(RESPONSE_MODE_AZIMUTH, self.az_chart, af_db, azimuths, elevations, metrics)
        self._draw_response(RESPONSE_MODE_ELEVATION, self.el_chart, af_db, azimuths, elevations, metrics)

        self.status.set("Ready")
        self.phys_canvas.draw_idle()
        self.virt_canvas.draw_idle()
        self.az_chart.canvas.draw_idle()
        self.el_chart.canvas.draw_idle()

    def _build_virtual_pair_map(
        self, array: AntennaArray
    ) -> dict[tuple[float, float], list[str]]:
        pair_map: dict[tuple[float, float], list[str]] = defaultdict(list)
        for point in array.virtual_points():
            key = (round(point.x, ROUND_DECIMALS), round(point.y, ROUND_DECIMALS))
            pair_map[key].append(f"{point.tx_name}-{point.rx_name}")
        return pair_map

    # ── Plot drawing ──────────────────────────────────────────────────

    def _draw_physical_array(self) -> None:
        self.physical_ax.clear()
        tx = [element for element in self.elements if element.kind == "tx"]
        rx = [element for element in self.elements if element.kind == "rx"]

        self.physical_ax.scatter(
            _to_display_lambda([element.x for element in tx]),
            _to_display_lambda([element.y for element in tx]),
            marker="D",
            s=62,
            facecolors="none",
            edgecolors="#b04f48",
            linewidths=1.7,
            label="Tx",
        )
        self.physical_ax.scatter(
            _to_display_lambda([element.x for element in rx]),
            _to_display_lambda([element.y for element in rx]),
            marker="*",
            s=112,
            color="#335c9e",
            label="Rx",
        )
        if self.selected_element is not None:
            self.physical_ax.scatter(
                _to_display_lambda([self.selected_element.x]),
                _to_display_lambda([self.selected_element.y]),
                marker="o",
                s=280,
                facecolors="none",
                edgecolors="#ffcc00",
                linewidths=2.4,
                zorder=5,
                label="_nolegend_",
            )
        for element in self.elements:
            if self.selected_element is element:
                self.physical_ax.annotate(
                    element.name,
                    xy=(
                        element.x * DISPLAY_SCALE_LAMBDA,
                        element.y * DISPLAY_SCALE_LAMBDA,
                    ),
                    xytext=(7, 16),
                    textcoords="offset points",
                    fontsize=8.8,
                    ha="left",
                    va="bottom",
                )
            else:
                dy = 1.0 if element.kind == "tx" else -1.15
                self.physical_ax.text(
                    element.x * DISPLAY_SCALE_LAMBDA,
                    element.y * DISPLAY_SCALE_LAMBDA + dy,
                    element.name,
                    fontsize=8.8,
                    ha="center",
                    va="center",
                )

        self.physical_ax.set_title(
            "Physical Array", fontsize=TITLE_SIZE, pad=6, y=1.02, loc="left",
            color=THEME["text_primary"], fontweight="bold",
        )
        self.physical_ax.set_xlabel("x (λ)", color=THEME["text_secondary"])
        self.physical_ax.set_ylabel("y (λ)", color=THEME["text_secondary"])
        self.physical_ax.tick_params(colors=THEME["text_secondary"], labelsize=8)
        if self.drag_axis_limits is not None:
            x_limits, y_limits = self.drag_axis_limits
        else:
            physical_x = _to_display_lambda([element.x for element in self.elements])
            physical_y = _to_display_lambda([element.y for element in self.elements])
            x_limits = _axis_limits(physical_x, minimum_span=5.0, padding=3.0)
            y_limits = _axis_limits(physical_y, minimum_span=5.0, padding=3.0)
        self.physical_ax.set_xlim(*x_limits)
        self.physical_ax.set_ylim(*y_limits)
        self.physical_ax.set_xticks(
            np.arange(
                np.floor(x_limits[0] / 5) * 5,
                np.ceil(x_limits[1] / 5) * 5 + 1,
                5,
            )
        )
        self.physical_ax.set_yticks(
            np.arange(
                np.floor(y_limits[0] / 5) * 5,
                np.ceil(y_limits[1] / 5) * 5 + 1,
                5,
            )
        )
        self.physical_ax.set_xticks(
            np.arange(
                np.floor(x_limits[0] / DISPLAY_GRID_STEP_LAMBDA) * DISPLAY_GRID_STEP_LAMBDA,
                x_limits[1] + DISPLAY_GRID_STEP_LAMBDA,
                DISPLAY_GRID_STEP_LAMBDA,
            ),
            minor=True,
        )
        self.physical_ax.set_yticks(
            np.arange(
                np.floor(y_limits[0] / DISPLAY_GRID_STEP_LAMBDA) * DISPLAY_GRID_STEP_LAMBDA,
                y_limits[1] + DISPLAY_GRID_STEP_LAMBDA,
                DISPLAY_GRID_STEP_LAMBDA,
            ),
            minor=True,
        )
        self.physical_ax.grid(
            True, which="major", color=THEME["grid_color"], linewidth=0.5, alpha=0.25
        )
        self.physical_ax.grid(
            True, which="minor", color=THEME["grid_color"], linewidth=0.3, alpha=0.12
        )
        self.physical_ax.legend(loc="upper right", framealpha=0.72)
        self.physical_ax.set_aspect("auto")
        self.physical_hover_annotation = self.physical_ax.annotate(
            "",
            xy=(0, 0),
            xytext=(12, 12),
            textcoords="offset points",
            bbox={
                "boxstyle": "round,pad=0.35",
                "facecolor": "#ffffff",
                "edgecolor": THEME["card_border"],
                "alpha": 0.95,
                "linewidth": 0.8,
            },
            arrowprops={"arrowstyle": "->", "color": "#888888", "linewidth": 0.8},
            fontsize=8,
            color=THEME["text_primary"],
        )
        self.physical_hover_annotation.set_visible(False)

    def _draw_virtual_array(
        self,
        unique: np.ndarray,
        counts: np.ndarray,
        pair_map: dict[tuple[float, float], list[str]],
        metrics: ArrayMetrics,
    ) -> None:
        self.virtual_ax.clear()
        unique_display = _to_display_lambda(unique)
        x_min, x_max = float(unique_display[:, 0].min()), float(unique_display[:, 0].max())
        y_min, y_max = float(unique_display[:, 1].min()), float(unique_display[:, 1].max())
        self.virtual_ax.add_patch(
            Rectangle(
                (x_min, y_min),
                x_max - x_min,
                y_max - y_min,
                fill=False,
                linestyle="--",
                linewidth=1.2,
                edgecolor="#6f6f6f",
                alpha=0.55,
            )
        )
        sizes = 80 + 54 * np.clip(counts - 2, 0, 6)
        single_mask = counts == 1
        duplicate_mask = counts > 1
        if np.any(single_mask):
            self.virtual_ax.scatter(
                unique_display[single_mask, 0],
                unique_display[single_mask, 1],
                s=34,
                marker="o",
                color="#4f86c6",
                edgecolors="#1f2933",
                linewidths=0.45,
                label="unique point",
            )
        if np.any(duplicate_mask):
            self.virtual_ax.scatter(
                unique_display[duplicate_mask, 0],
                unique_display[duplicate_mask, 1],
                s=sizes[duplicate_mask],
                color="#f28e2b",
                marker="o",
                edgecolors="#7a2e00",
                linewidths=1.4,
                label="duplicate point",
            )
        for (x, y), count in zip(unique_display, counts):
            if count > 1:
                self.virtual_ax.annotate(
                    f"×{int(count)}",
                    xy=(x, y),
                    xytext=(5, 5),
                    textcoords="offset points",
                    fontsize=12,
                    color="#8a1c1c",
                    weight="bold",
                )

        # Store hover data
        self.virtual_hover_xy = unique_display
        self.virtual_hover_text = []
        for x, y in unique:
            key = (round(float(x), ROUND_DECIMALS), round(float(y), ROUND_DECIMALS))
            pairs = pair_map.get(key, [])
            pair_text = ", ".join(pairs[:10])
            if len(pairs) > 10:
                pair_text += f", ... ({len(pairs)} pairs)"
            self.virtual_hover_text.append(
                f"({x * DISPLAY_SCALE_LAMBDA:g} λ, {y * DISPLAY_SCALE_LAMBDA:g} λ)\n"
                f"Multiplicity: {len(pairs)}\n{pair_text}"
            )

        self.virtual_hover_annotation = self.virtual_ax.annotate(
            "",
            xy=(0, 0),
            xytext=(12, 12),
            textcoords="offset points",
            bbox={
                "boxstyle": "round,pad=0.35",
                "facecolor": "#ffffff",
                "edgecolor": THEME["card_border"],
                "alpha": 0.95,
                "linewidth": 0.8,
            },
            arrowprops={"arrowstyle": "->", "color": "#888888", "linewidth": 0.8},
            fontsize=8,
        )
        self.virtual_hover_annotation.set_visible(False)

        self.virtual_ax.set_title("Virtual Array", fontsize=TITLE_SIZE, pad=8, loc="left",
                                    color=THEME["text_primary"], fontweight="bold")
        self.virtual_ax.set_xlabel("x (λ)", color=THEME["text_secondary"])
        self.virtual_ax.set_ylabel("y (λ)", color=THEME["text_secondary"])
        self.virtual_ax.tick_params(colors=THEME["text_secondary"], labelsize=8)
        self.virtual_ax.grid(True, alpha=THEME["grid_alpha"], color=THEME["grid_color"], linewidth=0.5)

        # Simple padded limits — let set_aspect("equal") handle the rest
        x_limits = _axis_limits(unique_display[:, 0], minimum_span=6.0, padding=2.0)
        y_limits = _axis_limits(unique_display[:, 1], minimum_span=6.0, padding=2.0)
        self.virtual_ax.set_xlim(*x_limits)
        self.virtual_ax.set_ylim(*y_limits)
        self.virtual_ax.set_xticks(
            np.arange(
                np.floor(x_limits[0] / 5) * 5,
                np.ceil(x_limits[1] / 5) * 5 + 1,
                5,
            )
        )
        self.virtual_ax.set_yticks(
            np.arange(
                np.floor(y_limits[0] / 5) * 5,
                np.ceil(y_limits[1] / 5) * 5 + 1,
                5,
            )
        )
        self.virtual_ax.set_xticks(
            np.arange(
                np.floor(x_limits[0] / DISPLAY_GRID_STEP_LAMBDA) * DISPLAY_GRID_STEP_LAMBDA,
                x_limits[1] + DISPLAY_GRID_STEP_LAMBDA,
                DISPLAY_GRID_STEP_LAMBDA,
            ),
            minor=True,
        )
        self.virtual_ax.set_yticks(
            np.arange(
                np.floor(y_limits[0] / DISPLAY_GRID_STEP_LAMBDA) * DISPLAY_GRID_STEP_LAMBDA,
                y_limits[1] + DISPLAY_GRID_STEP_LAMBDA,
                DISPLAY_GRID_STEP_LAMBDA,
            ),
            minor=True,
        )
        self.virtual_ax.set_aspect("equal", adjustable="box")

        # Info box in upper-left corner
        self.virtual_ax.text(
            0.01,
            0.98,
            f"Virtual {metrics.unique_count}/{metrics.virtual_count} | "
            f"Dup {metrics.duplicate_excess} | "
            f"X {_format_mm(self.aperture_mm(metrics.x_aperture))} | "
            f"Y {_format_mm(self.aperture_mm(metrics.y_aperture))}",
            transform=self.virtual_ax.transAxes,
            ha="left",
            va="top",
            fontsize=8.5,
            color="#111111",
            bbox={
                "boxstyle": "round,pad=0.22",
                "facecolor": "#ffffff",
                "edgecolor": "#cfcfcf",
                "alpha": 0.80,
            },
        )
        if counts.max() > 1:
            self.virtual_ax.legend(loc="best", fontsize=8)

    def _draw_response_common(
        self,
        ax,
        response_cut: ResponseCut,
        metrics: ArrayMetrics,
    ) -> None:
        """Shared drawing logic for both Az and El response figures."""
        ax.clear()
        response_db = response_cut.gains_db
        response_angles = response_cut.angles
        sidelobe_index, sidelobe_is_peak = _response_sidelobe_marker(
            response_angles, response_db, response_cut.mainlobe_guard
        )
        sidelobe_angle = float(response_angles[sidelobe_index])
        sidelobe_gain = float(response_db[sidelobe_index])
        sidelobe_label = "Max sidelobe" if sidelobe_is_peak else "Guard-edge max"
        response_ylim = (-40.0, 0.0)

        ax.plot(response_angles, response_db, color="#2f6fbb", linewidth=1.8)
        show_legend = False
        if self.element_pattern is not None:
            if response_cut.mode == RESPONSE_MODE_ELEVATION:
                element_pattern_cut = self.element_pattern.normalized_elevation_gain_db_at(
                    response_angles
                )
            else:
                element_pattern_cut = self.element_pattern.normalized_horizontal_gain_db_at(
                    response_angles
                )
            pattern_cut = np.clip(
                element_pattern_cut,
                response_ylim[0],
                response_ylim[1],
            )
            ax.plot(
                response_angles,
                pattern_cut,
                color="#607d8b",
                linestyle="--",
                linewidth=1.3,
                alpha=0.72,
                label=response_cut.pattern_label,
            )
            show_legend = True
        ax.set_xlim(response_cut.fov)
        ax.set_ylim(response_ylim)
        ax.axvspan(
            -response_cut.mainlobe_guard,
            response_cut.mainlobe_guard,
            color="#bbbbbb",
            alpha=0.38,
        )
        ax.scatter(
            [0.0], [0.0], marker="+", s=80, color="#111111", linewidths=2.0, zorder=4
        )
        # Max sidelobe marker
        ax.scatter(
            [sidelobe_angle],
            [sidelobe_gain],
            marker="x",
            s=70,
            color="#d95f02",
            linewidths=2.0,
            zorder=5,
            clip_on=True,
            label=sidelobe_label,
        )

        x_low, x_high = response_cut.fov
        y_low, y_high = response_ylim
        annotation_boxes: list[tuple[float, float, float, float]] = []

        def annotation_position(angle: float, gain: float) -> tuple[float, float, str]:
            angle_axes = (angle - x_low) / (x_high - x_low)
            gain_axes = (gain - y_low) / (y_high - y_low)
            box_width = 0.18
            box_height = 0.15
            if angle >= 0:
                base_x = min(angle_axes + 0.08, 0.76)
                ha = "left"
            else:
                base_x = max(angle_axes - 0.08, 0.24)
                ha = "right"

            candidates = (0.12, -0.12, 0.25, -0.25, 0.38, -0.34, 0.0)
            for offset in candidates:
                y = float(np.clip(gain_axes + offset, 0.18, 0.82))
                if ha == "left":
                    box = (base_x, y - box_height / 2, base_x + box_width, y + box_height / 2)
                else:
                    box = (base_x - box_width, y - box_height / 2, base_x, y + box_height / 2)
                if not any(_axes_boxes_overlap(box, existing) for existing in annotation_boxes):
                    annotation_boxes.append(box)
                    return base_x, y, ha

            fallback_y = float(np.clip(gain_axes, 0.18, 0.82))
            if ha == "left":
                annotation_boxes.append(
                    (base_x, fallback_y - box_height / 2, base_x + box_width, fallback_y + box_height / 2)
                )
            else:
                annotation_boxes.append(
                    (base_x - box_width, fallback_y - box_height / 2, base_x, fallback_y + box_height / 2)
                )
            return base_x, fallback_y, ha

        annotation_x, annotation_y, annotation_ha = annotation_position(
            sidelobe_angle, sidelobe_gain
        )
        ax.annotate(
            (
                f"{sidelobe_label}\n{response_cut.label} = {sidelobe_angle:.1f}°\n"
                f"Gain = {sidelobe_gain:.2f} dB"
            ),
            xy=(sidelobe_angle, sidelobe_gain),
            xytext=(annotation_x, annotation_y),
            textcoords=ax.transAxes,
            ha=annotation_ha,
            va="center",
            fontsize=7.5,
            color="#6b4226",
            bbox={
                "boxstyle": "round,pad=0.25",
                "facecolor": "#fff8f0",
                "edgecolor": "#d4a574",
                "alpha": 0.92,
                "linewidth": 0.7,
            },
            arrowprops={"arrowstyle": "->", "color": "#b8875a", "linewidth": 0.7},
            annotation_clip=True,
        )

        # Grating lobe marker (Az only)
        if (
            response_cut.mode == RESPONSE_MODE_AZIMUTH
            and metrics.azimuth_grating_lobe_angle is not None
            and metrics.azimuth_grating_lobe_db is not None
        ):
            grating_angle = metrics.azimuth_grating_lobe_angle
            grating_gain = metrics.azimuth_grating_lobe_db
            grating_same_as_max = (
                abs(grating_angle - sidelobe_angle)
                <= float(np.diff(response_angles).mean()) / 2.0
                and abs(grating_gain - sidelobe_gain) <= 0.05
            )
            ax.scatter(
                [grating_angle],
                [grating_gain],
                marker="^",
                s=82,
                facecolors="none",
                edgecolors="#7b1fa2",
                linewidths=1.8,
                zorder=6,
                clip_on=True,
                label=(
                    "Grating lobe = max sidelobe"
                    if grating_same_as_max
                    else "Grating lobe"
                ),
            )
            show_legend = True
            if not grating_same_as_max:
                grating_x, grating_y, grating_ha = annotation_position(
                    grating_angle, grating_gain
                )
                ax.annotate(
                    f"Grating lobe\nAz = {grating_angle:.1f}°\nGain = {grating_gain:.2f} dB",
                    xy=(grating_angle, grating_gain),
                    xytext=(grating_x, grating_y),
                    textcoords=ax.transAxes,
                    ha=grating_ha,
                    va="center",
                    fontsize=7.5,
                    color="#4a235a",
                    bbox={
                        "boxstyle": "round,pad=0.25",
                        "facecolor": "#f5eef8",
                        "edgecolor": "#9b72b0",
                        "alpha": 0.92,
                        "linewidth": 0.7,
                    },
                    arrowprops={"arrowstyle": "->", "color": "#9b72b0", "linewidth": 0.7},
                    annotation_clip=True,
                )
            else:
                ax.legend(loc="lower right", fontsize=7, framealpha=0.72)
                show_legend = False

        ax.set_title(f"Front Radar Response ({response_cut.label})", pad=6, y=1.02, loc="left",
                      color=THEME["text_primary"], fontweight="bold")
        ax.set_xlabel(response_cut.x_label, color=THEME["text_secondary"])
        ax.set_ylabel("Normalized gain (dB)", labelpad=2, color=THEME["text_secondary"])
        ax.tick_params(colors=THEME["text_secondary"], labelsize=8)
        ax.grid(True, alpha=THEME["grid_alpha"], color=THEME["grid_color"], linewidth=0.5)
        if show_legend:
            ax.legend(loc="lower right", fontsize=7, framealpha=0.72)

        response_psl_db = (
            metrics.elevation_psl_db
            if response_cut.mode == RESPONSE_MODE_ELEVATION
            else metrics.azimuth_psl_db
        )
        # PSL badge in lower-left corner
        ax.text(
            0.02,
            0.08,
            f"{response_cut.label} PSL: {response_psl_db:.2f} dB",
            transform=ax.transAxes,
            ha="left",
            va="bottom",
            fontsize=9,
            color=THEME["text_primary"],
            bbox={
                "boxstyle": "round,pad=0.25",
                "facecolor": "#ffffff",
                "edgecolor": THEME["card_border"],
                "alpha": 0.9,
                "linewidth": 0.7,
            },
        )

        return response_db, response_angles

    def _draw_response(
        self,
        mode: str,
        chart: ResponseChart,
        af_db: np.ndarray,
        azimuths: np.ndarray,
        elevations: np.ndarray,
        metrics: ArrayMetrics,
    ) -> None:
        """Draw a response chart (Az or El) and set up hover data."""
        response_cut = _response_cut_for_mode(af_db, azimuths, elevations, mode)
        response_db, response_angles = self._draw_response_common(chart.ax, response_cut, metrics)

        chart.hover_db = response_db
        chart.hover_angles = response_angles
        chart.hover_annotation = chart.ax.annotate(
            "",
            xy=(0, 0),
            xytext=(12, 12),
            textcoords="offset points",
            bbox={
                "boxstyle": "round,pad=0.35",
                "facecolor": "#ffffff",
                "edgecolor": THEME["card_border"],
                "alpha": 0.95,
                "linewidth": 0.8,
            },
            arrowprops={"arrowstyle": "->", "color": "#888888", "linewidth": 0.8},
            fontsize=8,
            color=THEME["text_primary"],
        )
        chart.hover_annotation.set_visible(False)

    # ── Notes helpers ─────────────────────────────────────────────────

    def _notes_parts(self, metrics: ArrayMetrics) -> list[str]:
        notes = []
        if metrics.duplicate_excess > 0:
            notes.append("Duplicate virtual points detected")
        if metrics.azimuth_psl_db > -10.0:
            notes.append("Windowing recommended")
        if metrics.elevation_ambiguity_level == "High":
            notes.append("elevation ambiguity high")
        elif metrics.elevation_ambiguity_level == "Medium":
            notes.append("elevation ambiguity medium")
        return notes

    def _update_notes_panel(self, notes_parts: list[str]) -> None:
        for child in self.notes_items_frame.winfo_children():
            child.destroy()

        if not notes_parts:
            notes_parts = ["None"]

        for index, note in enumerate(notes_parts):
            text, color = _note_display(note)
            pill = tk.Frame(self.notes_items_frame, bg=color, padx=6, pady=2)
            pill.pack(anchor="w", pady=(1 if index else 0, 1))
            ttk.Label(
                pill,
                text=text,
                font=(THEME["font_family"], THEME["font_size_sm"]),
                foreground="#ffffff",
                background=color,
            ).pack()

    def _element_pattern_export_info(self) -> dict[str, object]:
        if self.element_pattern is None:
            return {"mode": "isotropic"}
        return {
            "mode": "loaded",
            "source": self.element_pattern.source_path,
            "angle_column": self.element_pattern.angle_column,
            "horizontal_column": self.element_pattern.horizontal_column,
            "elevation_column": self.element_pattern.elevation_column,
        }

    def _load_local_state(self) -> None:
        try:
            state = load_state()
            if not state:
                return
            if state.get("version") != LOCAL_STATE_VERSION:
                LOGGER.info("Ignoring unsupported local state version: %r", state.get("version"))
                return

            layout_dir = state.get("last_layout_dir")
            if isinstance(layout_dir, str) and layout_dir:
                self.last_layout_dir = Path(layout_dir)

            pattern_dir = state.get("last_pattern_dir")
            if isinstance(pattern_dir, str) and pattern_dir:
                self.last_pattern_dir = Path(pattern_dir)

            frequency_mode = state.get("frequency_mode")
            if isinstance(frequency_mode, str) and frequency_mode in FREQUENCY_MODES_MM:
                self.frequency_mode.set(frequency_mode)

            layout = state.get("layout")
            if layout is not None:
                self.elements = self._elements_from_layout_config(layout)
            LOGGER.info("Loaded local state from %s", state_path())
        except Exception:
            LOGGER.exception("Failed to load local state from %s", state_path())

    def _save_local_state(self) -> None:
        state = {
            "version": LOCAL_STATE_VERSION,
            "last_layout_dir": str(self.last_layout_dir),
            "last_pattern_dir": str(self.last_pattern_dir),
            "frequency_mode": self.frequency_mode.get(),
            "layout": self._layout_coordinates_config(),
        }
        save_state(state)
        LOGGER.info("Saved local state to %s", state_path())

    def on_close(self) -> None:
        try:
            self._save_local_state()
        except Exception:
            LOGGER.exception("Failed to save local state")
        self.root.destroy()

    # ── Event handlers ────────────────────────────────────────────────

    def on_press(self, event) -> None:  # noqa: ANN001
        if event.inaxes != self.physical_ax or event.xdata is None or event.ydata is None:
            return
        internal_x = _to_internal_half_lambda(event.xdata)
        internal_y = _to_internal_half_lambda(event.ydata)
        self.dragging = self._nearest_element(internal_x, internal_y)
        if self.dragging is not None:
            x_limits = tuple(float(value) for value in self.physical_ax.get_xlim())
            y_limits = tuple(float(value) for value in self.physical_ax.get_ylim())
            self.drag_axis_limits = (x_limits, y_limits)
            self.drag_bounds = (
                _to_internal_half_lambda(x_limits[0]),
                _to_internal_half_lambda(x_limits[1]),
                _to_internal_half_lambda(y_limits[0]),
                _to_internal_half_lambda(y_limits[1]),
            )
            self.selected_element = self.dragging
            self.status.set(
                f"Selected {self.dragging.name} | "
                f"x={self.dragging.x * DISPLAY_SCALE_LAMBDA:g} λ | "
                f"y={self.dragging.y * DISPLAY_SCALE_LAMBDA:g} λ"
            )
            self._draw_physical_array()
            self.phys_canvas.draw()
        elif self.selected_element is not None:
            self.selected_element = None
            self.status.set(
                "Selection cleared. Click an antenna element to select."
            )
            self._draw_physical_array()
            self.phys_canvas.draw()

    def on_motion(self, event) -> None:  # noqa: ANN001
        if self.dragging is not None:
            if event.x is None or event.y is None:
                return
            display_x, display_y = self.physical_ax.transData.inverted().transform(
                (event.x, event.y)
            )
            internal_x = _to_internal_half_lambda(float(display_x))
            internal_y = _to_internal_half_lambda(float(display_y))
            if self.drag_bounds is not None:
                min_x, max_x, min_y, max_y = self.drag_bounds
                internal_x = _clip_to_bounds(internal_x, min_x, max_x)
                internal_y = _clip_to_bounds(internal_y, min_y, max_y)
            self.dragging.x = internal_x
            self.dragging.y = internal_y
            self.status.set(
                f"{self.dragging.name}: "
                f"x={self.dragging.x * DISPLAY_SCALE_LAMBDA:g} λ, "
                f"y={self.dragging.y * DISPLAY_SCALE_LAMBDA:g} λ"
            )
            self._draw_physical_array()
            self.phys_canvas.draw()
            return

        self._update_physical_hover(event)
        self._update_virtual_hover(event)
        self._update_response_hover(event, self.az_chart, "Az")
        self._update_response_hover(event, self.el_chart, "El")

    def on_release(self, event) -> None:  # noqa: ANN001
        if self.dragging is not None:
            if self.drag_bounds is not None:
                min_x, max_x, min_y, max_y = self.drag_bounds
                self.dragging.x = _snap_to_grid_inside(
                    self.dragging.x, min_x, max_x
                )
                self.dragging.y = _snap_to_grid_inside(
                    self.dragging.y, min_y, max_y
                )
            else:
                self.dragging.x = snap_to_grid(self.dragging.x)
                self.dragging.y = snap_to_grid(self.dragging.y)
            self.status.set(
                f"{self.dragging.name}: "
                f"x={self.dragging.x * DISPLAY_SCALE_LAMBDA:g} λ, "
                f"y={self.dragging.y * DISPLAY_SCALE_LAMBDA:g} λ"
            )
            self.dragging = None
            self.drag_bounds = None
            self.drag_axis_limits = None
            self.generate_virtual_array()

    def on_arrow_key(self, event) -> str:
        if self.selected_element is None:
            return "break"

        dx = 0.0
        dy = 0.0
        if event.keysym == "Left":
            dx = -GRID_STEP
        elif event.keysym == "Right":
            dx = GRID_STEP
        elif event.keysym == "Up":
            dy = GRID_STEP
        elif event.keysym == "Down":
            dy = -GRID_STEP
        else:
            return "break"

        self.selected_element.x = snap_to_grid(self.selected_element.x + dx)
        self.selected_element.y = snap_to_grid(self.selected_element.y + dy)
        self.generate_virtual_array()
        self.status.set(
            f"Selected {self.selected_element.name} | "
            f"x={self.selected_element.x * DISPLAY_SCALE_LAMBDA:g} λ | "
            f"y={self.selected_element.y * DISPLAY_SCALE_LAMBDA:g} λ"
        )
        return "break"

    def on_delete_key(self, _event) -> str:  # noqa: ANN001
        self.delete_selected_element()
        return "break"

    # ── Hover logic ───────────────────────────────────────────────────

    def _update_virtual_hover(self, event) -> None:  # noqa: ANN001
        if self.virtual_hover_annotation is None:
            return
        if (
            event.inaxes != self.virtual_ax
            or event.xdata is None
            or event.ydata is None
            or len(self.virtual_hover_xy) == 0
        ):
            if self.virtual_hover_annotation.get_visible():
                self.virtual_hover_annotation.set_visible(False)
                self.virt_canvas.draw_idle()
            return

        x_span = max(abs(np.diff(self.virtual_ax.get_xlim())[0]), 1.0)
        y_span = max(abs(np.diff(self.virtual_ax.get_ylim())[0]), 1.0)
        normalized_distance = np.hypot(
            (self.virtual_hover_xy[:, 0] - event.xdata) / x_span,
            (self.virtual_hover_xy[:, 1] - event.ydata) / y_span,
        )
        index = int(np.argmin(normalized_distance))
        if normalized_distance[index] > 0.018:
            if self.virtual_hover_annotation.get_visible():
                self.virtual_hover_annotation.set_visible(False)
                self.virt_canvas.draw_idle()
            return

        xy = self.virtual_hover_xy[index]
        self.virtual_hover_annotation.xy = (xy[0], xy[1])
        self.virtual_hover_annotation.set_text(self.virtual_hover_text[index])
        self.virtual_hover_annotation.set_visible(True)
        self.virt_canvas.draw_idle()

    def _update_physical_hover(self, event) -> None:  # noqa: ANN001
        if self.physical_hover_annotation is None:
            return
        if event.inaxes != self.physical_ax or event.xdata is None or event.ydata is None:
            if self.physical_hover_annotation.get_visible():
                self.physical_hover_annotation.set_visible(False)
                self.phys_canvas.draw_idle()
            return

        internal_x = _to_internal_half_lambda(event.xdata)
        internal_y = _to_internal_half_lambda(event.ydata)
        distances = np.array(
            [
                (element.x - internal_x) ** 2 + (element.y - internal_y) ** 2
                for element in self.elements
            ],
            dtype=float,
        )
        index = int(np.argmin(distances))
        if distances[index] > 2.0:
            if self.physical_hover_annotation.get_visible():
                self.physical_hover_annotation.set_visible(False)
                self.phys_canvas.draw_idle()
            return

        element = self.elements[index]
        display_x = element.x * DISPLAY_SCALE_LAMBDA
        display_y = element.y * DISPLAY_SCALE_LAMBDA
        self.physical_hover_annotation.xy = (display_x, display_y)
        self.physical_hover_annotation.set_text(
            f"{element.name}\nx = {display_x:g} λ\ny = {display_y:g} λ"
        )
        self.physical_hover_annotation.set_visible(True)
        self.phys_canvas.draw_idle()

    def _update_response_hover(
        self, event, chart: ResponseChart, label: str  # noqa: ANN001
    ) -> None:
        """Update hover tooltip for a response chart (Az or El)."""
        if chart.hover_annotation is None:
            return
        if (
            event.inaxes != chart.ax
            or event.xdata is None
            or event.ydata is None
            or chart.hover_db.size == 0
        ):
            if chart.hover_annotation.get_visible():
                chart.hover_annotation.set_visible(False)
                chart.canvas.draw_idle()
            return

        angle_index = int(np.argmin(np.abs(chart.hover_angles - event.xdata)))
        angle = float(chart.hover_angles[angle_index])
        gain = float(chart.hover_db[angle_index])
        chart.hover_annotation.xy = (angle, gain)
        chart.hover_annotation.set_text(
            f"{label} = {angle:.1f}°\nGain = {gain:.2f} dB"
        )
        chart.hover_annotation.set_visible(True)
        chart.canvas.draw_idle()

    def _nearest_element(self, x: float, y: float) -> EditableElement | None:
        distances = [
            ((element.x - x) ** 2 + (element.y - y) ** 2, element)
            for element in self.elements
        ]
        distance, element = min(distances, key=lambda item: item[0])
        return element if distance <= 4.0 else None


# ═══════════════════════════════════════════════════════════════════════
#  Entry point
# ═══════════════════════════════════════════════════════════════════════
def main() -> None:
    log_path = configure_logging()
    install_excepthook()
    LOGGER.info("Starting MIMO Array Visualizer")
    root = tk.Tk()
    root.report_callback_exception = _show_unhandled_tk_exception
    root.geometry(f"{WINDOW_WIDTH}x{WINDOW_HEIGHT}")
    root.minsize(WINDOW_MIN_WIDTH, WINDOW_MIN_HEIGHT)
    root.resizable(True, True)
    LOGGER.info("Log file: %s", log_path)
    app = VirtualArrayGui(root)
    root.protocol("WM_DELETE_WINDOW", app.on_close)
    try:
        root.mainloop()
    finally:
        LOGGER.info("MIMO Array Visualizer exited")


if __name__ == "__main__":
    main()
