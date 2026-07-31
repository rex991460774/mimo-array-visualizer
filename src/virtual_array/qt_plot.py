from __future__ import annotations

from dataclasses import dataclass
from types import SimpleNamespace
from typing import Any, Callable

import numpy as np
import pyqtgraph as pg
from PySide6 import QtCore, QtGui, QtWidgets

from .native_theme import TOKENS


pg.setConfigOptions(antialias=True)

rcParams: dict[str, Any] = {}
_SUBPLOT_MARGIN_SCALE = 0.5
_LARGE_SUBPLOT_LEFT_MARGIN_SCALE = 0.35
_EQUAL_ASPECT_WIDTH_SCALE = 0.9
_EQUAL_ASPECT_HEIGHT_SCALE = 1.04
_LARGE_EQUAL_ASPECT_WIDTH_SCALE = 0.938
_LARGE_EQUAL_ASPECT_HEIGHT_SCALE = 1.01
_LARGE_EQUAL_ASPECT_HEIGHT_CAP_SCALE = 0.985
_LARGE_WIDE_EQUAL_ASPECT_WIDTH_SCALE = 0.629
_LARGE_WIDE_EQUAL_ASPECT_HEIGHT_SCALE = 0.98
_COMPACT_EQUAL_ASPECT_WIDTH_SCALE = 0.935
_WIDE_COMPACT_EQUAL_ASPECT_WIDTH_SCALE = 0.808
_COMPACT_EQUAL_ASPECT_HEIGHT_SCALE = 1.19
_WIDE_COMPACT_EQUAL_ASPECT_HEIGHT_SCALE = 1.095
_LARGE_EQUAL_ASPECT_MARGINS = (3, 3, 14, 0)
_LARGE_WIDE_EQUAL_ASPECT_MARGINS = (5, 12, 31, 0)
_COMPACT_EQUAL_ASPECT_MARGINS = (3, 3, 14, 5)
_WIDE_COMPACT_EQUAL_ASPECT_MARGINS = (5, 12, 31, 0)
_COMPACT_SUBPLOT_MARGINS = (0, 12, 12, 8)
_COMPACT_SUBPLOT_PLOT_MARGINS = (5, 4, 0, 0)
_LARGE_SUBPLOT_PLOT_MARGINS = (-15, 21, 10, 4)
_RECT_PLOT_LEFT_MARGIN = 23
_RECT_PLOT_TOP_MARGIN = 27
_RECT_PLOT_RIGHT_MARGIN = 0
_RECT_PLOT_BOTTOM_MARGIN = 24
_WIDE_RECT_PLOT_BOTTOM_MARGIN = 34
_COLORBAR_X_OFFSET = -1
_COLORBAR_MIN_WIDTH = 67
_COMPACT_COLORBAR_MIN_WIDTH = 83
_COLORBAR_TOP_COMPENSATION = -2
_COLORBAR_BOTTOM_COMPENSATION = 3
_WIDE_COLORBAR_BOTTOM_COMPENSATION = 12


def _qt_parent(parent: Any) -> QtWidgets.QWidget | None:
    """Resolve either a native Qt parent or a transitional Tk-style wrapper."""
    if parent is None:
        return None
    if isinstance(parent, QtWidgets.QWidget):
        return parent
    candidate = getattr(parent, "_qt", None)
    return candidate if isinstance(candidate, QtWidgets.QWidget) else None


def _as_color(value: Any) -> str | None:
    return value if isinstance(value, str) and value else None


def _cursor_shape(name: str | None) -> QtCore.Qt.CursorShape:
    return {
        "hand2": QtCore.Qt.CursorShape.PointingHandCursor,
        "pointinghand": QtCore.Qt.CursorShape.PointingHandCursor,
        "fleur": QtCore.Qt.CursorShape.SizeAllCursor,
        "size_all": QtCore.Qt.CursorShape.SizeAllCursor,
        "openhand": QtCore.Qt.CursorShape.OpenHandCursor,
        "closedhand": QtCore.Qt.CursorShape.ClosedHandCursor,
        "sb_h_double_arrow": QtCore.Qt.CursorShape.SizeHorCursor,
        "size_hor": QtCore.Qt.CursorShape.SizeHorCursor,
        "sb_v_double_arrow": QtCore.Qt.CursorShape.SizeVerCursor,
        "size_ver": QtCore.Qt.CursorShape.SizeVerCursor,
        "cross": QtCore.Qt.CursorShape.CrossCursor,
        "crosshair": QtCore.Qt.CursorShape.CrossCursor,
    }.get(name or "", QtCore.Qt.CursorShape.ArrowCursor)


def _set_cursor(widget: QtWidgets.QWidget, name: str | None) -> None:
    if name:
        widget.setCursor(QtGui.QCursor(_cursor_shape(name)))
    else:
        widget.unsetCursor()


def _parse_pad_pair(value: Any) -> tuple[int, int]:
    if value is None:
        return (0, 0)
    if isinstance(value, (int, float)):
        size = int(value)
        return (size, size)
    if isinstance(value, (tuple, list)):
        if len(value) == 2:
            return (int(value[0]), int(value[1]))
        if len(value) == 4:
            return (int(value[0]), int(value[2]))
    return (0, 0)


def _is_no_color(value: Any) -> bool:
    return isinstance(value, str) and value.lower() in {"none", "transparent"}


def _color(value: Any, alpha: float | None = None) -> QtGui.QColor:
    if value is None:
        qcolor = QtGui.QColor("#000000")
    elif isinstance(value, QtGui.QColor):
        qcolor = QtGui.QColor(value)
    elif isinstance(value, tuple):
        if len(value) >= 3:
            scale = 255 if all(isinstance(v, float) and v <= 1 for v in value[:3]) else 1
            qcolor = QtGui.QColor(
                int(value[0] * scale),
                int(value[1] * scale),
                int(value[2] * scale),
            )
        else:
            qcolor = QtGui.QColor("#000000")
    else:
        qcolor = QtGui.QColor(str(value))
    if alpha is not None:
        qcolor.setAlphaF(max(0.0, min(1.0, float(alpha))))
    return qcolor


def _pen(
    color: Any = None,
    *,
    width: float | None = None,
    alpha: float | None = None,
    linestyle: str | None = None,
) -> QtGui.QPen:
    pen = pg.mkPen(_color(color, alpha), width=1.0 if width is None else float(width))
    if linestyle in {"--", "dashed"}:
        pen.setStyle(QtCore.Qt.PenStyle.DashLine)
    elif linestyle in {":", "dotted"}:
        pen.setStyle(QtCore.Qt.PenStyle.DotLine)
    return pen


def _brush(color: Any = None, *, alpha: float | None = None) -> QtGui.QBrush:
    if _is_no_color(color):
        return QtGui.QBrush(QtCore.Qt.BrushStyle.NoBrush)
    return pg.mkBrush(_color(color, alpha))


def _tick_values(values: Any) -> list[float]:
    try:
        array = np.asarray(values, dtype=float).ravel()
    except Exception:
        return []
    return [float(value) for value in array if np.isfinite(value)]


def _tick_label(value: float) -> str:
    if abs(value - round(value)) < 1e-9:
        return str(int(round(value)))
    return f"{value:g}"


def _text_anchor(ha: str | None, va: str | None) -> tuple[float, float]:
    x_anchor = {"left": 0.0, "center": 0.5, "right": 1.0}.get(str(ha or "left"), 0.0)
    y_anchor = {"top": 0.0, "center": 0.5, "bottom": 1.0, "baseline": 1.0}.get(
        str(va or "top"),
        0.0,
    )
    return (x_anchor, y_anchor)


def _font_families() -> list[str]:
    configured = rcParams.get("font.sans-serif") or rcParams.get("font.family")
    if isinstance(configured, str):
        values = [configured]
    else:
        try:
            values = [str(value) for value in configured]
        except TypeError:
            values = []
    values.extend(["Microsoft YaHei", "SimHei", "DejaVu Sans"])
    return list(dict.fromkeys(value for value in values if value))


def _primary_font_family() -> str:
    return _font_families()[0]


def _font(size: Any = None, weight: Any = None) -> QtGui.QFont | None:
    if size is None and weight is None:
        return None
    font = QtGui.QFont(_primary_font_family())
    if hasattr(font, "setFamilies"):
        font.setFamilies(_font_families())
    if size is not None:
        try:
            font.setPointSizeF(float(size))
        except Exception:
            pass
    if str(weight).lower() in {"bold", "demibold", "600", "700"}:
        font.setBold(True)
    return font


def _label_style_args(kwargs: dict[str, Any], *, default_size: float | None = None) -> dict[str, Any]:
    args: dict[str, Any] = {}
    args["font-family"] = ", ".join(
        family if family == "sans-serif" else f'"{family}"'
        for family in _font_families()
    )
    color = kwargs.get("color")
    if color:
        args["color"] = _color(color).name()
    size = kwargs.get("fontsize", default_size)
    if size is not None:
        try:
            args["size"] = f"{float(size):g}pt"
        except Exception:
            pass
    weight = kwargs.get("fontweight") or kwargs.get("weight")
    if str(weight).lower() in {"bold", "demibold", "600", "700"}:
        args["bold"] = True
    elif weight is not None:
        args["bold"] = False
    return args


def _bbox_pen_brush(bbox: Any) -> tuple[QtGui.QPen | None, QtGui.QBrush | None]:
    if not isinstance(bbox, dict):
        return (None, None)
    edge = bbox.get("edgecolor")
    face = bbox.get("facecolor")
    alpha = bbox.get("alpha")
    width = bbox.get("linewidth", 1.0)
    pen = (
        QtGui.QPen(QtCore.Qt.PenStyle.NoPen)
        if edge is None or _is_no_color(edge)
        else _pen(edge, width=width, alpha=alpha)
    )
    brush = (
        QtGui.QBrush(QtCore.Qt.BrushStyle.NoBrush)
        if face is None or _is_no_color(face)
        else _brush(face, alpha=alpha)
    )
    return (pen, brush)


def _set_text_margin(item: pg.TextItem, margin: float) -> None:
    try:
        item.textItem.document().setDocumentMargin(float(margin))
    except Exception:
        return


def _bbox_text_scale(
    text: str,
    fontsize: Any,
    bbox: Any,
    rotation: Any,
) -> tuple[float, float] | None:
    if not isinstance(bbox, dict) or fontsize is None:
        return None
    try:
        size = float(fontsize)
    except Exception:
        return None
    try:
        angle = abs(float(rotation or 0.0)) % 180.0
    except Exception:
        angle = 0.0
    is_vertical = 70.0 <= angle <= 110.0
    is_multiline = "\n" in text

    # Qt's QTextDocument uses taller line boxes than matplotlib/Tk for the same
    # point size.  Keep these corrections local to plot badges so axis chrome
    # and plain Tx/Rx labels retain their native pyqtgraph sizing.
    if size <= 7.6:
        if is_vertical:
            return (0.70, 0.92)
        if is_multiline:
            return (0.99, 0.78)
        return (0.92, 0.73)
    if size <= 8.6:
        return (1.10, 0.78) if not is_multiline else (1.02, 0.80)
    if is_multiline:
        return (1.07, 0.85)
    return (1.00, 0.78)


def _apply_bbox_text_scale(
    item: pg.TextItem,
    text: str,
    fontsize: Any,
    bbox: Any,
    rotation: Any,
) -> None:
    # Keep text glyphs at their native aspect ratio; shrinking plot badges with
    # transforms makes Qt-rendered labels look vertically compressed.
    return


def _uses_short_ascii_legend(labels: list[str]) -> bool:
    return bool(labels) and all(len(label) <= 2 and label.isascii() for label in labels)


class _LabelProxy:
    def __init__(self, setter: Callable[[str], None]) -> None:
        self._setter = setter

    def set_text(self, text: str) -> None:
        self._setter(str(text))

    def set_fontsize(self, _size: float) -> None:
        return

    def set_color(self, _color_value: Any) -> None:
        return

    def set_fontweight(self, _weight: str) -> None:
        return

    def set_horizontalalignment(self, _alignment: str) -> None:
        return

    def set_verticalalignment(self, _alignment: str) -> None:
        return


class _InvertedDataTransform:
    def __init__(self, axes: "Axes") -> None:
        self.axes = axes

    def transform(self, point: Any) -> tuple[float, float]:
        x, y = point
        scene_point = QtCore.QPointF(float(x), float(y))
        data_point = self.axes.plot_item.vb.mapSceneToView(scene_point)
        return (float(data_point.x()), float(data_point.y()))


class _DataTransform:
    def __init__(self, axes: "Axes") -> None:
        self.axes = axes

    def inverted(self) -> _InvertedDataTransform:
        return _InvertedDataTransform(self.axes)


class _Artist:
    def __init__(self, item: Any | None = None) -> None:
        self.item = item
        self._visible = True

    def set_visible(self, visible: bool) -> None:
        self._visible = bool(visible)
        if self.item is not None and hasattr(self.item, "setVisible"):
            self.item.setVisible(self._visible)

    def get_visible(self) -> bool:
        return self._visible

    def remove(self) -> None:
        if self.item is not None and hasattr(self.item, "getViewBox"):
            view_box = self.item.getViewBox()
            if view_box is not None:
                view_box.removeItem(self.item)
        self.item = None

    def set_clip_on(self, _enabled: bool) -> None:
        return

    def set_zorder(self, _zorder: int) -> None:
        return


class _ScatterArtist(_Artist):
    def __init__(
        self,
        item: Any | None = None,
        *,
        marker_scale: float = 1.55,
        size: Any = 28,
    ) -> None:
        super().__init__(item)
        self._marker_scale = marker_scale
        self._marker_size = self._mpl_marker_size(size)

    def _mpl_marker_size(self, size: Any) -> float:
        data = np.asarray(size, dtype=float)
        value = float(data.ravel()[0]) if data.size else 28.0
        return max(3.0, value ** 0.5 * self._marker_scale)

    def set_offsets(self, offsets: Any) -> None:
        if self.item is None:
            return
        data = np.asarray(offsets, dtype=float)
        if data.size == 0:
            self.item.setData([], [])
            return
        data = data.reshape((-1, 2))
        self.item.setData(x=data[:, 0], y=data[:, 1])
        self.item.setSize(self._marker_size)

    def set_sizes(self, sizes: Any) -> None:
        if self.item is None:
            return
        self._marker_size = self._mpl_marker_size(sizes)
        self.item.setSize(self._marker_size)


class _TextArtist(_Artist):
    def __init__(
        self,
        item: pg.TextItem,
        x: float = 0.0,
        y: float = 0.0,
        *,
        axes: "Axes | None" = None,
        offset_units: str | None = None,
        ha: str | None = None,
        va: str | None = None,
    ) -> None:
        super().__init__(item)
        self._xy = (float(x), float(y))
        self._offset = (0.0, 0.0)
        self._axes = axes
        self._offset_units = offset_units
        self._ha = ha or "left"
        self._va = va or "top"

    @property
    def xy(self) -> tuple[float, float]:
        return self._xy

    @xy.setter
    def xy(self, value: tuple[float, float]) -> None:
        self._xy = (float(value[0]), float(value[1]))
        self._apply_position()

    def set_text(self, text: str) -> None:
        if self.item is not None:
            self.item.setText(str(text))

    def set_position(self, xy: tuple[float, float]) -> None:
        self._offset = (float(xy[0]), float(xy[1]))
        self._apply_position()

    def _apply_position(self) -> None:
        if self.item is None:
            return
        dx, dy = self._converted_offset()
        self.item.setPos(self._xy[0] + dx, self._xy[1] + dy)

    def _converted_offset(self) -> tuple[float, float]:
        if self._offset_units != "offset points" or self._axes is None:
            return self._offset
        view_range = self._axes.plot_item.vb.viewRange()
        x_low, x_high = map(float, view_range[0])
        y_low, y_high = map(float, view_range[1])
        view_width = max(1.0, float(self._axes.plot_item.vb.width()))
        view_height = max(1.0, float(self._axes.plot_item.vb.height()))
        dx_points, dy_points = self._offset
        dx_pixels = dx_points * self._axes.figure.dpi / 72.0
        dy_pixels = dy_points * self._axes.figure.dpi / 72.0
        return (
            dx_pixels * (x_high - x_low) / view_width,
            dy_pixels * (y_high - y_low) / view_height,
        )

    def _apply_anchor(self) -> None:
        if self.item is not None and hasattr(self.item, "setAnchor"):
            self.item.setAnchor(_text_anchor(self._ha, self._va))

    def set_ha(self, value: str) -> None:
        self._ha = str(value)
        self._apply_anchor()

    def set_va(self, value: str) -> None:
        self._va = str(value)
        self._apply_anchor()


class _ImageArtist(_Artist):
    def __init__(self, item: pg.ImageItem, levels: tuple[float, float] | None = None) -> None:
        super().__init__(item)
        self.levels = levels


@dataclass
class Rectangle:
    xy: tuple[float, float]
    width: float
    height: float
    kwargs: dict[str, Any]

    def __init__(self, xy: tuple[float, float], width: float, height: float, **kwargs: Any) -> None:
        self.xy = xy
        self.width = width
        self.height = height
        self.kwargs = kwargs


class _Spine:
    def set_color(self, _color_value: Any) -> None:
        return

    def set_edgecolor(self, _color_value: Any) -> None:
        return

    def set_linewidth(self, _width: float) -> None:
        return


class _Legend:
    def __init__(self, item: pg.LegendItem | None = None) -> None:
        self.item = item

    def set_zorder(self, zorder: int) -> None:
        if self.item is not None:
            self.item.setZValue(float(zorder))

    def get_frame(self) -> "_Legend":
        return self

    def set_facecolor(self, color_value: Any) -> None:
        if self.item is None:
            return
        if color_value in {"none", "None", None}:
            brush = QtGui.QBrush(QtCore.Qt.BrushStyle.NoBrush)
        else:
            brush = _brush(color_value)
        self.item.setBrush(brush)

    def set_edgecolor(self, color_value: Any) -> None:
        if self.item is None:
            return
        if color_value in {"none", "None", None}:
            pen = QtGui.QPen(QtCore.Qt.PenStyle.NoPen)
        else:
            pen = _pen(color_value)
        self.item.setPen(pen)

    def set_linewidth(self, width: float) -> None:
        if self.item is None:
            return
        pen = self.item.pen
        if isinstance(pen, QtGui.QPen):
            pen.setWidthF(float(width))
            self.item.setPen(pen)

    def set_alpha(self, alpha: float) -> None:
        if self.item is None:
            return
        brush = self.item.brush
        if isinstance(brush, QtGui.QBrush) and brush.style() != QtCore.Qt.BrushStyle.NoBrush:
            color = brush.color()
            color.setAlphaF(max(0.0, min(1.0, float(alpha))))
            self.item.setBrush(QtGui.QBrush(color))

    def get_texts(self) -> list[Any]:
        if self.item is None:
            return []
        return [_LegendText(label, self.item) for _sample, label in self.item.items]


class _LegendText:
    def __init__(self, label: Any, legend: pg.LegendItem | None = None) -> None:
        self.label = label
        self.legend = legend

    def set_color(self, color_value: Any) -> None:
        color_name = _color(color_value).name()
        if self.legend is not None:
            try:
                self.legend.setLabelTextColor(color_name)
            except Exception:
                pass
        text = getattr(self.label, "text", "")
        try:
            self.label.setText(text, color=color_name)
        except Exception:
            return

    def set_fontsize(self, size: float) -> None:
        text = getattr(self.label, "text", "")
        try:
            self.label.setText(text, size=f"{float(size):g}pt")
        except Exception:
            return


class _Colorbar:
    def __init__(self, axis: "Axes") -> None:
        self.ax = axis
        self.outline = SimpleNamespace(
            set_edgecolor=lambda _value: None,
            set_linewidth=lambda _value: None,
        )

    def set_ticks(self, ticks: Any) -> None:
        values = _tick_values(ticks)
        self.ax.plot_item.getAxis("right").setTicks(
            [[(value, _tick_label(value)) for value in values]]
        )

    def set_label(self, label: str, **kwargs: Any) -> None:
        self.ax.plot_item.setLabel("right", str(label), **_label_style_args(kwargs, default_size=8.0))


class Axes:
    def __init__(self, figure: "Figure", *, rect: list[float] | None = None) -> None:
        self.figure = figure
        self.rect = rect
        self.widget = pg.PlotWidget(parent=figure.widget)
        self.widget.setBackground(_color("#ffffff"))
        self.widget.setMinimumSize(1, 1)
        self.widget.setSizePolicy(
            QtWidgets.QSizePolicy.Policy.Expanding,
            QtWidgets.QSizePolicy.Policy.Expanding,
        )
        self.plot_item = self.widget.getPlotItem()
        self.plot_item.setMenuEnabled(False)
        self.plot_item.hideButtons()
        view_box = self.plot_item.getViewBox()
        view_box.setMouseEnabled(x=False, y=False)
        view_box.setMenuEnabled(False)
        self.spines = {key: _Spine() for key in ("left", "right", "top", "bottom")}
        self.transData = _DataTransform(self)
        self.transAxes = object()
        self._xlim = (0.0, 1.0)
        self._ylim = (0.0, 1.0)
        self._major_ticks: dict[str, list[float] | None] = {"bottom": None, "left": None}
        self._minor_ticks: dict[str, list[float] | None] = {"bottom": None, "left": None}
        self._aspect_equal = False
        self._legend: pg.LegendItem | None = None
        self._legend_items: list[tuple[Any, str, dict[str, Any]]] = []
        self._button: QtWidgets.QPushButton | None = None
        self._grid_styles: dict[str, dict[str, Any]] = {}
        self._grid_items: list[Any] = []
        self._is_colorbar = False

    def clear(self) -> None:
        if self._legend is not None:
            try:
                scene = self._legend.scene()
                if scene is not None:
                    scene.removeItem(self._legend)
                self.plot_item.legend = None
            except Exception:
                pass
            self._legend = None
        self._clear_grid_items()
        self.plot_item.clear()
        self._legend_items.clear()
        self._grid_styles.clear()
        self._aspect_equal = False
        for axis_name in ("bottom", "left"):
            self._major_ticks[axis_name] = None
            self._minor_ticks[axis_name] = None
            self._reset_axis_ticks(axis_name)

    def set_facecolor(self, color: Any) -> None:
        self.widget.setBackground(_color(color))

    def set_title(self, title: str, **kwargs: Any) -> None:
        args = _label_style_args(kwargs, default_size=11.0)
        loc = str(kwargs.get("loc", "center")).lower()
        if loc in {"left", "center", "right"}:
            args["justify"] = loc
        self.plot_item.setTitle(str(title), **args)

    def set_xlabel(self, label: str, **kwargs: Any) -> None:
        self.plot_item.setLabel("bottom", str(label), **_label_style_args(kwargs, default_size=9.0))

    def set_ylabel(self, label: str, **kwargs: Any) -> None:
        self.plot_item.setLabel("left", str(label), **_label_style_args(kwargs, default_size=9.0))

    def set_xlim(self, left: float, right: float | None = None) -> None:
        if right is None:
            left, right = left  # type: ignore[misc]
        self._xlim = (float(left), float(right))
        self.plot_item.setXRange(self._xlim[0], self._xlim[1], padding=0)
        self._refresh_grid()

    def set_ylim(self, bottom: float, top: float | None = None) -> None:
        if top is None:
            bottom, top = bottom  # type: ignore[misc]
        self._ylim = (float(bottom), float(top))
        self.plot_item.setYRange(self._ylim[0], self._ylim[1], padding=0)
        self._refresh_grid()

    def get_xlim(self) -> tuple[float, float]:
        return self._xlim

    def get_ylim(self) -> tuple[float, float]:
        return self._ylim

    def set_aspect(self, aspect: str | float, **_: Any) -> None:
        self._aspect_equal = aspect == "equal"
        self.plot_item.getViewBox().setAspectLocked(self._aspect_equal)
        self.figure.sync_equal_axis_layout()

    def grid(
        self,
        visible: bool = True,
        which: str | None = None,
        alpha: float | None = None,
        **kwargs: Any,
    ) -> None:
        targets = ["major", "minor"] if which == "both" else [which or "major"]
        for target in targets:
            if visible:
                self._grid_styles[target] = {
                    "color": kwargs.get("color"),
                    "linewidth": kwargs.get("linewidth") or kwargs.get("lw"),
                    "alpha": 0.25 if alpha is None else alpha,
                }
            else:
                self._grid_styles.pop(target, None)
        self._refresh_grid()

    def _clear_grid_items(self) -> None:
        for item in self._grid_items:
            try:
                self.plot_item.removeItem(item)
            except Exception:
                pass
        self._grid_items.clear()

    def _refresh_grid(self) -> None:
        if not hasattr(self, "_grid_items"):
            return
        self._clear_grid_items()
        if not self._grid_styles:
            self.plot_item.showGrid(x=False, y=False)
            return
        has_manual_ticks = any(
            self._major_ticks.get(axis_name) is not None
            or self._minor_ticks.get(axis_name) is not None
            for axis_name in ("bottom", "left")
        )
        if not has_manual_ticks:
            style = self._grid_styles.get("major") or next(iter(self._grid_styles.values()))
            self.plot_item.showGrid(x=True, y=True, alpha=float(style.get("alpha", 0.25)))
            return
        self.plot_item.showGrid(x=False, y=False)
        for level, ticks_by_axis in (
            ("major", self._major_ticks),
            ("minor", self._minor_ticks),
        ):
            style = self._grid_styles.get(level)
            if style is None:
                continue
            pen = _pen(
                style.get("color"),
                width=style.get("linewidth"),
                alpha=style.get("alpha"),
            )
            for value in ticks_by_axis.get("bottom") or []:
                item = pg.InfiniteLine(pos=float(value), angle=90, pen=pen, movable=False)
                item.setZValue(-100.0 if level == "major" else -110.0)
                item.setAcceptedMouseButtons(QtCore.Qt.MouseButton.NoButton)
                item.setAcceptHoverEvents(False)
                self.plot_item.addItem(item)
                self._grid_items.append(item)
            for value in ticks_by_axis.get("left") or []:
                item = pg.InfiniteLine(pos=float(value), angle=0, pen=pen, movable=False)
                item.setZValue(-100.0 if level == "major" else -110.0)
                item.setAcceptedMouseButtons(QtCore.Qt.MouseButton.NoButton)
                item.setAcceptHoverEvents(False)
                self.plot_item.addItem(item)
                self._grid_items.append(item)

    def minorticks_on(self) -> None:
        return

    def tick_params(self, **kwargs: Any) -> None:
        color = kwargs.get("colors")
        width = kwargs.get("width")
        length = kwargs.get("length")
        tick_font = _font(kwargs.get("labelsize"))
        if color or width is not None:
            pen = _pen(color or "#000000", width=width)
            for axis_name in ("left", "bottom", "right"):
                self.plot_item.getAxis(axis_name).setPen(pen)
                self.plot_item.getAxis(axis_name).setTextPen(pen)
        if tick_font is not None:
            for axis_name in ("left", "bottom", "right"):
                self.plot_item.getAxis(axis_name).setStyle(tickFont=tick_font)
        if length is not None:
            try:
                tick_length = int(round(float(length)))
            except Exception:
                tick_length = 0
            if tick_length > 0:
                for axis_name in ("left", "bottom", "right"):
                    self.plot_item.getAxis(axis_name).setStyle(tickLength=tick_length)

    def _reset_axis_ticks(self, axis_name: str) -> None:
        axis = self.plot_item.getAxis(axis_name)
        try:
            axis.setTicks(None)
        except Exception:
            return

    def _apply_axis_ticks(self, axis_name: str) -> None:
        major = self._major_ticks[axis_name]
        minor = self._minor_ticks[axis_name]
        if major is None and minor is None:
            self._reset_axis_ticks(axis_name)
            return
        levels: list[list[tuple[float, str]]] = []
        if major is not None:
            levels.append([(value, _tick_label(value)) for value in major])
        if minor is not None:
                levels.append([(value, "") for value in minor])
        self.plot_item.getAxis(axis_name).setTicks(levels)

    def _expand_limits_to_ticks(self, axis_name: str, ticks: list[float]) -> None:
        finite = [float(value) for value in ticks if np.isfinite(value)]
        if not finite:
            return
        low = min(finite)
        high = max(finite)
        if axis_name == "bottom":
            current_low, current_high = self._xlim
            if low < current_low or high > current_high:
                self.set_xlim(min(current_low, low), max(current_high, high))
        elif axis_name == "left":
            current_low, current_high = self._ylim
            if low < current_low or high > current_high:
                self.set_ylim(min(current_low, low), max(current_high, high))

    def set_xticks(self, ticks: Any, **kwargs: Any) -> None:
        axis_name = "bottom"
        if kwargs.get("minor"):
            self._minor_ticks[axis_name] = _tick_values(ticks)
        else:
            values = _tick_values(ticks)
            self._major_ticks[axis_name] = values
            self._expand_limits_to_ticks(axis_name, values)
        self._apply_axis_ticks(axis_name)
        self._refresh_grid()
        if self._aspect_equal:
            self.figure.sync_equal_axis_layout()

    def set_yticks(self, ticks: Any, **kwargs: Any) -> None:
        axis_name = "left"
        if kwargs.get("minor"):
            self._minor_ticks[axis_name] = _tick_values(ticks)
        else:
            values = _tick_values(ticks)
            self._major_ticks[axis_name] = values
            self._expand_limits_to_ticks(axis_name, values)
        self._apply_axis_ticks(axis_name)
        self._refresh_grid()
        if self._aspect_equal:
            self.figure.sync_equal_axis_layout()

    def plot(self, x: Any, y: Any = None, **kwargs: Any) -> list[_Artist]:
        if y is None:
            y = x
            x = np.arange(len(y))
        label = kwargs.get("label")
        if label == "_nolegend_":
            label = None
        item = self.plot_item.plot(
            np.asarray(x, dtype=float),
            np.asarray(y, dtype=float),
            pen=_pen(
                kwargs.get("color"),
                width=kwargs.get("linewidth") or kwargs.get("lw"),
                alpha=kwargs.get("alpha"),
                linestyle=kwargs.get("linestyle"),
            ),
            name=label,
        )
        if label:
            self._legend_items.append((item, str(label), {"kind": "line"}))
        return [_Artist(item)]

    def scatter(self, x: Any, y: Any, **kwargs: Any) -> _ScatterArtist:
        size = kwargs.get("s", 28)
        marker = str(kwargs.get("marker", "o"))
        symbol = {"x": "x", "+": "+", "o": "o", "^": "t", "s": "s", "*": "star", "D": "d", "d": "d"}.get(
            marker,
            "o",
        )
        marker_scale = 1.55
        if marker in {"D", "d"}:
            marker_scale = 1.9
        elif marker in {"*", "x", "+"}:
            marker_scale = 1.35
        color = (
            kwargs.get("color")
            or kwargs.get("c")
            or kwargs.get("facecolor")
            or kwargs.get("facecolors")
            or "#000000"
        )
        edge = kwargs.get("edgecolors") or kwargs.get("edgecolor") or color
        label = kwargs.get("label")
        if label == "_nolegend_":
            label = None
        marker_size = max(3.0, float(np.asarray(size, dtype=float).ravel()[0]) ** 0.5 * marker_scale)
        brush = _brush(color, alpha=kwargs.get("alpha"))
        pen = _pen(edge, width=kwargs.get("linewidths") or kwargs.get("linewidth") or 1.0)
        item = pg.ScatterPlotItem(
            x=np.asarray(x, dtype=float),
            y=np.asarray(y, dtype=float),
            size=marker_size,
            symbol=symbol,
            brush=brush,
            pen=pen,
            name=label,
        )
        self.plot_item.addItem(item)
        if label:
            self._legend_items.append(
                (
                    item,
                    str(label),
                    {
                        "kind": "scatter",
                        "size": marker_size,
                        "symbol": symbol,
                        "brush": brush,
                        "pen": pen,
                    },
                )
            )
        return _ScatterArtist(item, marker_scale=marker_scale, size=size)

    def axvline(self, x: float, **kwargs: Any) -> _Artist:
        pen = _pen(
            kwargs.get("color"),
            width=kwargs.get("linewidth"),
            alpha=kwargs.get("alpha"),
            linestyle=kwargs.get("linestyle"),
        )
        item = pg.InfiniteLine(
            pos=float(x),
            angle=90,
            pen=pen,
        )
        self.plot_item.addItem(item)
        label = kwargs.get("label")
        if label and label != "_nolegend_":
            self._legend_items.append((pg.PlotDataItem([0, 1], [0, 0], pen=pen), str(label), {"kind": "line"}))
        return _Artist(item)

    def axhline(self, y: float, **kwargs: Any) -> _Artist:
        pen = _pen(
            kwargs.get("color"),
            width=kwargs.get("linewidth"),
            alpha=kwargs.get("alpha"),
            linestyle=kwargs.get("linestyle"),
        )
        item = pg.InfiniteLine(
            pos=float(y),
            angle=0,
            pen=pen,
        )
        self.plot_item.addItem(item)
        label = kwargs.get("label")
        if label and label != "_nolegend_":
            self._legend_items.append((pg.PlotDataItem([0, 1], [0, 0], pen=pen), str(label), {"kind": "line"}))
        return _Artist(item)

    def axvspan(self, xmin: float, xmax: float, **kwargs: Any) -> _Artist:
        y0, y1 = self._ylim
        rect = QtWidgets.QGraphicsRectItem(float(xmin), y0, float(xmax) - float(xmin), y1 - y0)
        rect.setPen(QtGui.QPen(QtCore.Qt.PenStyle.NoPen))
        rect.setBrush(_brush(kwargs.get("color"), alpha=kwargs.get("alpha")))
        zorder = kwargs.get("zorder")
        rect.setZValue(float(zorder) if zorder is not None else -10.0)
        self.plot_item.addItem(rect)
        return _Artist(rect)

    def text(self, x: float, y: float, text: str, transform: Any = None, **kwargs: Any) -> _TextArtist:
        color = kwargs.get("color") or "#000000"
        bbox = kwargs.get("bbox")
        border, fill = _bbox_pen_brush(bbox)
        item = pg.TextItem(
            str(text),
            color=_color(color),
            anchor=_text_anchor(kwargs.get("ha"), kwargs.get("va")),
            border=border,
            fill=fill,
        )
        _set_text_margin(item, 1.0 if bbox is not None else 0.0)
        font = _font(kwargs.get("fontsize"), kwargs.get("fontweight") or kwargs.get("weight"))
        if font is not None:
            item.setFont(font)
        if kwargs.get("rotation") is not None:
            try:
                item.setRotation(float(kwargs["rotation"]))
            except Exception:
                pass
        if transform is self.transAxes:
            xr = self._xlim[0] + float(x) * (self._xlim[1] - self._xlim[0])
            yr = self._ylim[0] + float(y) * (self._ylim[1] - self._ylim[0])
        else:
            xr, yr = float(x), float(y)
        item.setPos(xr, yr)
        self.plot_item.addItem(item)
        _apply_bbox_text_scale(
            item,
            str(text),
            kwargs.get("fontsize"),
            bbox,
            kwargs.get("rotation"),
        )
        return _TextArtist(
            item,
            xr,
            yr,
            axes=self,
            ha=kwargs.get("ha"),
            va=kwargs.get("va"),
        )

    def annotate(self, text: str, xy: tuple[float, float], **kwargs: Any) -> _TextArtist:
        xytext = kwargs.get("xytext", xy)
        textcoords = kwargs.get("textcoords")
        if textcoords is self.transAxes:
            artist = self.text(
                float(xytext[0]),
                float(xytext[1]),
                text,
                transform=self.transAxes,
                **{key: value for key, value in kwargs.items() if key not in {"xytext", "textcoords"}},
            )
        elif textcoords == "offset points":
            artist = self.text(
                float(xy[0]),
                float(xy[1]),
                text,
                **{key: value for key, value in kwargs.items() if key not in {"xytext", "textcoords"}},
            )
            artist._offset_units = "offset points"
            artist.set_position((float(xytext[0]), float(xytext[1])))
        else:
            artist = self.text(
                float(xy[0]),
                float(xy[1]),
                text,
                **{key: value for key, value in kwargs.items() if key not in {"xytext", "textcoords"}},
            )
        if textcoords is self.transAxes:
            artist._xy = (float(xy[0]), float(xy[1]))
        else:
            artist.xy = (float(xy[0]), float(xy[1]))
        return artist

    def imshow(self, data: Any, **kwargs: Any) -> _ImageArtist:
        array = np.asarray(data, dtype=float)
        item = pg.ImageItem(array.T)
        cmap_name = kwargs.get("cmap")
        if cmap_name:
            try:
                cmap = pg.colormap.get(str(cmap_name))
                item.setLookupTable(cmap.getLookupTable(nPts=256))
            except Exception:
                pass
        levels = None
        if kwargs.get("vmin") is not None and kwargs.get("vmax") is not None:
            levels = (float(kwargs["vmin"]), float(kwargs["vmax"]))
            item.setLevels(levels)
        extent = kwargs.get("extent")
        if extent is not None:
            left, right, bottom, top = map(float, extent)
            item.setRect(QtCore.QRectF(left, bottom, right - left, top - bottom))
            self.set_xlim(left, right)
            self.set_ylim(bottom, top)
        self.plot_item.addItem(item)
        return _ImageArtist(item, levels)

    def _legend_anchor(self, loc: str) -> tuple[tuple[int, int], tuple[int, int], tuple[int, int]]:
        normalized = loc.replace("_", " ").lower()
        mapping = {
            "upper right": ((1, 0), (1, 0), (-8, 8)),
            "upper left": ((0, 0), (0, 0), (8, 8)),
            "lower right": ((1, 1), (1, 1), (-8, -8)),
            "lower left": ((0, 1), (0, 1), (8, -8)),
            "center right": ((1, 0), (1, 0), (-8, 36)),
            "best": ((1, 0), (1, 0), (-8, 8)),
        }
        return mapping.get(normalized, mapping["upper right"])

    def legend(self, **kwargs: Any) -> _Legend:
        if self._legend is not None:
            try:
                scene = self._legend.scene()
                if scene is not None:
                    scene.removeItem(self._legend)
                self.plot_item.legend = None
            except Exception:
                pass
            self._legend = None
        if self._legend_items:
            legend = self.plot_item.addLegend(offset=(0, 0))
            self._legend = legend
            try:
                legend.setContentsMargins(0, 0, 0, 0)
                legend.layout.setContentsMargins(0, 0, 0, 0)
                legend.layout.setSpacing(0)
                legend.layout.setHorizontalSpacing(1)
                legend.layout.setVerticalSpacing(0)
            except Exception:
                pass
            fontsize = kwargs.get("fontsize")
            if fontsize is not None:
                try:
                    legend.setLabelTextSize(f"{float(fontsize):g}pt")
                except Exception:
                    pass
            try:
                markerscale = float(kwargs.get("markerscale", 1.0))
            except Exception:
                markerscale = 1.0
            for item, label, meta in self._legend_items:
                legend_item = item
                if meta.get("kind") == "scatter":
                    legend_item = pg.ScatterPlotItem(
                        x=[0.0],
                        y=[0.0],
                        size=max(3.0, float(meta.get("size", 6.0)) * markerscale),
                        symbol=meta.get("symbol", "o"),
                        brush=meta.get("brush"),
                        pen=meta.get("pen"),
                    )
                try:
                    legend.addItem(legend_item, label)
                except Exception:
                    pass
            labels = [label for _item, label, _meta in self._legend_items]
            item_anchor, parent_anchor, offset = self._legend_anchor(str(kwargs.get("loc", "upper right")))
            if _uses_short_ascii_legend(labels):
                legend.setScale(0.66)
            legend.anchor(item_anchor, parent_anchor, offset=offset)
            if not _uses_short_ascii_legend(labels):
                legend.setTransform(QtGui.QTransform.fromScale(1.0, 0.875), True)
            return _Legend(legend)
        return _Legend()

    def add_patch(self, patch: Rectangle) -> _Artist:
        x, y = patch.xy
        rect = QtWidgets.QGraphicsRectItem(float(x), float(y), float(patch.width), float(patch.height))
        rect.setPen(
            _pen(
                patch.kwargs.get("edgecolor"),
                width=patch.kwargs.get("linewidth"),
                alpha=patch.kwargs.get("alpha"),
                linestyle=patch.kwargs.get("linestyle"),
            )
        )
        facecolor = patch.kwargs.get("facecolor")
        if patch.kwargs.get("fill") is False or facecolor is None or _is_no_color(facecolor):
            rect.setBrush(QtGui.QBrush(QtCore.Qt.BrushStyle.NoBrush))
        else:
            rect.setBrush(_brush(facecolor, alpha=patch.kwargs.get("alpha")))
        self.plot_item.addItem(rect)
        return _Artist(rect)


class Figure:
    def __init__(self, figsize: tuple[float, float] = (4.0, 3.0), dpi: int = 100) -> None:
        self.figsize = figsize
        self.dpi = dpi
        self.widget = QtWidgets.QWidget()
        self.layout = QtWidgets.QGridLayout(self.widget)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setSpacing(0)
        self.axes: list[Axes] = []
        self._next_overlay_row = 0
        self._subplot_adjust: dict[str, float] | None = None

    def set_facecolor(self, color: Any) -> None:
        self.widget.setStyleSheet(f"background-color: {_color(color).name()};")

    def subplots_adjust(self, **kwargs: Any) -> None:
        current = self._subplot_adjust or {
            "left": 0.125,
            "right": 0.9,
            "bottom": 0.11,
            "top": 0.88,
        }
        self._subplot_adjust = {
            **current,
            **{key: float(value) for key, value in kwargs.items() if value is not None},
        }
        self.sync_equal_axis_layout()

    def _subplot_margins(self, width: int, height: int) -> tuple[int, int, int, int]:
        if self._subplot_adjust is None:
            self.layout.setContentsMargins(0, 0, 0, 0)
            return (0, 0, 0, 0)
        has_equal_axis = any(axis._aspect_equal and axis.rect is None for axis in self.axes)
        if width < 500 or height < 350:
            if has_equal_axis:
                self.layout.setContentsMargins(0, 0, 0, 0)
                return (0, 0, 0, 0)
            self.layout.setContentsMargins(*_COMPACT_SUBPLOT_MARGINS)
            return _COMPACT_SUBPLOT_MARGINS
        left = max(0.0, min(1.0, self._subplot_adjust.get("left", 0.125)))
        right = max(left, min(1.0, self._subplot_adjust.get("right", 0.9)))
        bottom = max(0.0, min(1.0, self._subplot_adjust.get("bottom", 0.11)))
        top = max(bottom, min(1.0, self._subplot_adjust.get("top", 0.88)))
        left_scale = (
            _LARGE_SUBPLOT_LEFT_MARGIN_SCALE
            if not has_equal_axis and width >= 500 and height >= 350
            else _SUBPLOT_MARGIN_SCALE
        )
        margins = (
            int(round(width * left * left_scale)),
            int(round(height * (1.0 - top) * _SUBPLOT_MARGIN_SCALE)),
            int(round(width * (1.0 - right) * _SUBPLOT_MARGIN_SCALE)),
            int(round(height * bottom * _SUBPLOT_MARGIN_SCALE)),
        )
        self.layout.setContentsMargins(*margins)
        return margins

    def _apply_rect_axes_layout(self, width: int | None = None, height: int | None = None) -> None:
        rect_axes = [axis for axis in self.axes if axis.rect is not None]
        if not rect_axes:
            return
        width = int(width if width is not None and width > 0 else self.widget.width())
        height = int(height if height is not None and height > 0 else self.widget.height())
        if width <= 0:
            width = int(self.figsize[0] * self.dpi)
        if height <= 0:
            height = int(self.figsize[1] * self.dpi)
        for axis in rect_axes:
            rect = axis.rect or [0.0, 0.0, 1.0, 1.0]
            left = max(0.0, min(1.0, float(rect[0])))
            bottom = max(0.0, min(1.0, float(rect[1])))
            rect_width = max(0.0, min(1.0 - left, float(rect[2])))
            rect_height = max(0.0, min(1.0 - bottom, float(rect[3])))
            x = int(round(width * left))
            y = int(round(height * (1.0 - bottom - rect_height)))
            w = max(1, int(round(width * rect_width)))
            h = max(1, int(round(height * rect_height)))
            if rect_width < 0.08:
                w = max(w, 58, int(round(width * 0.065)))
            elif rect_width >= 0.2 and rect_height >= 0.2:
                bottom_margin = (
                    _WIDE_RECT_PLOT_BOTTOM_MARGIN
                    if self.figsize[0] >= 3.4
                    else _RECT_PLOT_BOTTOM_MARGIN
                )
                x -= _RECT_PLOT_LEFT_MARGIN
                y -= _RECT_PLOT_TOP_MARGIN
                w += _RECT_PLOT_LEFT_MARGIN + _RECT_PLOT_RIGHT_MARGIN
                h += _RECT_PLOT_TOP_MARGIN + bottom_margin
            if axis._is_colorbar:
                colorbar_min_width = (
                    _COMPACT_COLORBAR_MIN_WIDTH
                    if self.figsize[0] < 3.2
                    else _COLORBAR_MIN_WIDTH
                )
                colorbar_bottom = (
                    _WIDE_COLORBAR_BOTTOM_COMPENSATION
                    if self.figsize[0] >= 3.4
                    else _COLORBAR_BOTTOM_COMPENSATION
                )
                x += _COLORBAR_X_OFFSET
                y -= _COLORBAR_TOP_COMPENSATION
                w = max(w, colorbar_min_width)
                h += _COLORBAR_TOP_COMPENSATION + colorbar_bottom
            axis.widget.setGeometry(x, y, w, h)
            axis.widget.raise_()
            axis.widget.updateGeometry()

    def _subplot_position(self, args: tuple[Any, ...]) -> tuple[int, int, int, int]:
        if not args:
            return (0, 0, 1, 1)
        code = args[0]
        if isinstance(code, int) and 100 <= code <= 999:
            nrows = code // 100
            ncols = (code // 10) % 10
            index = code % 10
            if nrows > 0 and ncols > 0 and 1 <= index <= nrows * ncols:
                row = (index - 1) // ncols
                column = (index - 1) % ncols
                return (row, column, 1, 1)
        return (0, 0, 1, 1)

    def add_subplot(self, *args: Any, **_kwargs: Any) -> Axes:
        axis = Axes(self)
        self.axes.append(axis)
        row, column, row_span, column_span = self._subplot_position(args)
        self.layout.addWidget(axis.widget, row, column, row_span, column_span)
        return axis

    def tight_layout(self, *_args: Any, **_kwargs: Any) -> None:
        self.sync_equal_axis_layout()

    def add_axes(self, rect: list[float], **_kwargs: Any) -> Axes:
        axis = Axes(self, rect=rect)
        self.axes.append(axis)
        if float(rect[2]) < 0.08:
            width = max(58, int(round(self.figsize[0] * self.dpi * float(rect[2]) * 2.2)))
            axis.widget.setMinimumWidth(width)
            axis.widget.setMaximumWidth(16_777_215)
            axis.plot_item.hideAxis("bottom")
        axis.widget.show()
        self._apply_rect_axes_layout()
        return axis

    def sync_equal_axis_layout(
        self,
        available_w: int | None = None,
        available_h: int | None = None,
    ) -> None:
        parent = self.widget.parentWidget()
        if parent is None:
            for axis in self.axes:
                if axis.rect is None:
                    parent = axis.widget.parentWidget()
                    break
        if parent is None:
            return
        available_w = max(1, int(available_w if available_w is not None else parent.width()))
        available_h = max(1, int(available_h if available_h is not None else parent.height()))
        self._apply_rect_axes_layout(available_w, available_h)
        left_margin, top_margin, right_margin, bottom_margin = self._subplot_margins(
            available_w,
            available_h,
        )
        content_w = max(1, available_w - left_margin - right_margin)
        content_h = max(1, available_h - top_margin - bottom_margin)
        equal_axes = [axis for axis in self.axes if axis._aspect_equal and axis.rect is None]
        if len(equal_axes) != 1:
            plot_margins = (
                _LARGE_SUBPLOT_PLOT_MARGINS
                if content_w >= 500 and content_h >= 350
                else _COMPACT_SUBPLOT_PLOT_MARGINS
            )
            for axis in self.axes:
                if axis.rect is None:
                    axis.plot_item.layout.setContentsMargins(*plot_margins)
                    axis.widget.setMinimumSize(1, 1)
                    axis.widget.setMaximumSize(16_777_215, 16_777_215)
            return
        axis = equal_axes[0]
        if content_w < 160 or content_h < 120:
            axis.widget.setMinimumSize(1, 1)
            axis.widget.setMaximumSize(16_777_215, 16_777_215)
            return
        x_span = abs(axis._xlim[1] - axis._xlim[0])
        y_span = abs(axis._ylim[1] - axis._ylim[0])
        if x_span <= 0 or y_span <= 0:
            return
        ratio = x_span / y_span
        if content_w >= 500 and content_h >= 350:
            if ratio >= 1.2:
                width_scale = _LARGE_WIDE_EQUAL_ASPECT_WIDTH_SCALE
                height_scale = _LARGE_WIDE_EQUAL_ASPECT_HEIGHT_SCALE
                plot_margins = _LARGE_WIDE_EQUAL_ASPECT_MARGINS
            else:
                width_scale = _LARGE_EQUAL_ASPECT_WIDTH_SCALE
                height_scale = _LARGE_EQUAL_ASPECT_HEIGHT_SCALE
                plot_margins = _LARGE_EQUAL_ASPECT_MARGINS
        else:
            width_scale = (
                _WIDE_COMPACT_EQUAL_ASPECT_WIDTH_SCALE
                if ratio >= 1.2
                else _COMPACT_EQUAL_ASPECT_WIDTH_SCALE
            )
            height_scale = (
                _WIDE_COMPACT_EQUAL_ASPECT_HEIGHT_SCALE
                if ratio >= 1.2
                else _COMPACT_EQUAL_ASPECT_HEIGHT_SCALE
            )
            plot_margins = (
                _WIDE_COMPACT_EQUAL_ASPECT_MARGINS
                if ratio >= 1.2
                else _COMPACT_EQUAL_ASPECT_MARGINS
            )
        target_w_limit = content_w
        target_h_limit = content_h
        if content_w >= 500 and content_h >= 350 and ratio < 1.2:
            target_h_limit = min(
                available_h,
                int(round(content_h * _LARGE_EQUAL_ASPECT_HEIGHT_CAP_SCALE)),
            )
        target_w = max(80, min(target_w_limit, int(round(content_h * ratio * width_scale))))
        target_h = max(80, min(target_h_limit, int(round(content_w / ratio * height_scale))))
        # Keep an equal-aspect plot visually bounded without turning its current
        # render size into a hard window minimum.  ``setFixedSize`` made the
        # top-level window refuse the documented 1100x650 compact viewport
        # after the first layout pass, especially on high-DPI displays.
        axis.widget.setMinimumSize(1, 1)
        axis.widget.setMaximumSize(target_w, target_h)
        axis.widget.resize(target_w, target_h)
        axis.plot_item.layout.setContentsMargins(*plot_margins)
        axis.widget.updateGeometry()
        self.widget.layout().invalidate()
        self.layout.setAlignment(axis.widget, QtCore.Qt.AlignmentFlag.AlignCenter)
        axis.plot_item.setXRange(axis._xlim[0], axis._xlim[1], padding=0)
        axis.plot_item.setYRange(axis._ylim[0], axis._ylim[1], padding=0)

    def colorbar(self, image: _ImageArtist, cax: Axes) -> _Colorbar:
        cax._is_colorbar = True
        self._apply_rect_axes_layout()
        cax.clear()
        levels = image.levels or (0.0, 1.0)
        gradient = np.linspace(levels[0], levels[1], 128).reshape(128, 1)
        cax.imshow(
            gradient,
            extent=(0, 1, levels[0], levels[1]),
            vmin=levels[0],
            vmax=levels[1],
            cmap="magma",
        )
        span = max(abs(float(levels[1]) - float(levels[0])), 1.0)
        cax.set_ylim(float(levels[0]) - span * 0.035, float(levels[1]) + span * 0.035)
        cax.set_xticks([])
        cax.plot_item.hideAxis("left")
        cax.plot_item.showAxis("right")
        cax.plot_item.getAxis("right").setTicks(
            [[(float(value), _tick_label(float(value))) for value in np.linspace(levels[0], levels[1], 9)]]
        )
        return _Colorbar(cax)


class FigureCanvasQt(QtWidgets.QWidget):
    """Native Qt canvas with a small, temporary Tk geometry compatibility API.

    New callers should pass a ``QWidget`` as ``parent`` and add this canvas to a
    Qt layout normally.  ``master``, ``get_tk_widget()``, ``grid()`` and
    ``pack()`` remain available so the legacy GUI can migrate incrementally.
    """

    _winfo_class = "Canvas"

    def __init__(
        self,
        figure: Figure,
        parent: Any = None,
        *,
        master: Any | None = None,
    ) -> None:
        if parent is not None and master is not None and parent is not master:
            raise TypeError("pass either parent or master, not both")
        owner = parent if parent is not None else master
        qt_parent = _qt_parent(owner)
        if owner is not None and qt_parent is None:
            raise TypeError("parent must be a QWidget or expose a QWidget through '_qt'")
        super().__init__(qt_parent)
        self.figure = figure
        self._qt = self
        self._qt._tk_wrapper = self  # type: ignore[attr-defined]
        self._parent = owner
        self._children: list[Any] = []
        self._grid_layout = None
        self._pack_layout = None
        self._layout_kind = None
        self._padding = (0, 0, 0, 0)
        self._bindings: list[Any] = []
        self._callbacks: dict[str, dict[int, Callable[[Any], Any]]] = {}
        self._next_callback_id = 1
        self._event_axis_by_object: dict[QtCore.QObject, Axes] = {}
        self._captured_axis: Axes | None = None
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(figure.widget)
        width = int(figure.figsize[0] * figure.dpi)
        height = int(figure.figsize[1] * figure.dpi)
        self.resize(width, height)
        self.setBaseSize(width, height)
        self.setMinimumSize(1, 1)
        self.setSizePolicy(
            QtWidgets.QSizePolicy.Policy.Expanding,
            QtWidgets.QSizePolicy.Policy.Expanding,
        )
        figure.widget.setMinimumSize(1, 1)
        figure.widget.setSizePolicy(
            QtWidgets.QSizePolicy.Policy.Expanding,
            QtWidgets.QSizePolicy.Policy.Expanding,
        )
        self.setMouseTracking(True)
        self.installEventFilter(self)
        figure.widget.setMouseTracking(True)
        figure.widget.installEventFilter(self)
        self._install_axis_event_filters()
        if owner is not None and hasattr(owner, "_children"):
            owner._children.append(self)  # type: ignore[arg-type]

    def get_tk_widget(self) -> "FigureCanvasQt":
        return self

    def grab_pointer(self, axis: Axes | None = None) -> None:
        """Keep delivering pointer events until release.

        This mirrors pointer capture on the web: direct manipulation remains
        continuous even when the cursor temporarily leaves the plot surface.
        Repeated calls simply retarget the capture, so the interaction stays
        interruptible.
        """

        self._captured_axis = axis
        self.grabMouse()

    def release_pointer(self) -> None:
        """Release a previously captured pointer without raising on teardown."""

        self._captured_axis = None
        if QtWidgets.QWidget.mouseGrabber() is self:
            self.releaseMouse()

    def _emit_pointer_cancel(self) -> None:
        """Notify interaction owners when the OS revokes mouse capture."""

        axis = self._captured_axis
        if axis is None:
            return
        self._captured_axis = None
        event = SimpleNamespace(
            canvas=self,
            inaxes=axis,
            x=None,
            y=None,
            xdata=None,
            ydata=None,
            button=None,
        )
        for callback in list(self._callbacks.get("pointer_cancel_event", {}).values()):
            callback(event)

    def winfo_children(self) -> list[Any]:
        return list(self._children)

    def winfo_class(self) -> str:
        return self._winfo_class

    def winfo_x(self) -> int:
        return int(self.x())

    def winfo_y(self) -> int:
        return int(self.y())

    def winfo_rootx(self) -> int:
        return int(self.mapToGlobal(QtCore.QPoint(0, 0)).x())

    def winfo_rooty(self) -> int:
        return int(self.mapToGlobal(QtCore.QPoint(0, 0)).y())

    def winfo_screenwidth(self) -> int:
        screen = QtWidgets.QApplication.primaryScreen()
        return int(screen.geometry().width()) if screen is not None else 0

    def winfo_screenheight(self) -> int:
        screen = QtWidgets.QApplication.primaryScreen()
        return int(screen.geometry().height()) if screen is not None else 0

    def winfo_width(self) -> int:
        return int(self.width())

    def winfo_height(self) -> int:
        return int(self.height())

    def winfo_geometry(self) -> str:
        return f"{self.width()}x{self.height()}+{self.x()}+{self.y()}"

    def configure(self, **kwargs: Any) -> None:
        if "cursor" in kwargs:
            _set_cursor(self, kwargs.get("cursor"))
        bg = _as_color(kwargs.get("bg") or kwargs.get("background"))
        if bg:
            self.setStyleSheet(f"background-color: {bg};")
        if "width" in kwargs:
            self.resize(int(kwargs["width"]), self.height())
            self.setBaseSize(int(kwargs["width"]), self.baseSize().height())
        if "height" in kwargs:
            self.resize(self.width(), int(kwargs["height"]))
            self.setBaseSize(self.baseSize().width(), int(kwargs["height"]))

    config = configure

    def _compat_grid_layout(self) -> QtWidgets.QGridLayout:
        if self._parent is None:
            raise RuntimeError("grid() requires a parent; use a native Qt layout for new code")
        ensure_layout = getattr(self._parent, "_ensure_grid_layout", None)
        if callable(ensure_layout):
            layout = ensure_layout()
            if isinstance(layout, QtWidgets.QGridLayout):
                return layout
        parent = _qt_parent(self._parent)
        if parent is None:
            raise TypeError("grid() parent is not backed by QWidget")
        layout = parent.layout()
        if layout is None:
            layout = QtWidgets.QGridLayout(parent)
            layout.setContentsMargins(0, 0, 0, 0)
            layout.setSpacing(0)
        if not isinstance(layout, QtWidgets.QGridLayout):
            raise TypeError("grid() requires a QGridLayout; use layout.addWidget(canvas) instead")
        return layout

    def _compat_pack_layout(self, side: str | None) -> QtWidgets.QBoxLayout:
        if self._parent is None:
            raise RuntimeError("pack() requires a parent; use a native Qt layout for new code")
        ensure_layout = getattr(self._parent, "_ensure_pack_layout", None)
        if callable(ensure_layout):
            layout = ensure_layout(side)
            if isinstance(layout, QtWidgets.QBoxLayout):
                return layout
        parent = _qt_parent(self._parent)
        if parent is None:
            raise TypeError("pack() parent is not backed by QWidget")
        layout = parent.layout()
        if layout is None:
            if side in {"left", "right"}:
                layout = QtWidgets.QHBoxLayout(parent)
            else:
                layout = QtWidgets.QVBoxLayout(parent)
            layout.setContentsMargins(0, 0, 0, 0)
            layout.setSpacing(0)
        if not isinstance(layout, QtWidgets.QBoxLayout):
            raise TypeError("pack() requires a QBoxLayout; use layout.addWidget(canvas) instead")
        return layout

    def grid(
        self,
        row: int = 0,
        column: int = 0,
        rowspan: int = 1,
        columnspan: int = 1,
        sticky: str | None = None,
        padx: Any = None,
        pady: Any = None,
        **_kwargs: Any,
    ) -> None:
        """Place the canvas using the legacy Tk-style grid contract."""
        if self._parent is None:
            return
        layout = self._compat_grid_layout()
        pad_left, pad_right = _parse_pad_pair(padx)
        pad_top, pad_bottom = _parse_pad_pair(pady)
        if pad_left or pad_right:
            layout.setHorizontalSpacing(
                max(0, layout.horizontalSpacing(), pad_left + pad_right)
            )
        if pad_top or pad_bottom:
            layout.setVerticalSpacing(max(0, layout.verticalSpacing(), pad_top + pad_bottom))

        alignment = QtCore.Qt.AlignmentFlag(0)
        sticky = sticky or ""
        if "w" in sticky and "e" not in sticky:
            alignment |= QtCore.Qt.AlignmentFlag.AlignLeft
        elif "e" in sticky and "w" not in sticky:
            alignment |= QtCore.Qt.AlignmentFlag.AlignRight
        elif "w" not in sticky and "e" not in sticky:
            alignment |= QtCore.Qt.AlignmentFlag.AlignHCenter
        if "n" in sticky and "s" not in sticky:
            alignment |= QtCore.Qt.AlignmentFlag.AlignTop
        elif "s" in sticky and "n" not in sticky:
            alignment |= QtCore.Qt.AlignmentFlag.AlignBottom
        elif "n" not in sticky and "s" not in sticky:
            alignment |= QtCore.Qt.AlignmentFlag.AlignVCenter

        if alignment:
            layout.addWidget(self, row, column, rowspan, columnspan, alignment)
        else:
            layout.addWidget(self, row, column, rowspan, columnspan)

        parent = self._parent
        if hasattr(parent, "_grid_max_row"):
            parent._grid_max_row = max(parent._grid_max_row, row + rowspan - 1)
        if hasattr(parent, "_grid_max_column"):
            parent._grid_max_column = max(parent._grid_max_column, column + columnspan - 1)
        sync_grid = getattr(parent, "_sync_grid_slack", None)
        if callable(sync_grid):
            sync_grid()

    def pack(
        self,
        side: str | None = None,
        fill: str | None = None,
        expand: bool = False,
        padx: Any = None,
        pady: Any = None,
        anchor: str | None = None,
        **_kwargs: Any,
    ) -> None:
        """Place the canvas using the legacy Tk-style pack contract."""
        del anchor  # Kept for signature compatibility; the prior adapter ignored it too.
        if self._parent is None:
            return
        layout = self._compat_pack_layout(side)
        stretch = 1 if expand else 0
        pad_left, pad_right = _parse_pad_pair(padx)
        pad_top, pad_bottom = _parse_pad_pair(pady)
        is_horizontal = layout.direction() in {
            QtWidgets.QBoxLayout.Direction.LeftToRight,
            QtWidgets.QBoxLayout.Direction.RightToLeft,
        }
        before_pad = pad_left if is_horizontal else pad_top
        after_pad = pad_right if is_horizontal else pad_bottom
        if before_pad:
            layout.addSpacing(before_pad)
        alignment = QtCore.Qt.AlignmentFlag(0)
        if is_horizontal and fill != "both":
            alignment |= QtCore.Qt.AlignmentFlag.AlignVCenter
        elif not is_horizontal and fill not in {"x", "both"}:
            alignment |= QtCore.Qt.AlignmentFlag.AlignHCenter
        if alignment:
            layout.addWidget(self, stretch, alignment)
        else:
            layout.addWidget(self, stretch)
        if after_pad:
            layout.addSpacing(after_pad)

        if fill in {"x", "both"} or expand:
            if is_horizontal:
                horizontal_policy = QtWidgets.QSizePolicy.Policy.Expanding
                vertical_policy = (
                    QtWidgets.QSizePolicy.Policy.Expanding
                    if fill == "both"
                    else QtWidgets.QSizePolicy.Policy.Preferred
                )
            else:
                horizontal_policy = (
                    QtWidgets.QSizePolicy.Policy.Expanding
                    if fill in {"x", "both"}
                    else QtWidgets.QSizePolicy.Policy.Preferred
                )
                vertical_policy = (
                    QtWidgets.QSizePolicy.Policy.Expanding
                    if expand or fill == "both"
                    else QtWidgets.QSizePolicy.Policy.Preferred
                )
            self.setSizePolicy(horizontal_policy, vertical_policy)

    def draw_idle(self) -> None:
        self.update()

    def draw(self) -> None:
        self.update()

    def resizeEvent(self, event: QtGui.QResizeEvent) -> None:  # noqa: N802
        self._install_axis_event_filters()
        self.figure.sync_equal_axis_layout(event.size().width(), event.size().height())
        super().resizeEvent(event)

    def mpl_connect(self, event_name: str, callback: Callable[[Any], Any]) -> int:
        callback_id = self._next_callback_id
        self._next_callback_id += 1
        self._callbacks.setdefault(event_name, {})[callback_id] = callback
        return callback_id

    def mpl_disconnect(self, callback_id: int) -> None:
        for callbacks in self._callbacks.values():
            callbacks.pop(callback_id, None)

    def _install_axis_event_filters(self) -> None:
        for axis in self.figure.axes:
            axis.widget.setMouseTracking(True)
            sources: list[QtCore.QObject] = [axis.widget]
            viewport = axis.widget.viewport() if hasattr(axis.widget, "viewport") else None
            if viewport is not None:
                viewport.setMouseTracking(True)
                sources.append(viewport)
            scene = axis.widget.scene() if hasattr(axis.widget, "scene") else None
            if scene is not None:
                sources.append(scene)
            for source in sources:
                if source in self._event_axis_by_object:
                    continue
                source.installEventFilter(self)
                self._event_axis_by_object[source] = axis

    def _axis_at(
        self,
        scene_pos: QtCore.QPointF,
        preferred_axis: Axes | None = None,
    ) -> tuple[Axes | None, float | None, float | None]:
        if preferred_axis is not None:
            plot_item = preferred_axis.plot_item
            if plot_item.sceneBoundingRect().contains(scene_pos):
                point = plot_item.vb.mapSceneToView(scene_pos)
                return preferred_axis, float(point.x()), float(point.y())
        for axis in self.figure.axes:
            plot_item = axis.plot_item
            if plot_item.sceneBoundingRect().contains(scene_pos):
                point = plot_item.vb.mapSceneToView(scene_pos)
                return axis, float(point.x()), float(point.y())
        return None, None, None

    def _mouse_button(self, qt_event: Any) -> int | None:
        button = qt_event.button() if hasattr(qt_event, "button") else None
        if button == QtCore.Qt.MouseButton.LeftButton:
            return 1
        if button == QtCore.Qt.MouseButton.MiddleButton:
            return 2
        if button == QtCore.Qt.MouseButton.RightButton:
            return 3
        return None

    def _event_scene_pos(
        self,
        watched: QtCore.QObject | None,
        qt_event: Any,
        preferred_axis: Axes | None,
    ) -> QtCore.QPointF:
        if hasattr(qt_event, "scenePos"):
            return QtCore.QPointF(qt_event.scenePos())
        pos = qt_event.position() if hasattr(qt_event, "position") else qt_event.pos()
        point = pos.toPoint() if hasattr(pos, "toPoint") else QtCore.QPoint(int(pos.x()), int(pos.y()))
        if preferred_axis is not None and hasattr(preferred_axis.widget, "mapToScene"):
            if watched is preferred_axis.widget:
                return QtCore.QPointF(preferred_axis.widget.mapToScene(point))
            if isinstance(watched, QtWidgets.QWidget):
                global_pos = watched.mapToGlobal(point)
                local_pos = preferred_axis.widget.mapFromGlobal(global_pos)
                return QtCore.QPointF(preferred_axis.widget.mapToScene(local_pos))
        if isinstance(watched, QtWidgets.QWidget):
            global_pos = watched.mapToGlobal(point)
            for axis in self.figure.axes:
                if hasattr(axis.widget, "mapFromGlobal") and hasattr(axis.widget, "mapToScene"):
                    local_pos = axis.widget.mapFromGlobal(global_pos)
                    if axis.widget.rect().contains(local_pos):
                        return QtCore.QPointF(axis.widget.mapToScene(local_pos))
        return QtCore.QPointF(pos)

    def _emit(
        self,
        event_name: str,
        qt_event: Any,
        *,
        button: int | None = None,
        watched: QtCore.QObject | None = None,
    ) -> None:
        preferred_axis = (
            self._event_axis_by_object.get(watched)
            if watched is not None
            else None
        ) or self._captured_axis
        scene_pos = self._event_scene_pos(watched, qt_event, preferred_axis)
        axis, xdata, ydata = self._axis_at(scene_pos, preferred_axis)
        event = SimpleNamespace(
            canvas=self,
            inaxes=axis,
            x=float(scene_pos.x()),
            y=float(scene_pos.y()),
            xdata=xdata,
            ydata=ydata,
            button=button,
        )
        for callback in list(self._callbacks.get(event_name, {}).values()):
            callback(event)

    def eventFilter(self, watched: QtCore.QObject, event: QtCore.QEvent) -> bool:
        is_axis_source = watched in self._event_axis_by_object
        if event.type() in {
            QtCore.QEvent.Type.GraphicsSceneMouseMove,
            QtCore.QEvent.Type.MouseMove,
        }:
            if event.type() == QtCore.QEvent.Type.GraphicsSceneMouseMove or not is_axis_source:
                self._emit("motion_notify_event", event, watched=watched)
                return True
        elif event.type() in {
            QtCore.QEvent.Type.GraphicsSceneMousePress,
            QtCore.QEvent.Type.MouseButtonPress,
        }:
            if event.type() == QtCore.QEvent.Type.GraphicsSceneMousePress or not is_axis_source:
                self._emit("button_press_event", event, button=self._mouse_button(event), watched=watched)
                return True
        elif event.type() in {
            QtCore.QEvent.Type.GraphicsSceneMouseRelease,
            QtCore.QEvent.Type.MouseButtonRelease,
        }:
            if event.type() == QtCore.QEvent.Type.GraphicsSceneMouseRelease or not is_axis_source:
                self._emit("button_release_event", event, button=self._mouse_button(event), watched=watched)
                return True
        elif event.type() == QtCore.QEvent.Type.Leave:
            for callback in list(self._callbacks.get("figure_leave_event", {}).values()):
                callback(SimpleNamespace(canvas=self, inaxes=None, xdata=None, ydata=None, button=None))
        elif event.type() == QtCore.QEvent.Type.UngrabMouse:
            self._emit_pointer_cancel()
        return super().eventFilter(watched, event)

    def winfo_class(self) -> str:
        return self._winfo_class


# Transitional import compatibility.  New code should use FigureCanvasQt.
FigureCanvasTkAgg = FigureCanvasQt


class MplButton:
    def __init__(self, ax: Axes, label: str, color: Any = None, hovercolor: Any = None) -> None:
        self.ax = ax
        self.button = QtWidgets.QPushButton(label, ax.widget)
        self.button.setSizePolicy(
            QtWidgets.QSizePolicy.Policy.Expanding,
            QtWidgets.QSizePolicy.Policy.Expanding,
        )
        layout = QtWidgets.QVBoxLayout(ax.widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.button)
        if color:
            hover = _color(hovercolor or color).name()
            base = _color(color).name()
            self.button.setStyleSheet(
                f"QPushButton {{ background-color: {base}; "
                f"border: 1px solid {TOKENS.border}; "
                f"border-radius: {TOKENS.radius}px; }}"
                f"QPushButton:hover {{ background-color: {hover}; }}"
                f"QPushButton:pressed {{ background-color: {TOKENS.surface_pressed}; }}"
            )
        self.label = _LabelProxy(self.button.setText)

    def on_clicked(self, callback: Callable[[Any], Any]) -> int:
        self.button.clicked.connect(lambda _checked=False: callback(SimpleNamespace()))
        return 1
