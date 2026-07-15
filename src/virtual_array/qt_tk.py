from __future__ import annotations

import itertools
import re
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Callable

from PySide6 import QtCore, QtGui, QtWidgets

from .native_theme import TOKENS


class TclError(Exception):
    """Compatibility exception used by Tk-oriented GUI code."""


HORIZONTAL = "horizontal"
VERTICAL = "vertical"
LEFT = "left"
RIGHT = "right"
X = "x"
BOTH = "both"
WORD = "word"
SOLID = "solid"
END = "end"
DISABLED = "disabled"
NORMAL = "normal"


_DEFAULT_FONT_FAMILY = "Microsoft YaHei"
_ITEM_IDS = itertools.count(1)
_STYLE_CONFIGS: dict[str, dict[str, Any]] = {}
_STYLE_MAPS: dict[str, dict[str, list[tuple[str, Any]]]] = {}
_HIDDEN_NOTEBOOK_TABS: set[str] = set()
_OBJECT_IDS = itertools.count(1)


def _ensure_app() -> QtWidgets.QApplication:
    app = QtWidgets.QApplication.instance()
    if app is None:
        app = QtWidgets.QApplication(sys.argv[:1])
        app.setStyle("Fusion")
    return app


def _qt_parent(parent: Any) -> QtWidgets.QWidget | None:
    if parent is None:
        return None
    return getattr(parent, "_qt", None)


def _as_color(value: Any) -> str | None:
    if isinstance(value, str) and value:
        return value
    return None


def _parse_padding(value: Any) -> tuple[int, int, int, int]:
    if value is None:
        return (0, 0, 0, 0)
    if isinstance(value, int):
        return (value, value, value, value)
    if isinstance(value, tuple):
        if len(value) == 2:
            x, y = value
            return (int(x), int(y), int(x), int(y))
        if len(value) == 4:
            return tuple(int(part) for part in value)  # type: ignore[return-value]
    return (0, 0, 0, 0)


def _qt_button_text(value: Any) -> str:
    return str(value).replace("&", "&&")


def _parse_pad_pair(value: Any) -> tuple[int, int]:
    if value is None:
        return (0, 0)
    if isinstance(value, int):
        return (int(value), int(value))
    if isinstance(value, tuple):
        if len(value) == 2:
            return (int(value[0]), int(value[1]))
        if len(value) == 4:
            return (int(value[0]), int(value[2]))
    return (0, 0)


def _parse_geometry(value: str) -> tuple[int, int, int | None, int | None] | None:
    match = re.match(r"^(\d+)x(\d+)(?:([+-]\d+)([+-]\d+))?$", value)
    if not match:
        return None
    width = int(match.group(1))
    height = int(match.group(2))
    x = int(match.group(3)) if match.group(3) else None
    y = int(match.group(4)) if match.group(4) else None
    return width, height, x, y


def _screen_geometry_limit() -> QtCore.QSize | None:
    app = _ensure_app()
    screens = app.screens()
    if not screens:
        return None
    width = max(screen.availableGeometry().width() for screen in screens)
    height = max(screen.availableGeometry().height() for screen in screens)
    return QtCore.QSize(width, height)


def _tk_px(value: int | float) -> int:
    """Return Qt logical pixels.

    Qt already exposes device-independent logical coordinates when high-DPI
    scaling is enabled.  Dividing by ``devicePixelRatio`` a second time made
    the old compatibility UI shrink at 125%/150% Windows scaling (most
    noticeably the header chips).  Keeping the logical value lets Qt perform
    the only required conversion.
    """

    return max(1, int(round(float(value))))


def _scrollbar_fractions(scrollbar: QtWidgets.QScrollBar) -> tuple[float, float]:
    minimum = scrollbar.minimum()
    maximum = scrollbar.maximum()
    page = max(1, scrollbar.pageStep())
    span = max(1, maximum - minimum + page)
    first = (scrollbar.value() - minimum) / span
    last = (scrollbar.value() - minimum + page) / span
    return (max(0.0, min(1.0, first)), max(0.0, min(1.0, last)))


def _scrollbar_view(scrollbar: QtWidgets.QScrollBar, *args: Any) -> tuple[float, float] | None:
    if not args:
        return _scrollbar_fractions(scrollbar)
    command = args[0]
    if command == "moveto" and len(args) >= 2:
        try:
            fraction = float(args[1])
        except (TypeError, ValueError):
            return None
        span = scrollbar.maximum() - scrollbar.minimum()
        scrollbar.setValue(scrollbar.minimum() + int(round(span * fraction)))
        return None
    if command == "scroll" and len(args) >= 3:
        try:
            amount = int(args[1])
        except (TypeError, ValueError):
            return None
        unit = str(args[2])
        step = scrollbar.pageStep() if unit.startswith("page") else scrollbar.singleStep()
        scrollbar.setValue(scrollbar.value() + amount * max(1, step))
    return None


def _connect_scroll_command(
    scrollbar: QtWidgets.QScrollBar,
    command: Callable[..., Any] | None,
) -> None:
    if command is None:
        return
    owner = getattr(command, "__self__", None)
    if getattr(owner, "_winfo_class", None) == "TScrollbar" and hasattr(
        owner, "_attach_qt_scrollbar"
    ):
        owner._attach_qt_scrollbar(scrollbar)
        return

    def emit(*_args: Any) -> None:
        first, last = _scrollbar_fractions(scrollbar)
        command(first, last)

    refs = getattr(scrollbar, "_tk_scroll_callbacks", [])
    refs.append(emit)
    scrollbar._tk_scroll_callbacks = refs  # type: ignore[attr-defined]
    scrollbar.valueChanged.connect(emit)
    scrollbar.rangeChanged.connect(lambda *_args: emit())
    QtCore.QTimer.singleShot(0, emit)


def _sequence_to_key(sequence: str) -> tuple[str, str]:
    cleaned = sequence.strip("<>")
    parts = cleaned.split("-")
    key = parts[-1]
    modifiers = {part.lower() for part in parts[:-1]}
    qt_parts: list[str] = []
    if "control" in modifiers or "ctrl" in modifiers:
        qt_parts.append("Ctrl")
    if "shift" in modifiers:
        qt_parts.append("Shift")
    qt_key_map = {
        "Escape": "Esc",
        "Delete": "Del",
        "Left": "Left",
        "Right": "Right",
        "Up": "Up",
        "Down": "Down",
    }
    qt_key = qt_key_map.get(key, key.upper() if len(key) == 1 else key)
    qt_parts.append(qt_key)
    keysym = {
        "Esc": "Escape",
        "Del": "Delete",
    }.get(qt_key, key)
    return "+".join(qt_parts), keysym


def _cursor_shape(name: str | None) -> QtCore.Qt.CursorShape:
    if name in {"hand2", "pointinghand"}:
        return QtCore.Qt.CursorShape.PointingHandCursor
    if name in {"fleur", "size_all"}:
        return QtCore.Qt.CursorShape.SizeAllCursor
    if name in {"sb_h_double_arrow", "size_hor"}:
        return QtCore.Qt.CursorShape.SizeHorCursor
    if name in {"sb_v_double_arrow", "size_ver"}:
        return QtCore.Qt.CursorShape.SizeVerCursor
    if name in {"cross", "crosshair"}:
        return QtCore.Qt.CursorShape.CrossCursor
    return QtCore.Qt.CursorShape.ArrowCursor


def _set_cursor(widget: QtWidgets.QWidget, name: str | None) -> None:
    if name:
        widget.setCursor(QtGui.QCursor(_cursor_shape(name)))
    else:
        widget.unsetCursor()


def _qt_alignment(anchor: str | None = None, justify: str | None = None) -> QtCore.Qt.AlignmentFlag:
    anchor = (anchor or "").lower()
    justify = (justify or "").lower()
    alignment = QtCore.Qt.AlignmentFlag(0)
    if anchor in {"center", "c"} or justify == "center":
        alignment |= QtCore.Qt.AlignmentFlag.AlignHCenter
    elif "e" in anchor or justify == "right":
        alignment |= QtCore.Qt.AlignmentFlag.AlignRight
    elif "w" in anchor or justify == "left" or not anchor and not justify:
        alignment |= QtCore.Qt.AlignmentFlag.AlignLeft
    else:
        alignment |= QtCore.Qt.AlignmentFlag.AlignHCenter
    if "n" in anchor:
        alignment |= QtCore.Qt.AlignmentFlag.AlignTop
    elif "s" in anchor:
        alignment |= QtCore.Qt.AlignmentFlag.AlignBottom
    else:
        alignment |= QtCore.Qt.AlignmentFlag.AlignVCenter
    return alignment


def _style_chain(style_name: str | None, default_style: str) -> list[str]:
    chain = [default_style]
    if style_name and style_name != default_style:
        chain.append(style_name)
    return chain


def _merged_style(style_name: str | None, default_style: str) -> dict[str, Any]:
    merged: dict[str, Any] = {}
    for name in _style_chain(style_name, default_style):
        merged.update(_STYLE_CONFIGS.get(name, {}))
    return merged


def _merged_maps(style_name: str | None, default_style: str) -> dict[str, list[tuple[str, Any]]]:
    merged: dict[str, list[tuple[str, Any]]] = {}
    for name in _style_chain(style_name, default_style):
        for key, value in _STYLE_MAPS.get(name, {}).items():
            merged[key] = value
    return merged


def _font_rules(font: Any) -> list[str]:
    if not font:
        return []
    family = _DEFAULT_FONT_FAMILY
    size: int | None = None
    bold = False
    italic = False
    if isinstance(font, tuple):
        if font:
            family = str(font[0])
        if len(font) > 1:
            try:
                size = int(font[1])
            except (TypeError, ValueError):
                size = None
        for part in font[2:]:
            text = str(part).lower()
            bold = bold or "bold" in text
            italic = italic or "italic" in text
    elif isinstance(font, str):
        family = font
    if family.lower().startswith("tkdefaultfont"):
        family = _DEFAULT_FONT_FAMILY
    elif family.lower().startswith("tkfixedfont"):
        family = "Cascadia Mono"
    fallback_families = [
        family,
        "Microsoft YaHei",
        "SimHei",
        "Noto Sans CJK SC",
        "Segoe UI",
        "sans-serif",
    ]
    unique_families = list(dict.fromkeys(fallback_families))
    rules = [
        "font-family: "
        + ", ".join(
            name if name == "sans-serif" else f"\"{name}\""
            for name in unique_families
        )
        + ";"
    ]
    if size is not None:
        rules.append(f"font-size: {size}pt;")
    if bold:
        rules.append("font-weight: 700;")
    if italic:
        rules.append("font-style: italic;")
    return rules


def _font_from_config(font: Any) -> QtGui.QFont | None:
    if not font:
        return None
    family = _DEFAULT_FONT_FAMILY
    size: int | None = None
    bold = False
    italic = False
    if isinstance(font, tuple):
        if font:
            family = str(font[0])
        if len(font) > 1:
            try:
                size = int(font[1])
            except (TypeError, ValueError):
                size = None
        for part in font[2:]:
            text = str(part).lower()
            bold = bold or "bold" in text
            italic = italic or "italic" in text
    elif isinstance(font, str):
        family = font
    if family.lower().startswith("tkdefaultfont"):
        family = _DEFAULT_FONT_FAMILY
    elif family.lower().startswith("tkfixedfont"):
        family = "Cascadia Mono"
    qt_font = QtGui.QFont(family)
    if hasattr(qt_font, "setFamilies"):
        qt_font.setFamilies(
            [
                family,
                "Microsoft YaHei",
                "SimHei",
                "Noto Sans CJK SC",
                "Segoe UI",
            ]
        )
    if size is not None:
        qt_font.setPointSize(size)
    qt_font.setBold(bold)
    qt_font.setItalic(italic)
    return qt_font


def _font_config_with_size(font: Any, size: int) -> Any:
    if isinstance(font, tuple):
        if not font:
            return (_DEFAULT_FONT_FAMILY, size)
        return (font[0], size, *font[2:])
    if isinstance(font, str):
        return (font, size)
    return (_DEFAULT_FONT_FAMILY, size)


def _font_family_name(font: Any) -> str:
    if isinstance(font, tuple) and font:
        return str(font[0])
    if isinstance(font, str):
        return font
    return ""


def _uses_tk_default_font(config: dict[str, Any]) -> bool:
    return _font_family_name(config.get("font")).lower().startswith("tkdefaultfont")


def _padding_rule(value: Any) -> str | None:
    left, top, right, bottom = _parse_padding(value)
    if left == top == right == bottom == 0:
        return None
    return f"padding: {top}px {right}px {bottom}px {left}px;"


def _text_width_px(width: int | None, *, average_px: int | float = 9) -> int | None:
    if width is None:
        return None
    return int(round(max(1, int(width)) * float(average_px)))


def _header_chip_name_min_width(text: str) -> int:
    if len(text) >= 5 and any(ord(char) > 127 for char in text):
        return int(round(len(text) * 13.8))
    return 0


def _toolbar_label_min_width(
    label: QtWidgets.QLabel,
    config: dict[str, Any] | None = None,
) -> int:
    text = label.text()
    cjk_count = sum(1 for char in text if ord(char) > 127)
    if config is not None and _uses_tk_default_font(config):
        has_unit_suffix = "(" in text or "（" in text
        if has_unit_suffix:
            compensation = 14 if cjk_count >= 4 else 9
        else:
            compensation = 8 if cjk_count >= 4 else 5
    else:
        compensation = 8 if cjk_count >= 4 else 5
    return label.fontMetrics().horizontalAdvance(text) + compensation


def _button_minimum_height(config: dict[str, Any], font_metrics: QtGui.QFontMetrics) -> int:
    _left, top, _right, bottom = _parse_padding(config.get("padding"))
    borderwidth = int(config.get("borderwidth") or 0)
    return max(1, font_metrics.height() + top + bottom + borderwidth * 2 + 2)


def _allows_layout_expansion(widget: QtWidgets.QWidget) -> bool:
    return not isinstance(
        widget,
        (
            QtWidgets.QAbstractButton,
            QtWidgets.QLabel,
            QtWidgets.QLineEdit,
            QtWidgets.QPlainTextEdit,
            QtWidgets.QComboBox,
        ),
    )


def _mapped_value(
    maps: dict[str, list[tuple[str, Any]]], option: str, state: str
) -> Any | None:
    for map_state, value in maps.get(option, []):
        if map_state == state:
            return value
    return None


def _style_rules(config: dict[str, Any], *, widget_kind: str) -> list[str]:
    background = config.get("fieldbackground") if widget_kind == "entry" else None
    background = background or config.get("background")
    foreground = config.get("foreground")
    bordercolor = config.get("bordercolor") or config.get("darkcolor")
    borderwidth = config.get("borderwidth")
    relief = str(config.get("relief") or "").lower()
    padding = config.get("padding")
    rules: list[str] = []
    if background:
        rules.append(f"background-color: {background};")
    if foreground:
        rules.append(f"color: {foreground};")
    rules.extend(_font_rules(config.get("font")))
    if widget_kind == "checkbutton":
        rules.append("border: 0px solid transparent;")
        rules.append("spacing: 4px;")
        return rules
    if config.get("selectbackground"):
        rules.append(f"selection-background-color: {config['selectbackground']};")
    if config.get("selectforeground"):
        rules.append(f"selection-color: {config['selectforeground']};")
    padding_css = _padding_rule(padding)
    if padding_css:
        rules.append(padding_css)
    if bordercolor or borderwidth or relief in {"solid", "sunken", "raised", "groove", "ridge"}:
        width = int(borderwidth if borderwidth is not None else 1)
        if widget_kind in {"button", "toolbutton"} and relief == "flat" and width <= 1:
            width = 0
        color = bordercolor or ("#cbd5e1" if relief != "flat" and width > 0 else "transparent")
        if width == 0:
            color = "transparent"
        rules.append(f"border: {width}px solid {color};")
        if widget_kind in {"button", "entry", "toolbutton"}:
            rules.append(f"border-radius: {TOKENS.radius}px;")
        elif widget_kind in {"frame", "groupbox"}:
            rules.append(f"border-radius: {TOKENS.card_radius}px;")
    elif widget_kind in {"button", "toolbutton"}:
        rules.append("border: 1px solid transparent;")
        rules.append(f"border-radius: {TOKENS.radius}px;")
    return rules


def _effective_style_config(
    style_name: str | None,
    default_style: str,
    *,
    overrides: dict[str, Any] | None = None,
) -> dict[str, Any]:
    config = _merged_style(style_name, default_style)
    if overrides:
        config.update(overrides)
    if style_name in {"AppBrand.TLabel", "AppSeparator.TLabel"}:
        config = dict(config)
        config["font"] = _font_config_with_size(config.get("font"), 10)
    elif style_name == "TopMenu.TMenubutton":
        config = dict(config)
        left, _top, right, _bottom = _parse_padding(config.get("padding"))
        config["padding"] = (left, 4, right, 4)
    elif style_name in {"WorkspaceTab.TButton", "WorkspaceTabSelected.TButton"}:
        config = dict(config)
        left, _top, right, _bottom = _parse_padding(config.get("padding"))
        config["padding"] = (left, 6, right, 6)
    elif style_name in {
        "HeaderChipName.TLabel",
        "HeaderChipValue.TLabel",
        "HeaderChipPatternValue.TLabel",
    }:
        config = dict(config)
        font = config.get("font")
        size = 9
        if isinstance(font, tuple) and len(font) > 1:
            try:
                size = max(9, int(font[1]))
            except (TypeError, ValueError):
                pass
        config["font"] = _font_config_with_size(font, size)
    return config


def _qss_for_widget(
    object_name: str,
    style_name: str | None,
    default_style: str,
    *,
    widget_kind: str,
    overrides: dict[str, Any] | None = None,
) -> str:
    config = _effective_style_config(
        style_name,
        default_style,
        overrides=overrides,
    )
    maps = _merged_maps(style_name, default_style)
    base_rules = _style_rules(config, widget_kind=widget_kind)
    selector = f"#{object_name}"
    blocks: list[str] = []
    if base_rules:
        blocks.append(f"{selector} {{ {' '.join(base_rules)} }}")

    if widget_kind in {"button", "toolbutton"}:
        for state, pseudo in (("active", "hover"), ("pressed", "pressed"), ("disabled", "disabled")):
            state_config = dict(config)
            for option in ("background", "foreground", "bordercolor", "lightcolor", "darkcolor"):
                value = _mapped_value(maps, option, state)
                if value is not None:
                    state_config[option] = value
            state_rules = _style_rules(state_config, widget_kind=widget_kind)
            if state_rules:
                blocks.append(f"{selector}:{pseudo} {{ {' '.join(state_rules)} }}")
        blocks.append(
            f"{selector}:focus {{ border: 2px solid {TOKENS.focus}; }}"
        )
        if style_name and "danger" in style_name.lower():
            blocks.append(
                f"{selector}:checked {{ background-color: {TOKENS.danger_fill}; "
                f"color: {TOKENS.danger}; border: 1px solid {TOKENS.danger}; }}"
            )
        else:
            blocks.append(
                f"{selector}:checked {{ background-color: {TOKENS.accent_tint}; "
                f"color: {TOKENS.accent_pressed}; border: 1px solid {TOKENS.accent}; }}"
            )

    if widget_kind == "entry":
        selection_bg = config.get("selectbackground")
        selection_fg = config.get("selectforeground")
        selection_rules = []
        if selection_bg:
            selection_rules.append(f"selection-background-color: {selection_bg};")
        if selection_fg:
            selection_rules.append(f"selection-color: {selection_fg};")
        if selection_rules:
            blocks.append(f"{selector} {{ {' '.join(selection_rules)} }}")
        blocks.append(
            f"{selector}:focus {{ border: 2px solid {TOKENS.focus}; }}"
        )

    if widget_kind == "checkbutton":
        blocks.append(f"{selector}:focus {{ color: {TOKENS.accent_pressed}; }}")

    if widget_kind == "groupbox":
        title_color = config.get("foreground")
        title_rules = _font_rules(config.get("font"))
        if title_color:
            title_rules.append(f"color: {title_color};")
        if title_rules:
            blocks.append(f"{selector}::title {{ {' '.join(title_rules)} }}")

    if widget_kind == "tree":
        heading_config = _merged_style("Treeview.Heading", "Treeview.Heading")
        heading_rules = _style_rules(heading_config, widget_kind="frame")
        if heading_rules:
            blocks.append(
                f"{selector} QHeaderView::section {{ {' '.join(heading_rules)} }}"
            )
        rowheight = config.get("rowheight")
        if rowheight:
            blocks.append(f"{selector}::item {{ height: {int(rowheight)}px; }}")
        selected_rules = []
        selected_bg = _mapped_value(maps, "background", "selected")
        selected_fg = _mapped_value(maps, "foreground", "selected")
        if selected_bg:
            selected_rules.append(f"background-color: {selected_bg};")
        if selected_fg:
            selected_rules.append(f"color: {selected_fg};")
        if selected_rules:
            blocks.append(f"{selector}::item:selected {{ {' '.join(selected_rules)} }}")
        blocks.append(
            f"{selector}:focus {{ border: 2px solid {TOKENS.focus}; }}"
        )

    if widget_kind == "notebook":
        tab_config = _merged_style(f"{style_name}.Tab" if style_name else "TNotebook.Tab", "TNotebook.Tab")
        if not tab_config and style_name != "Eval.TNotebook":
            tab_config = _merged_style("Eval.TNotebook.Tab", "Eval.TNotebook.Tab")
        tab_rules = _style_rules(tab_config, widget_kind="button")
        tab_rules.extend(
            [
                "min-width: 76px;",
                "min-height: 24px;",
                "margin-right: 2px;",
            ]
        )
        if tab_rules:
            blocks.append(f"{selector} QTabBar::tab {{ {' '.join(tab_rules)} }}")
            unselected_config = dict(tab_config)
            unselected_config["foreground"] = (
                unselected_config.get("foreground") or config.get("foreground") or "#111827"
            )
            unselected_rules = _style_rules(unselected_config, widget_kind="button")
            unselected_rules.extend(["min-width: 76px;", "min-height: 24px;"])
            blocks.append(
                f"{selector} QTabBar::tab:!selected {{ {' '.join(unselected_rules)} }}"
            )
        selected_config = dict(tab_config)
        for option in ("background", "foreground"):
            value = _mapped_value(
                _merged_maps(
                    f"{style_name}.Tab" if style_name else "TNotebook.Tab",
                    "TNotebook.Tab",
                ),
                option,
                "selected",
            )
            if value is not None:
                selected_config[option] = value
        selected_rules = _style_rules(selected_config, widget_kind="button")
        selected_rules.extend(["min-width: 76px;", "min-height: 24px;"])
        if selected_rules:
            blocks.append(f"{selector} QTabBar::tab:selected {{ {' '.join(selected_rules)} }}")
    return "\n".join(blocks)


class Variable:
    def __init__(self, value: Any = None) -> None:
        self._value = value
        self._callbacks: list[Callable[[Any], None]] = []

    def get(self) -> Any:
        return self._value

    def set(self, value: Any) -> None:
        self._value = value
        for callback in list(self._callbacks):
            callback(value)

    def _connect(self, callback: Callable[[Any], None]) -> None:
        self._callbacks.append(callback)
        callback(self._value)


class StringVar(Variable):
    def __init__(self, value: str = "") -> None:
        super().__init__(value)

    def get(self) -> str:
        return str(super().get())

    def set(self, value: Any) -> None:
        super().set(str(value))


class DoubleVar(Variable):
    def __init__(self, value: float = 0.0) -> None:
        super().__init__(float(value))

    def get(self) -> float:
        return float(super().get())

    def set(self, value: Any) -> None:
        super().set(float(value))


class BooleanVar(Variable):
    def __init__(self, value: bool = False) -> None:
        super().__init__(bool(value))

    def get(self) -> bool:
        return bool(super().get())

    def set(self, value: Any) -> None:
        super().set(bool(value))


class _FocusOutFilter(QtCore.QObject):
    def __init__(self, owner: "Widget", callback: Callable[[Any], Any]) -> None:
        super().__init__(owner._qt)
        self.owner = owner
        self.callback = callback

    def eventFilter(self, obj: QtCore.QObject, event: QtCore.QEvent) -> bool:
        if event.type() == QtCore.QEvent.Type.FocusOut:
            self.owner._invoke_bound(self.callback, keysym="FocusOut")
        return False


class _SplitterResizeFilter(QtCore.QObject):
    def __init__(self, owner: "PanedWindow") -> None:
        super().__init__(owner._qt)
        self.owner = owner

    def eventFilter(self, obj: QtCore.QObject, event: QtCore.QEvent) -> bool:
        if event.type() in {
            QtCore.QEvent.Type.Resize,
            QtCore.QEvent.Type.Show,
            QtCore.QEvent.Type.LayoutRequest,
        }:
            self.owner._apply_pending_sash()
        return False


class Widget:
    _winfo_class = "Widget"
    _default_style = "TWidget"
    _style_kind = "frame"

    def __init__(
        self,
        qt_widget: QtWidgets.QWidget,
        parent: Any = None,
        *,
        padding: Any = None,
        width: int | None = None,
        height: int | None = None,
        style: str | None = None,
        **kwargs: Any,
    ) -> None:
        self._qt = qt_widget
        self._qt._tk_wrapper = self  # type: ignore[attr-defined]
        self._parent = parent
        self._children: list[Widget] = []
        self._grid_layout: QtWidgets.QGridLayout | None = None
        self._pack_layout: QtWidgets.QBoxLayout | None = None
        self._layout_kind: str | None = None
        self._grid_row_weights: dict[int, int] = {}
        self._grid_column_weights: dict[int, int] = {}
        self._grid_row_mins: dict[int, int] = {}
        self._grid_column_mins: dict[int, int] = {}
        self._grid_max_row = -1
        self._grid_max_column = -1
        self._grid_slack_row: int | None = None
        self._grid_slack_column: int | None = None
        self._padding = _parse_padding(padding)
        self._style_name = style
        self._style_overrides: dict[str, Any] = {}
        self._bindings: list[Any] = []
        self._textvariable: Variable | None = None
        self._variable: Variable | None = None
        if not self._qt.objectName():
            self._qt.setObjectName(f"qt_tk_{next(_OBJECT_IDS)}")
        if parent is not None and hasattr(parent, "_children"):
            parent._children.append(self)
        if width is not None:
            self._qt.setMinimumWidth(int(width))
        if height is not None:
            self._qt.setMinimumHeight(int(height))
        self.configure(**kwargs)
        self._apply_style()

    def _layout_margins(self) -> tuple[int, int, int, int]:
        left, top, right, bottom = self._padding
        config = _effective_style_config(self._style_name, self._default_style)
        background = str(config.get("background", "")).lower()
        if (
            self._style_name in {"Status.TFrame", "StatusInner.TFrame"}
            and background in {"#f7fafc", "#f7fbff"}
        ) or (
            self._style_name == "ToolbarGroup.TFrame"
            and background in {"#ffffff", "#f9fcff"}
        ):
            left, top, right, bottom = (
                left,
                _tk_px(top),
                right,
                _tk_px(bottom),
            )
        if isinstance(self._qt, QtWidgets.QGroupBox):
            top += max(18, self._qt.fontMetrics().height() + 6)
        return (left, top, right, bottom)

    def _ensure_grid_layout(self) -> QtWidgets.QGridLayout:
        if self._grid_layout is None:
            if self._layout_kind == "pack":
                raise TclError("cannot mix grid and pack in one parent")
            self._grid_layout = QtWidgets.QGridLayout(self._qt)
            self._grid_layout.setContentsMargins(*self._layout_margins())
            self._grid_layout.setSpacing(0)
            self._layout_kind = "grid"
        return self._grid_layout

    def _ensure_pack_layout(self, side: str | None = None) -> QtWidgets.QBoxLayout:
        if self._pack_layout is None:
            if self._layout_kind == "grid":
                raise TclError("cannot mix pack and grid in one parent")
            orientation = (
                QtWidgets.QBoxLayout.Direction.LeftToRight
                if side in {LEFT, RIGHT}
                else QtWidgets.QBoxLayout.Direction.TopToBottom
            )
            self._pack_layout = QtWidgets.QBoxLayout(orientation, self._qt)
            self._pack_layout.setContentsMargins(*self._layout_margins())
            self._pack_layout.setSpacing(0)
            self._layout_kind = "pack"
        return self._pack_layout

    def grid(
        self,
        row: int = 0,
        column: int = 0,
        rowspan: int = 1,
        columnspan: int = 1,
        sticky: str | None = None,
        padx: Any = None,
        pady: Any = None,
        **_: Any,
    ) -> None:
        if self._parent is None:
            return
        layout = self._parent._ensure_grid_layout()
        pad_left, pad_right = _parse_pad_pair(padx)
        pad_top, pad_bottom = _parse_pad_pair(pady)
        horizontal_gap = pad_left + pad_right
        vertical_gap = pad_top + pad_bottom
        use_padding_wrapper = (
            bool(horizontal_gap or vertical_gap)
            and (
                getattr(self._parent, "_winfo_class", None) == "TLabelframe"
                or (
                    bool(horizontal_gap)
                    and getattr(self._parent, "_style_name", None) == "Dialog.TFrame"
                )
                or getattr(self._parent, "_style_name", None) == "AppMenu.TFrame"
            )
        )
        if (
            getattr(self._parent, "_style_name", None) == "Panel.TFrame"
            and getattr(self, "_style_name", None) == "PlotPanel.TFrame"
        ):
            horizontal_gap *= 2
            vertical_gap *= 2
        if (
            getattr(self._parent, "_winfo_class", None) == "Tk"
            and self._style_name == "Status.TFrame"
        ):
            config = _effective_style_config(self._style_name, self._default_style)
            if str(config.get("background", "")).lower() == "#f7fafc":
                self._qt.setMinimumHeight(max(self._qt.minimumHeight(), 94))
        if horizontal_gap and not use_padding_wrapper:
            layout.setHorizontalSpacing(max(0, layout.horizontalSpacing(), horizontal_gap))
        if vertical_gap and not use_padding_wrapper:
            layout.setVerticalSpacing(max(0, layout.verticalSpacing(), vertical_gap))
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

        grid_widget = self._qt
        if use_padding_wrapper:
            wrapper = QtWidgets.QWidget(_qt_parent(self._parent))
            wrapper.setObjectName(f"qt_tk_gridpad_{next(_OBJECT_IDS)}")
            wrapper.setAttribute(QtCore.Qt.WidgetAttribute.WA_StyledBackground, False)
            parent_config = _effective_style_config(
                getattr(self._parent, "_style_name", None),
                getattr(self._parent, "_default_style", "TFrame"),
            )
            parent_bg = _as_color(parent_config.get("background")) or "transparent"
            wrapper.setStyleSheet(f"background-color: {parent_bg}; border: 0px;")
            wrapper_layout = QtWidgets.QGridLayout(wrapper)
            wrapper_layout.setContentsMargins(pad_left, pad_top, pad_right, pad_bottom)
            wrapper_layout.setSpacing(0)
            wrapper_layout.addWidget(self._qt, 0, 0)
            wrapper.setSizePolicy(self._qt.sizePolicy())
            self._grid_wrapper = wrapper
            grid_widget = wrapper

        if alignment:
            layout.addWidget(grid_widget, row, column, rowspan, columnspan, alignment)
        else:
            layout.addWidget(grid_widget, row, column, rowspan, columnspan)
        if getattr(self._parent, "_winfo_class", None) == "Tk" and hasattr(
            self._parent,
            "_adjust_root_overflow_rows",
        ):
            QtCore.QTimer.singleShot(0, self._parent._adjust_root_overflow_rows)
        self._parent._grid_max_row = max(self._parent._grid_max_row, row + rowspan - 1)
        self._parent._grid_max_column = max(
            self._parent._grid_max_column,
            column + columnspan - 1,
        )
        self._parent._sync_grid_slack()
        column_weighted = any(
            self._parent._grid_column_weights.get(index, 0) > 0
            for index in range(column, column + columnspan)
        )
        row_weighted = any(
            self._parent._grid_row_weights.get(index, 0) > 0
            for index in range(row, row + rowspan)
        )
        if (
            sticky
            and "w" in sticky
            and "e" in sticky
            and column_weighted
            and _allows_layout_expansion(self._qt)
        ):
            self._qt.setSizePolicy(
                QtWidgets.QSizePolicy.Policy.Expanding,
                self._qt.sizePolicy().verticalPolicy(),
            )
            if use_padding_wrapper:
                grid_widget.setSizePolicy(
                    QtWidgets.QSizePolicy.Policy.Expanding,
                    grid_widget.sizePolicy().verticalPolicy(),
                )
        if (
            sticky
            and "n" in sticky
            and "s" in sticky
            and row_weighted
            and _allows_layout_expansion(self._qt)
        ):
            self._qt.setSizePolicy(
                self._qt.sizePolicy().horizontalPolicy(),
                QtWidgets.QSizePolicy.Policy.Expanding,
            )
            if use_padding_wrapper:
                grid_widget.setSizePolicy(
                    grid_widget.sizePolicy().horizontalPolicy(),
                    QtWidgets.QSizePolicy.Policy.Expanding,
                )

    def pack(
        self,
        side: str | None = None,
        fill: str | None = None,
        expand: bool = False,
        padx: Any = None,
        pady: Any = None,
        anchor: str | None = None,
        **_: Any,
    ) -> None:
        if self._parent is None:
            return
        layout = self._parent._ensure_pack_layout(side)
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
        if is_horizontal and fill != BOTH:
            alignment |= QtCore.Qt.AlignmentFlag.AlignVCenter
        elif not is_horizontal and fill not in {X, BOTH}:
            alignment |= QtCore.Qt.AlignmentFlag.AlignHCenter
        if alignment:
            layout.addWidget(self._qt, stretch, alignment)
        else:
            layout.addWidget(self._qt, stretch)
        if after_pad:
            layout.addSpacing(after_pad)
        if fill in {X, BOTH} or expand:
            if is_horizontal:
                horizontal_policy = (
                    QtWidgets.QSizePolicy.Policy.Expanding
                    if expand or fill in {X, BOTH}
                    else QtWidgets.QSizePolicy.Policy.Preferred
                )
                vertical_policy = (
                    QtWidgets.QSizePolicy.Policy.Expanding
                    if fill == BOTH
                    else QtWidgets.QSizePolicy.Policy.Preferred
                )
            else:
                horizontal_policy = (
                    QtWidgets.QSizePolicy.Policy.Expanding
                    if fill in {X, BOTH}
                    else QtWidgets.QSizePolicy.Policy.Preferred
                )
                vertical_policy = (
                    QtWidgets.QSizePolicy.Policy.Expanding
                    if expand or fill == BOTH
                    else QtWidgets.QSizePolicy.Policy.Preferred
                )
            self._qt.setSizePolicy(
                horizontal_policy,
                vertical_policy,
            )

    def grid_rowconfigure(
        self,
        index: int,
        weight: int = 0,
        minsize: int | None = None,
        **_: Any,
    ) -> None:
        layout = self._ensure_grid_layout()
        self._grid_row_weights[index] = weight
        self._grid_max_row = max(self._grid_max_row, index)
        layout.setRowStretch(index, weight)
        if minsize is not None:
            minimum = int(minsize)
            self._grid_row_mins[index] = minimum
            layout.setRowMinimumHeight(index, minimum)
        self._sync_grid_slack()

    def grid_columnconfigure(
        self,
        index: int,
        weight: int = 0,
        minsize: int | None = None,
        **_: Any,
    ) -> None:
        layout = self._ensure_grid_layout()
        self._grid_column_weights[index] = weight
        self._grid_max_column = max(self._grid_max_column, index)
        layout.setColumnStretch(index, weight)
        if minsize is not None:
            minimum = int(minsize)
            if self._style_name == "Header.TFrame" and index > 0 and minimum >= 90:
                minimum = max(1, minimum - 6)
            self._grid_column_mins[index] = minimum
            layout.setColumnMinimumWidth(index, minimum)
        self._sync_grid_slack()

    def _sync_grid_slack(self) -> None:
        if self._grid_layout is None:
            return
        if self._grid_max_column >= 0:
            has_column_weight = any(
                self._grid_column_weights.get(index, 0) > 0
                for index in range(self._grid_max_column + 1)
            )
            slack_column = self._grid_max_column + 1
            if self._grid_slack_column is not None and self._grid_slack_column != slack_column:
                self._grid_layout.setColumnStretch(
                    self._grid_slack_column,
                    self._grid_column_weights.get(self._grid_slack_column, 0),
                )
            self._grid_layout.setColumnStretch(slack_column, 0 if has_column_weight else 1)
            self._grid_layout.setColumnMinimumWidth(slack_column, 0)
            self._grid_slack_column = slack_column
        if self._grid_max_row >= 0:
            has_row_weight = any(
                self._grid_row_weights.get(index, 0) > 0
                for index in range(self._grid_max_row + 1)
            )
            slack_row = self._grid_max_row + 1
            if self._grid_slack_row is not None and self._grid_slack_row != slack_row:
                self._grid_layout.setRowStretch(
                    self._grid_slack_row,
                    self._grid_row_weights.get(self._grid_slack_row, 0),
                )
            self._grid_layout.setRowStretch(slack_row, 0 if has_row_weight else 1)
            self._grid_layout.setRowMinimumHeight(slack_row, 0)
            self._grid_slack_row = slack_row

    def grid_propagate(self, _enabled: bool) -> None:
        return

    def configure(self, **kwargs: Any) -> None:
        if not kwargs:
            self._apply_style()
            return
        if "style" in kwargs:
            self._style_name = kwargs["style"]
        bg = _as_color(kwargs.get("bg") or kwargs.get("background"))
        fg = _as_color(kwargs.get("fg") or kwargs.get("foreground"))
        if bg:
            self._style_overrides["background"] = bg
        if fg:
            self._style_overrides["foreground"] = fg
        if "font" in kwargs and kwargs["font"] is not None:
            self._style_overrides["font"] = kwargs["font"]
        if "relief" in kwargs and kwargs["relief"] is not None:
            self._style_overrides["relief"] = kwargs["relief"]
        if "borderwidth" in kwargs and kwargs["borderwidth"] is not None:
            self._style_overrides["borderwidth"] = kwargs["borderwidth"]
        if "selectbackground" in kwargs and kwargs["selectbackground"] is not None:
            self._style_overrides["selectbackground"] = kwargs["selectbackground"]
        if "selectforeground" in kwargs and kwargs["selectforeground"] is not None:
            self._style_overrides["selectforeground"] = kwargs["selectforeground"]
        if "padding" in kwargs and kwargs["padding"] is not None:
            self._style_overrides["padding"] = kwargs["padding"]
        elif "padx" in kwargs or "pady" in kwargs:
            padx = int(kwargs.get("padx") or 0)
            pady = int(kwargs.get("pady") or 0)
            self._style_overrides["padding"] = (padx, pady, padx, pady)
        if "cursor" in kwargs:
            _set_cursor(self._qt, kwargs.get("cursor"))
        if "state" in kwargs:
            state = kwargs["state"]
            self._qt.setEnabled(state != DISABLED)
        if "width" in kwargs and kwargs["width"] is not None:
            self._qt.setMinimumWidth(int(kwargs["width"]))
        if "height" in kwargs and kwargs["height"] is not None:
            self._qt.setMinimumHeight(int(kwargs["height"]))
        self._apply_style()

    config = configure

    def _apply_style(self) -> None:
        config = _effective_style_config(
            self._style_name,
            self._default_style,
            overrides=self._style_overrides,
        )
        font = _font_from_config(config.get("font"))
        if font is not None:
            self._qt.setFont(font)
        stylesheet = _qss_for_widget(
            self._qt.objectName(),
            self._style_name,
            self._default_style,
            widget_kind=self._style_kind,
            overrides=self._style_overrides,
        )
        self._qt.setStyleSheet(stylesheet)

    def cget(self, option: str) -> Any:
        if option == "style":
            return self._style_name
        if option == "text":
            if hasattr(self, "_text_value"):
                return self._text_value
            if hasattr(self._qt, "text"):
                return self._qt.text()
        return None

    def bind(self, sequence: str, callback: Callable[[Any], Any], **_: Any) -> None:
        if sequence.startswith("<<"):
            return
        qt_sequence, keysym = _sequence_to_key(sequence)
        if sequence == "<Return>" and isinstance(self._qt, QtWidgets.QLineEdit):
            self._qt.returnPressed.connect(
                lambda cb=callback, key=keysym: self._invoke_bound(cb, keysym=key)
            )
            return
        if sequence == "<FocusOut>":
            filt = _FocusOutFilter(self, callback)
            self._qt.installEventFilter(filt)
            self._bindings.append(filt)
            return
        shortcut = QtGui.QShortcut(QtGui.QKeySequence(qt_sequence), self._qt)
        shortcut.activated.connect(
            lambda cb=callback, key=keysym: self._invoke_bound(cb, keysym=key)
        )
        self._bindings.append(shortcut)

    def _invoke_bound(self, callback: Callable[[Any], Any], *, keysym: str) -> None:
        focus = QtWidgets.QApplication.focusWidget()
        widget = getattr(focus, "_tk_wrapper", None) if focus is not None else None
        callback(SimpleNamespace(keysym=keysym, widget=widget))

    def focus_set(self) -> None:
        self._qt.setFocus(QtCore.Qt.FocusReason.OtherFocusReason)

    def winfo_children(self) -> list["Widget"]:
        return list(self._children)

    def winfo_class(self) -> str:
        return self._winfo_class

    def winfo_x(self) -> int:
        return int(self._qt.x())

    def winfo_y(self) -> int:
        return int(self._qt.y())

    def winfo_rootx(self) -> int:
        return int(self._qt.mapToGlobal(QtCore.QPoint(0, 0)).x())

    def winfo_rooty(self) -> int:
        return int(self._qt.mapToGlobal(QtCore.QPoint(0, 0)).y())

    def winfo_screenwidth(self) -> int:
        screen = _ensure_app().primaryScreen()
        return int(screen.geometry().width()) if screen is not None else 0

    def winfo_screenheight(self) -> int:
        screen = _ensure_app().primaryScreen()
        return int(screen.geometry().height()) if screen is not None else 0

    def winfo_width(self) -> int:
        return int(self._qt.width())

    def winfo_height(self) -> int:
        return int(self._qt.height())

    def winfo_geometry(self) -> str:
        geo = self._qt.geometry()
        return f"{geo.width()}x{geo.height()}+{geo.x()}+{geo.y()}"

    def update_idletasks(self) -> None:
        QtWidgets.QApplication.processEvents()

    def update(self) -> None:
        QtWidgets.QApplication.processEvents()

    def destroy(self) -> None:
        self._qt.close()


class Tk(Widget):
    _winfo_class = "Tk"
    _default_style = "TFrame"
    _style_kind = "frame"

    def __init__(self, window: QtWidgets.QMainWindow | None = None) -> None:
        self._app = _ensure_app()
        self._window = window if window is not None else _MainWindow(self)
        central = self._window.centralWidget()
        if central is None:
            central = QtWidgets.QWidget()
            self._window.setCentralWidget(central)
        self._close_callback: Callable[[], Any] | None = None
        self._destroying = False
        self._pending_geometry_size: tuple[int, int] | None = None
        self._pending_resizable: tuple[bool, bool] | None = None
        super().__init__(central, None)
        self._qt = central
        self._window._tk_owner = self  # type: ignore[attr-defined]
        self._window_filter: _WindowEventFilter | None = None
        if not isinstance(self._window, _MainWindow):
            self._window_filter = _WindowEventFilter(self)
            self._window.installEventFilter(self._window_filter)

    def title(self, text: str) -> None:
        self._window.setWindowTitle(text)

    def configure(self, **kwargs: Any) -> None:
        super().configure(**kwargs)
        bg = _as_color(kwargs.get("bg") or kwargs.get("background"))
        if bg:
            self._window.setStyleSheet(f"background-color: {bg};")

    def option_add(self, *_args: Any, **_kwargs: Any) -> None:
        return

    def geometry(self, value: str | None = None) -> str:
        if value is None:
            geo = self._window.geometry()
            return f"{geo.width()}x{geo.height()}+{geo.x()}+{geo.y()}"
        parsed = _parse_geometry(value)
        if parsed is None:
            raise TclError(f"bad geometry specifier: {value}")
        width, height, x, y = parsed
        screen = self._app.screenAt(QtGui.QCursor.pos()) or self._app.primaryScreen()
        available = screen.availableGeometry() if screen is not None else QtCore.QRect()
        if available.isValid():
            width = min(width, max(1, available.width()))
            height = min(height, max(1, available.height()))
            if x is not None and y is not None:
                x = min(max(x, available.left()), max(available.left(), available.right() - width + 1))
                y = min(max(y, available.top()), max(available.top(), available.bottom() - height + 1))
        self._window.resize(width, height)
        self._pending_geometry_size = None if self._window.isVisible() else (width, height)
        if x is not None and y is not None:
            self._window.move(x, y)
        return value

    def minsize(self, width: int, height: int) -> None:
        screen = self._window.screen() or self._app.primaryScreen()
        available = screen.availableGeometry() if screen is not None else QtCore.QRect()
        if available.isValid():
            width = min(width, max(1, available.width()))
            height = min(height, max(1, available.height()))
        self._window.setMinimumSize(width, height)

    def resizable(self, width: bool, height: bool) -> None:
        if not width or not height:
            for child in self._children:
                if (
                    getattr(child, "_style_name", None) == "Status.TFrame"
                    and getattr(child, "_parent", None) is self
                ):
                    config = _effective_style_config(child._style_name, child._default_style)
                    if str(config.get("background", "")).lower() == "#f7fbff":
                        child._qt.setMinimumHeight(max(child._qt.minimumHeight(), 79))
            self._app.processEvents()
            current_y = self._window.geometry().y()
            hint = self._window.sizeHint()
            if hint.isValid():
                current_before_hint = self._window.size()
                target_width = current_before_hint.width()
                target_height = current_before_hint.height()
                screen = self._app.primaryScreen()
                screen_rect = screen.geometry() if screen is not None else QtCore.QRect()
                if not width:
                    target_width = max(target_width, min(hint.width(), screen_rect.width()))
                if not height:
                    if screen_rect.isValid():
                        max_height = max(1, screen_rect.bottom() - current_y + 1)
                        if target_width >= screen_rect.width():
                            target_height = max_height
                        else:
                            target_height = min(max(target_height, hint.height()), max_height)
                    else:
                        target_height = max(target_height, hint.height())
                if target_width != current_before_hint.width() or target_height != current_before_hint.height():
                    self._window.resize(target_width, target_height)
            current = self._window.size()
            minimum = self._window.minimumSize()
            maximum_width = current.width() if not width else 16_777_215
            maximum_height = current.height() if not height else 16_777_215
            if not self._window.isVisible():
                self._pending_resizable = (width, height)
                return
            self._window.setMinimumSize(
                current.width() if not width else minimum.width(),
                current.height() if not height else minimum.height(),
            )
            self._window.setMaximumSize(maximum_width, maximum_height)
            self._pending_resizable = None

    def _apply_pending_geometry(self) -> None:
        if self._pending_geometry_size is None or not self._window.isVisible():
            return
        width, height = self._pending_geometry_size
        if self._window.width() != width or self._window.height() != height:
            self._window.resize(width, height)
            self._app.processEvents()
        self._pending_geometry_size = None

    def _apply_pending_resizable(self) -> None:
        if self._pending_resizable is None or not self._window.isVisible():
            return
        width, height = self._pending_resizable
        current = self._window.size()
        minimum = self._window.minimumSize()
        self._window.setMinimumSize(
            current.width() if not width else minimum.width(),
            current.height() if not height else minimum.height(),
        )
        self._window.setMaximumSize(
            current.width() if not width else 16_777_215,
            current.height() if not height else 16_777_215,
        )
        self._pending_resizable = None

    def protocol(self, name: str, callback: Callable[[], Any]) -> None:
        if name == "WM_DELETE_WINDOW":
            self._close_callback = callback

    def bind(self, sequence: str, callback: Callable[[Any], Any]) -> None:
        qt_sequence, keysym = _sequence_to_key(sequence)
        shortcut = QtGui.QShortcut(QtGui.QKeySequence(qt_sequence), self._window)
        shortcut.activated.connect(
            lambda cb=callback, key=keysym: self._invoke_bound(cb, keysym=key)
        )
        self._bindings.append(shortcut)

    def after(self, delay_ms: int, callback: Callable[[], Any]) -> str:
        timer = QtCore.QTimer(self._window)
        timer.setSingleShot(True)
        timer.timeout.connect(callback)
        timer.start(delay_ms)
        timer_id = f"after-{id(timer)}"
        if not hasattr(self, "_timers"):
            self._timers = {}
        self._timers[timer_id] = timer
        timer.timeout.connect(lambda key=timer_id: self._timers.pop(key, None))
        return timer_id

    def after_idle(self, callback: Callable[[], Any]) -> str:
        return self.after(0, callback)

    def after_cancel(self, after_id: str) -> None:
        timer = getattr(self, "_timers", {}).pop(after_id, None)
        if timer is not None:
            timer.stop()

    def _adjust_root_overflow_rows(self) -> None:
        layout = self._grid_layout
        if layout is None:
            return
        status_children = [
            child
            for child in self._children
            if getattr(child, "_style_name", None) == "Status.TFrame"
            and getattr(child, "_parent", None) is self
        ]
        if not status_children:
            return
        status = status_children[-1]._qt
        requested_workspace_min = self._grid_row_mins.get(2, layout.rowMinimumHeight(2))
        if requested_workspace_min <= 0:
            return
        menu_height = next(
            (
                child._qt.height()
                for child in self._children
                if getattr(child, "_style_name", None) == "AppMenu.TFrame"
            ),
            layout.rowMinimumHeight(0),
        )
        header_height = next(
            (
                child._qt.height()
                for child in self._children
                if getattr(child, "_style_name", None) == "Header.TFrame"
            ),
            layout.rowMinimumHeight(1),
        )
        status_hint = status.sizeHint().height()
        required_height = menu_height + header_height + requested_workspace_min + status_hint
        current_height = self._qt.height()
        if required_height > current_height and not self._window.isMaximized():
            screen = self._app.primaryScreen()
            screen_rect = screen.geometry() if screen is not None else QtCore.QRect()
            target_height = required_height
            if screen_rect.isValid():
                current_y = self._window.geometry().y()
                target_height = min(target_height, max(1, screen_rect.bottom() - current_y + 1))
            if target_height > current_height:
                self._window.resize(self._window.width(), int(target_height))
                self._app.processEvents()
                current_height = self._qt.height()
                status_hint = status.sizeHint().height()
                required_height = (
                    menu_height
                    + header_height
                    + requested_workspace_min
                    + status_hint
                )
        if current_height >= required_height:
            if layout.rowMinimumHeight(2) != requested_workspace_min:
                layout.setRowMinimumHeight(2, requested_workspace_min)
                self._qt.updateGeometry()
            if status.maximumHeight() != 16_777_215:
                status.setMaximumHeight(16_777_215)
                status.updateGeometry()
            return

        available_for_workspace = current_height - menu_height - header_height - status_hint
        if available_for_workspace > 0:
            workspace_min = min(requested_workspace_min, max(1, int(available_for_workspace)))
            if layout.rowMinimumHeight(2) != workspace_min:
                layout.setRowMinimumHeight(2, workspace_min)
                self._qt.updateGeometry()
        else:
            workspace_min = layout.rowMinimumHeight(2)
        available_for_status = current_height - menu_height - header_height - workspace_min
        if available_for_status <= 0:
            return
        desired_max = max(1, int(available_for_status))
        if desired_max < status_hint:
            if status.maximumHeight() != desired_max:
                status.setMaximumHeight(desired_max)
                status.updateGeometry()
        elif status.maximumHeight() != 16_777_215:
            status.setMaximumHeight(16_777_215)
            status.updateGeometry()

    def mainloop(self) -> None:
        self._window.show()
        self._apply_pending_geometry()
        self._apply_pending_resizable()
        self._adjust_root_overflow_rows()
        self._app.processEvents()
        self._app.exec()

    def destroy(self) -> None:
        self._destroying = True
        self._window.close()
        self._app.quit()

    def state(self, value: str | None = None) -> str:
        if value is None:
            if self._window.isMinimized():
                return "iconic"
            if self._window.isMaximized():
                return "zoomed"
            return "normal"
        if value == "zoomed":
            self._window.showMaximized()
        elif value == "iconic":
            self._window.showMinimized()
        elif value == "normal":
            self._window.showNormal()
        return value

    def update_idletasks(self) -> None:
        self._app.processEvents()
        self._apply_pending_geometry()
        self._apply_pending_resizable()

    def update(self) -> None:
        self._app.processEvents()
        self._apply_pending_geometry()
        self._apply_pending_resizable()

    def iconbitmap(self, default: str | None = None, **_: Any) -> None:
        if default:
            self._window.setWindowIcon(QtGui.QIcon(default))

    def iconphoto(self, _default: bool, image: "PhotoImage") -> None:
        self._window.setWindowIcon(QtGui.QIcon(image.pixmap))


class _MainWindow(QtWidgets.QMainWindow):
    def __init__(self, owner: Tk) -> None:
        super().__init__()
        self.owner = owner

    def resizeEvent(self, event: QtGui.QResizeEvent) -> None:  # noqa: N802
        super().resizeEvent(event)
        QtCore.QTimer.singleShot(0, self.owner._adjust_root_overflow_rows)

    def closeEvent(self, event: QtGui.QCloseEvent) -> None:
        if self.owner._destroying:
            event.accept()
            return
        if self.owner._close_callback is not None:
            self.owner._close_callback()
            if self.owner._destroying:
                event.accept()
            else:
                event.ignore()
            return
        event.accept()


class _WindowEventFilter(QtCore.QObject):
    """Give an externally supplied QMainWindow the same lifecycle hooks."""

    def __init__(self, owner: Tk) -> None:
        super().__init__(owner._window)
        self.owner = owner

    def eventFilter(self, watched: QtCore.QObject, event: QtCore.QEvent) -> bool:
        if event.type() == QtCore.QEvent.Type.Resize:
            QtCore.QTimer.singleShot(0, self.owner._adjust_root_overflow_rows)
        elif event.type() == QtCore.QEvent.Type.Close and not self.owner._destroying:
            if self.owner._close_callback is not None:
                self.owner._close_callback()
                if not self.owner._destroying:
                    event.ignore()
                    return True
        return super().eventFilter(watched, event)


class Toplevel(Widget):
    _winfo_class = "Toplevel"
    _default_style = "TFrame"
    _style_kind = "frame"

    def __init__(self, parent: Any = None, **kwargs: Any) -> None:
        _ensure_app()
        dialog = _Dialog(self)
        qt_parent = _qt_parent(parent)
        if qt_parent is not None:
            dialog.setParent(qt_parent.window(), QtCore.Qt.WindowType.Dialog)
        self._close_callback: Callable[[], Any] | None = None
        self._destroying = False
        super().__init__(dialog, parent, **kwargs)
        dialog.resize(640, 480)
        dialog.show()

    def title(self, text: str) -> None:
        self._qt.setWindowTitle(text)

    def geometry(self, value: str | None = None) -> str:
        if value is None:
            return self.winfo_geometry()
        parsed = _parse_geometry(value)
        if parsed is None:
            raise TclError(f"bad geometry specifier: {value}")
        width, height, x, y = parsed
        self._qt.resize(width, height)
        if x is not None and y is not None:
            self._qt.move(x, y)
        else:
            self._qt.move(0, 0)
        return value

    def minsize(self, width: int, height: int) -> None:
        self._qt.setMinimumSize(width, height)

    def transient(self, parent: Any) -> None:
        qt_parent = _qt_parent(parent)
        if qt_parent is not None:
            was_visible = self._qt.isVisible()
            self._qt.setParent(qt_parent.window(), QtCore.Qt.WindowType.Dialog)
            if was_visible:
                self._qt.show()

    def grab_set(self) -> None:
        self._qt.setModal(True)

    def wait_window(self) -> None:
        if isinstance(self._qt, QtWidgets.QDialog):
            self._qt.setModal(True)
            self._qt.exec()

    def protocol(self, name: str, callback: Callable[[], Any]) -> None:
        if name == "WM_DELETE_WINDOW":
            self._close_callback = callback

    def destroy(self) -> None:
        self._destroying = True
        if isinstance(self._qt, QtWidgets.QDialog):
            self._qt.accept()
        else:
            self._qt.close()


class _Dialog(QtWidgets.QDialog):
    def __init__(self, owner: Toplevel) -> None:
        super().__init__()
        self.owner = owner

    def closeEvent(self, event: QtGui.QCloseEvent) -> None:
        if self.owner._destroying:
            event.accept()
            return
        if self.owner._close_callback is not None:
            self.owner._close_callback()
            if self.owner._destroying:
                event.accept()
            else:
                event.ignore()
            return
        event.accept()


class Frame(Widget):
    _winfo_class = "TFrame"
    _default_style = "TFrame"
    _style_kind = "frame"

    def __init__(self, parent: Any = None, **kwargs: Any) -> None:
        width = kwargs.pop("width", None)
        height = kwargs.pop("height", None)
        frame = QtWidgets.QWidget(_qt_parent(parent))
        if width is not None or height is not None:
            frame.resize(int(width or frame.width()), int(height or frame.height()))
            frame.setBaseSize(int(width or 0), int(height or 0))
        super().__init__(frame, parent, **kwargs)


class LabelFrame(Widget):
    _winfo_class = "TLabelframe"
    _default_style = "TLabelframe"
    _style_kind = "groupbox"

    def __init__(self, parent: Any = None, text: str = "", **kwargs: Any) -> None:
        self._text_value = str(text)
        super().__init__(QtWidgets.QGroupBox(text, _qt_parent(parent)), parent, **kwargs)

    def configure(self, **kwargs: Any) -> None:
        text = kwargs.pop("text", None)
        if text is not None:
            self._text_value = str(text)
            self._qt.setTitle(self._text_value)
        super().configure(**kwargs)


class Label(Widget):
    _winfo_class = "TLabel"
    _default_style = "TLabel"
    _style_kind = "label"

    def __init__(
        self,
        parent: Any = None,
        text: str | None = None,
        textvariable: Variable | None = None,
        image: Any = None,
        anchor: str | None = None,
        justify: str | None = None,
        **kwargs: Any,
    ) -> None:
        label = QtWidgets.QLabel(_qt_parent(parent))
        self._text_value = "" if text is None else str(text)
        label.setText(self._text_value)
        wraplength = kwargs.pop("wraplength", None)
        label.setWordWrap(wraplength is not None and int(wraplength) > 0)
        if wraplength is not None and int(wraplength) > 0:
            wrap_px = int(wraplength)
            if wrap_px <= 120:
                label.setMinimumWidth(_tk_px(wrap_px))
        label.setAlignment(_qt_alignment(anchor, justify))
        char_width = kwargs.pop("width", None)
        style_name = kwargs.get("style")
        if char_width is not None:
            minimum_width = _text_width_px(int(char_width), average_px=7) or 0
            if style_name in {
                "HeaderChipValue.TLabel",
                "HeaderChipPatternValue.TLabel",
            }:
                minimum_width += 4
            label.setMinimumWidth(minimum_width)
        super().__init__(label, parent, **kwargs)
        if self._style_name == "HeaderTitle.TLabel":
            config = _effective_style_config(self._style_name, self._default_style)
            is_light_header = str(config.get("background", "")).lower() == "#f5faff"
            label.setMinimumHeight(17 if is_light_header else 21)
            minimum_width = (
                246
                if is_light_header
                else 106
            )
            label.setMinimumWidth(max(label.minimumWidth(), minimum_width))
        if self._style_name == "Toolbar.TLabel":
            config = _effective_style_config(self._style_name, self._default_style)
            label.setMinimumHeight(17 if _uses_tk_default_font(config) else 21)
            # Toolbar copy changes with the active locale.  A minimum captured
            # from the first language made the command bar permanently wider
            # even after a shorter translation was selected.
            label.setMinimumWidth(0)
            label.setSizePolicy(
                QtWidgets.QSizePolicy.Policy.Preferred,
                QtWidgets.QSizePolicy.Policy.Preferred,
            )
        if self._style_name == "Muted.TLabel":
            config = _effective_style_config(self._style_name, self._default_style)
            if not _uses_tk_default_font(config):
                label.setMinimumHeight(max(label.minimumHeight(), 21))
        if self._style_name == "Card.TLabel":
            config = _effective_style_config(self._style_name, self._default_style)
            if str(config.get("background", "")).lower() == "#ffffff":
                label.setMinimumHeight(max(label.minimumHeight(), 20))
                if wraplength is not None and int(wraplength) >= 600:
                    target_height = 43 if _uses_tk_default_font(config) else 55
                    label.setMinimumHeight(max(label.minimumHeight(), target_height))
        if self._style_name in {
            "HeaderChipName.TLabel",
            "HeaderChipValue.TLabel",
            "HeaderChipPatternValue.TLabel",
        }:
            config = _effective_style_config(self._style_name, self._default_style)
            is_light_header = str(config.get("background", "")).lower() == "#f8fbff"
            label.setMinimumHeight(_tk_px(21) if is_light_header else 21)
            if self._style_name == "HeaderChipName.TLabel":
                label.setMinimumWidth(
                    max(label.minimumWidth(), _header_chip_name_min_width(label.text()))
                )
        if image is not None and hasattr(image, "pixmap"):
            pixmap = image.pixmap
            config = _effective_style_config(self._style_name, self._default_style)
            if (
                self._style_name == "AppLogo.TLabel"
                and str(config.get("background", "")).lower() == "#fbfdff"
                and not pixmap.isNull()
            ):
                size = 52
                pixmap = pixmap.scaled(
                    size,
                    size,
                    QtCore.Qt.AspectRatioMode.KeepAspectRatio,
                    QtCore.Qt.TransformationMode.SmoothTransformation,
                )
            label.setPixmap(pixmap)
        if textvariable is not None:
            self._textvariable = textvariable
            textvariable._connect(self._set_text)

    def _set_text(self, value: Any) -> None:
        self._text_value = str(value)
        self._qt.setText(self._text_value)

    def configure(self, **kwargs: Any) -> None:
        text = kwargs.pop("text", None)
        textvariable = kwargs.pop("textvariable", None)
        image = kwargs.pop("image", None)
        wraplength = kwargs.pop("wraplength", None)
        anchor = kwargs.pop("anchor", None)
        justify = kwargs.pop("justify", None)
        if text is not None:
            self._set_text(text)
        if image is not None and hasattr(image, "pixmap"):
            pixmap = image.pixmap
            config = _effective_style_config(self._style_name, self._default_style)
            if (
                self._style_name == "AppLogo.TLabel"
                and str(config.get("background", "")).lower() == "#fbfdff"
                and not pixmap.isNull()
            ):
                size = 52
                pixmap = pixmap.scaled(
                    size,
                    size,
                    QtCore.Qt.AspectRatioMode.KeepAspectRatio,
                    QtCore.Qt.TransformationMode.SmoothTransformation,
                )
            self._qt.setPixmap(pixmap)
        if textvariable is not None:
            self._textvariable = textvariable
            textvariable._connect(self._set_text)
        if wraplength is not None:
            wrap_px = int(wraplength)
            self._qt.setWordWrap(wrap_px > 0)
            if wrap_px > 0:
                if wrap_px <= 120:
                    self._qt.setMinimumWidth(max(self._qt.minimumWidth(), wrap_px))
            else:
                self._qt.setMaximumWidth(16_777_215)
        if anchor is not None or justify is not None:
            self._qt.setAlignment(_qt_alignment(anchor, justify))
        super().configure(**kwargs)
        if self._style_name == "Toolbar.TLabel":
            config = _effective_style_config(self._style_name, self._default_style)
            self._qt.setMinimumHeight(
                max(self._qt.minimumHeight(), 17 if _uses_tk_default_font(config) else 21)
            )
            self._qt.setMinimumWidth(
                max(self._qt.minimumWidth(), _toolbar_label_min_width(self._qt, config))
            )
        if self._style_name == "Muted.TLabel":
            config = _effective_style_config(self._style_name, self._default_style)
            if not _uses_tk_default_font(config):
                self._qt.setMinimumHeight(max(self._qt.minimumHeight(), 21))
        if self._style_name == "Card.TLabel" and wraplength is not None and int(wraplength) >= 600:
            config = _effective_style_config(self._style_name, self._default_style)
            target_height = 43 if _uses_tk_default_font(config) else 55
            self._qt.setMinimumHeight(max(self._qt.minimumHeight(), target_height))


class Button(Widget):
    _winfo_class = "TButton"
    _default_style = "TButton"
    _style_kind = "button"

    def __init__(
        self,
        parent: Any = None,
        text: str = "",
        command: Callable[[], Any] | None = None,
        **kwargs: Any,
    ) -> None:
        self._text_value = str(text)
        button = QtWidgets.QPushButton(_qt_button_text(text), _qt_parent(parent))
        char_width = kwargs.pop("width", None)
        if char_width is not None:
            style_name = kwargs.get("style")
            average_px = (
                10.1
                if style_name in {"WorkspaceTab.TButton", "WorkspaceTabSelected.TButton"}
                else 10.4
                if style_name == "ToolbarPrimary.TButton"
                else 9.75
                if style_name is not None and str(style_name).startswith("Compact")
                else 9
            )
            button.setMinimumWidth(max(1, int(round(int(char_width) * average_px))))
        super().__init__(button, parent, **kwargs)
        config = _effective_style_config(self._style_name, self._default_style)
        button.setMinimumHeight(
            max(button.minimumHeight(), _button_minimum_height(config, button.fontMetrics()))
        )
        if self._style_name is not None and str(self._style_name).startswith("Compact"):
            if _uses_tk_default_font(config):
                button.setFixedHeight(26)
            else:
                button.setMinimumHeight(max(button.minimumHeight(), 29))
        if self._style_name == "ToolbarPrimary.TButton" and _uses_tk_default_font(config):
            button.setFixedHeight(28)
        if self._style_name == "Large.TButton":
            button.setMinimumWidth(max(button.minimumWidth(), 107))
            if _uses_tk_default_font(config):
                button.setFixedHeight(33)
            else:
                button.setMinimumHeight(max(button.minimumHeight(), 37))
        if self._style_name in {"DialogButton.TButton", "DialogDanger.TButton"}:
            button.setMinimumWidth(max(button.minimumWidth(), 107))
            if _uses_tk_default_font(config):
                button.setFixedHeight(33)
            else:
                button.setMinimumHeight(max(button.minimumHeight(), 37))
        self._command = command
        if command is not None:
            button.clicked.connect(lambda _checked=False, cb=command: cb())

    def configure(self, **kwargs: Any) -> None:
        text = kwargs.pop("text", None)
        command = kwargs.pop("command", None)
        if text is not None:
            self._text_value = str(text)
            self._qt.setText(_qt_button_text(text))
        if command is not None:
            try:
                self._qt.clicked.disconnect()
            except RuntimeError:
                pass
            self._qt.clicked.connect(lambda _checked=False, cb=command: cb())
            self._command = command
        super().configure(**kwargs)


class Menubutton(Button):
    _winfo_class = "TMenubutton"
    _default_style = "TMenubutton"
    _style_kind = "toolbutton"

    def __init__(self, parent: Any = None, text: str = "", **kwargs: Any) -> None:
        tool_button = QtWidgets.QToolButton(_qt_parent(parent))
        self._text_value = str(text)
        tool_button.setText(_qt_button_text(text))
        tool_button.setPopupMode(QtWidgets.QToolButton.ToolButtonPopupMode.InstantPopup)
        char_width = kwargs.pop("width", None)
        if char_width is not None:
            style_name = kwargs.get("style")
            if style_name == "TopMenu.TMenubutton":
                config = _effective_style_config(style_name, self._default_style)
                average_px = 17.4 if _uses_tk_default_font(config) else 16.4
                tool_button.setFixedWidth(max(1, int(round(int(char_width) * average_px))))
            else:
                tool_button.setMinimumWidth(max(1, int(round(int(char_width) * 15.5))))
        Widget.__init__(self, tool_button, parent, **kwargs)

    def configure(self, **kwargs: Any) -> None:
        menu = kwargs.pop("menu", None)
        text = kwargs.pop("text", None)
        if text is not None:
            self._text_value = str(text)
            self._qt.setText(_qt_button_text(text))
        if menu is not None:
            self._qt.setMenu(menu._menu)
        Widget.configure(self, **kwargs)


class Entry(Widget):
    _winfo_class = "TEntry"
    _default_style = "TEntry"
    _style_kind = "entry"

    def __init__(
        self,
        parent: Any = None,
        textvariable: Variable | None = None,
        width: int | None = None,
        justify: str | None = None,
        **kwargs: Any,
    ) -> None:
        line = QtWidgets.QLineEdit(_qt_parent(parent))
        requested_width = _text_width_px(width, average_px=9.25)
        super().__init__(line, parent, **kwargs)
        if requested_width is not None:
            line.setFixedWidth(requested_width)
        config = _effective_style_config(self._style_name, self._default_style)
        line.setFixedHeight(25 if _uses_tk_default_font(config) else 29)
        if justify == "right":
            line.setAlignment(QtCore.Qt.AlignmentFlag.AlignRight)
        self._textvariable = textvariable
        self._updating = False
        if textvariable is not None:
            textvariable._connect(self._set_from_variable)
            line.textChanged.connect(lambda value: self._set_variable(value))

    def _set_from_variable(self, value: Any) -> None:
        if self._qt.text() == str(value):
            return
        self._updating = True
        self._qt.setText(str(value))
        self._updating = False

    def _set_variable(self, value: str) -> None:
        if self._updating or self._textvariable is None:
            return
        self._textvariable.set(value)

    def get(self) -> str:
        return self._qt.text()

    def selection_range(self, start: int, end: Any) -> None:
        length = len(self._qt.text()) if end == END else int(end) - start
        self._qt.setSelection(start, length)


class Radiobutton(Widget):
    _winfo_class = "TRadiobutton"
    _default_style = "TRadiobutton"
    _style_kind = "checkbutton"

    def __init__(
        self,
        parent: Any = None,
        text: str = "",
        variable: Variable | None = None,
        value: Any = None,
        command: Callable[[], Any] | None = None,
        **kwargs: Any,
    ) -> None:
        self._text_value = str(text)
        button = QtWidgets.QRadioButton(_qt_button_text(text), _qt_parent(parent))
        button.setAutoExclusive(False)
        super().__init__(button, parent, **kwargs)
        config = _effective_style_config(self._style_name, self._default_style)
        button.setMinimumHeight(
            max(button.minimumHeight(), 19 if _uses_tk_default_font(config) else 23)
        )
        if _uses_tk_default_font(config) and any(ord(char) > 127 for char in text):
            button.setMinimumWidth(max(button.minimumWidth(), button.sizeHint().width() + 3))
        self._variable = variable
        self._value = value
        self._command = command
        if variable is not None:
            variable._connect(lambda current: button.setChecked(current == value))
        button.toggled.connect(self._on_toggled)

    def _on_toggled(self, checked: bool) -> None:
        if not checked:
            if self._variable is not None and self._variable.get() == self._value:
                self._qt.setChecked(True)
            return
        if self._variable is not None:
            self._variable.set(self._value)
        if self._command is not None:
            self._command()

    def configure(self, **kwargs: Any) -> None:
        text = kwargs.pop("text", None)
        if text is not None:
            self._text_value = str(text)
            self._qt.setText(_qt_button_text(text))
        super().configure(**kwargs)


class Checkbutton(Widget):
    _winfo_class = "TCheckbutton"
    _default_style = "TCheckbutton"
    _style_kind = "checkbutton"

    def __init__(
        self,
        parent: Any = None,
        text: str = "",
        variable: Variable | None = None,
        command: Callable[[], Any] | None = None,
        **kwargs: Any,
    ) -> None:
        self._text_value = str(text)
        button = QtWidgets.QCheckBox(_qt_button_text(text), _qt_parent(parent))
        super().__init__(button, parent, **kwargs)
        config = _effective_style_config(self._style_name, self._default_style)
        button.setMinimumHeight(
            max(button.minimumHeight(), 19 if _uses_tk_default_font(config) else 23)
        )
        self._variable = variable
        self._command = command
        if variable is not None:
            variable._connect(lambda current: button.setChecked(bool(current)))
        button.toggled.connect(self._on_toggled)

    def _on_toggled(self, checked: bool) -> None:
        if self._variable is not None:
            self._variable.set(bool(checked))
        if self._command is not None:
            self._command()

    def configure(self, **kwargs: Any) -> None:
        text = kwargs.pop("text", None)
        if text is not None:
            self._text_value = str(text)
            self._qt.setText(_qt_button_text(text))
        super().configure(**kwargs)


class Separator(Widget):
    _winfo_class = "TSeparator"
    _default_style = "TSeparator"
    _style_kind = "frame"

    def __init__(self, parent: Any = None, orient: str = HORIZONTAL, **kwargs: Any) -> None:
        line = QtWidgets.QFrame(_qt_parent(parent))
        line.setFrameShape(
            QtWidgets.QFrame.Shape.VLine
            if orient == VERTICAL
            else QtWidgets.QFrame.Shape.HLine
        )
        line.setFrameShadow(QtWidgets.QFrame.Shadow.Sunken)
        if orient == VERTICAL:
            line.setFixedWidth(2)
            line.setSizePolicy(
                QtWidgets.QSizePolicy.Policy.Fixed,
                QtWidgets.QSizePolicy.Policy.Expanding,
            )
        else:
            line.setFixedHeight(2)
            line.setSizePolicy(
                QtWidgets.QSizePolicy.Policy.Expanding,
                QtWidgets.QSizePolicy.Policy.Fixed,
            )
        super().__init__(line, parent, **kwargs)


class Scrollbar(Widget):
    _winfo_class = "TScrollbar"
    _default_style = "TScrollbar"
    _style_kind = "frame"

    def __init__(
        self,
        parent: Any = None,
        orient: str = VERTICAL,
        command: Callable[..., Any] | None = None,
        **kwargs: Any,
    ) -> None:
        bar = QtWidgets.QScrollBar(
            QtCore.Qt.Orientation.Vertical
            if orient == VERTICAL
            else QtCore.Qt.Orientation.Horizontal,
            _qt_parent(parent),
        )
        super().__init__(bar, parent, **kwargs)
        self.command = command
        self._target_scrollbar: QtWidgets.QScrollBar | None = None
        self._syncing = False
        self._qt.valueChanged.connect(self._on_value_changed)

    def _attach_qt_scrollbar(self, scrollbar: QtWidgets.QScrollBar) -> None:
        self._target_scrollbar = scrollbar
        scrollbar.valueChanged.connect(lambda *_args: self._sync_from_target())
        scrollbar.rangeChanged.connect(lambda *_args: self._sync_from_target())
        self._sync_from_target()

    def _sync_from_target(self) -> None:
        if self._target_scrollbar is None:
            return
        self._syncing = True
        try:
            self._qt.setRange(
                self._target_scrollbar.minimum(),
                self._target_scrollbar.maximum(),
            )
            self._qt.setSingleStep(max(1, self._target_scrollbar.singleStep()))
            self._qt.setPageStep(max(1, self._target_scrollbar.pageStep()))
            self._qt.setValue(self._target_scrollbar.value())
        finally:
            self._syncing = False

    def _on_value_changed(self, value: int) -> None:
        if self._syncing:
            return
        if self._target_scrollbar is not None:
            self._target_scrollbar.setValue(value)
            return
        if self.command is not None:
            maximum = max(1, self._qt.maximum() - self._qt.minimum())
            self.command("moveto", (value - self._qt.minimum()) / maximum)

    def set(self, *args: Any) -> None:
        if self._target_scrollbar is not None:
            self._sync_from_target()
            return
        if len(args) < 2:
            return
        try:
            first = max(0.0, min(1.0, float(args[0])))
            last = max(first, min(1.0, float(args[1])))
        except (TypeError, ValueError):
            return
        scale = 1000
        page = max(1, int(round((last - first) * scale)))
        self._syncing = True
        try:
            self._qt.setPageStep(page)
            self._qt.setRange(0, max(0, scale - page))
            self._qt.setValue(min(self._qt.maximum(), int(round(first * scale))))
        finally:
            self._syncing = False


class Text(Widget):
    _winfo_class = "Text"
    _default_style = "TEntry"
    _style_kind = "entry"

    def __init__(self, parent: Any = None, **kwargs: Any) -> None:
        text = QtWidgets.QPlainTextEdit(_qt_parent(parent))
        super().__init__(text, parent, **kwargs)

    def insert(self, _index: str, text: str) -> None:
        self._qt.setPlainText(text)

    def configure(self, **kwargs: Any) -> None:
        yscrollcommand = kwargs.pop("yscrollcommand", None)
        if yscrollcommand is not None:
            _connect_scroll_command(self._qt.verticalScrollBar(), yscrollcommand)
            self._qt.setVerticalScrollBarPolicy(
                QtCore.Qt.ScrollBarPolicy.ScrollBarAlwaysOff
            )
        if kwargs.get("wrap") == WORD:
            self._qt.setLineWrapMode(QtWidgets.QPlainTextEdit.LineWrapMode.WidgetWidth)
            self._qt.setHorizontalScrollBarPolicy(
                QtCore.Qt.ScrollBarPolicy.ScrollBarAlwaysOff
            )
        state = kwargs.pop("state", None)
        if state is not None:
            self._qt.setReadOnly(state == DISABLED)
        super().configure(**kwargs)

    def yview(self, *args: Any) -> tuple[float, float] | None:
        return _scrollbar_view(self._qt.verticalScrollBar(), *args)


class Canvas(Widget):
    _winfo_class = "Canvas"
    _default_style = "TFrame"
    _style_kind = "frame"

    def __init__(self, parent: Any = None, width: int = 16, height: int = 16, **kwargs: Any) -> None:
        widget = QtWidgets.QWidget(_qt_parent(parent))
        widget.setMinimumSize(width, height)
        super().__init__(widget, parent, **kwargs)
        self._items: dict[int, dict[str, Any]] = {}

    def create_oval(self, *coords: Any, **kwargs: Any) -> int:
        item_id = next(_ITEM_IDS)
        self._items[item_id] = {"coords": coords, **kwargs}
        return item_id

    def itemconfig(self, item_id: int, **kwargs: Any) -> None:
        self._items.setdefault(item_id, {}).update(kwargs)


class Combobox(Entry):
    _winfo_class = "TCombobox"


class Scale(Widget):
    _winfo_class = "TScale"
    _default_style = "TScale"
    _style_kind = "frame"

    def __init__(self, parent: Any = None, orient: str = HORIZONTAL, **kwargs: Any) -> None:
        slider = QtWidgets.QSlider(
            QtCore.Qt.Orientation.Horizontal
            if orient == HORIZONTAL
            else QtCore.Qt.Orientation.Vertical,
            _qt_parent(parent),
        )
        super().__init__(slider, parent, **kwargs)


class Notebook(Widget):
    _winfo_class = "TNotebook"
    _default_style = "TNotebook"
    _style_kind = "notebook"

    def __init__(self, parent: Any = None, **kwargs: Any) -> None:
        notebook = QtWidgets.QTabWidget(_qt_parent(parent))
        notebook.setDocumentMode(True)
        notebook.setUsesScrollButtons(False)
        notebook.setElideMode(QtCore.Qt.TextElideMode.ElideNone)
        notebook.tabBar().setExpanding(False)
        notebook.tabBar().setDrawBase(False)
        super().__init__(notebook, parent, **kwargs)
        self._tabs: dict[Widget, int] = {}
        self._tab_widgets: list[Widget] = []
        self._tab_changed_callbacks: list[Callable[[Any], Any]] = []
        self._qt.currentChanged.connect(self._emit_tab_changed)
        self._sync_tab_visibility()

    def add(self, child: Widget, text: str = "", **_: Any) -> None:
        index = self._qt.addTab(child._qt, text)
        self._tabs[child] = index
        self._tab_widgets.append(child)
        if len(self._tab_widgets) == 1:
            self.select(0)
        else:
            self._apply_tab_button_styles()
        self._sync_tab_visibility()

    def _tab_index(self, child: Widget | int) -> int | None:
        if isinstance(child, int):
            if 0 <= child < self._qt.count():
                return int(child)
            return None
        return self._tabs.get(child)

    def tabs(self) -> tuple[Widget, ...]:
        return tuple(self._tab_widgets)

    def tab(self, child: Widget | int, option: str | None = None, **kwargs: Any) -> Any:
        index = self._tab_index(child)
        if index is None:
            return
        if option is not None and not kwargs:
            if option == "text":
                return self._qt.tabText(index)
            return None
        if "text" in kwargs:
            self._qt.setTabText(index, str(kwargs["text"]))
            self._apply_tab_button_styles()
            self._sync_tab_visibility()

    def select(self, child: Widget | int | None = None) -> Widget | None:
        if child is None:
            index = self._qt.currentIndex()
            for page, page_index in self._tabs.items():
                if page_index == index:
                    return page
            return None
        index = child if isinstance(child, int) else self._tabs.get(child)
        if index is not None:
            self._qt.setCurrentIndex(index)
            self._apply_tab_button_styles()
            self._sync_tab_visibility()
        return None

    def index(self, child: Widget | None) -> int:
        if child is None:
            raise TclError("bad notebook tab")
        index = self._tabs.get(child)
        if index is None:
            raise TclError("bad notebook tab")
        return index

    def bind(self, sequence: str, callback: Callable[[Any], Any], **_: Any) -> None:
        if sequence == "<<NotebookTabChanged>>":
            self._tab_changed_callbacks.append(callback)
            return
        super().bind(sequence, callback)

    def _emit_tab_changed(self, _index: int) -> None:
        if not hasattr(self, "_tab_changed_callbacks"):
            return
        event = SimpleNamespace(widget=self)
        for callback in list(self._tab_changed_callbacks):
            callback(event)

    def _apply_style(self) -> None:
        super()._apply_style()
        self._apply_tab_button_styles()
        self._sync_tab_visibility()

    def _sync_tab_visibility(self) -> None:
        tab_bar = self._qt.tabBar()
        hidden = self._style_name in _HIDDEN_NOTEBOOK_TABS
        if hasattr(self._qt, "setTabBarAutoHide"):
            self._qt.setTabBarAutoHide(False)
        tab_bar.setVisible(not hidden)
        if not hidden:
            tab_bar.setMinimumHeight(max(24, tab_bar.sizeHint().height()))

    def _apply_tab_button_styles(self) -> None:
        if not hasattr(self, "_tab_widgets"):
            return
        tab_style = f"{self._style_name}.Tab" if self._style_name else "TNotebook.Tab"
        default_style = "TNotebook.Tab"
        tab_config = _merged_style(tab_style, default_style)
        tab_maps = _merged_maps(tab_style, default_style)
        selected_config = dict(tab_config)
        unselected_config = dict(tab_config)
        hover_config = dict(tab_config)
        for option in ("background", "foreground", "bordercolor"):
            selected_value = _mapped_value(tab_maps, option, "selected")
            active_value = _mapped_value(tab_maps, option, "active")
            if selected_value is not None:
                selected_config[option] = selected_value
            if active_value is not None:
                hover_config[option] = active_value

        for config in (selected_config, unselected_config, hover_config):
            config.setdefault("bordercolor", "#d7e0ea")
            config.setdefault("borderwidth", 1)

        tab_font = _font_from_config(tab_config.get("font"))
        font_height = QtGui.QFontMetrics(tab_font or self._qt.font()).height()
        tab_height = max(28, font_height + 10)
        if self._style_name == "Eval.TNotebook":
            tab_height = max(tab_height, 33)
        self._qt.tabBar().setMinimumHeight(tab_height)
        pane_config = _merged_style(self._style_name, self._default_style)
        pane_bg = pane_config.get("background") or "#ffffff"
        if tab_font is not None:
            self._qt.tabBar().setFont(tab_font)

        if self._style_name == "Workspace.TNotebook":
            tab_height = max(38, font_height + 12)
            self._qt.setDocumentMode(True)
            self._qt.tabBar().setDrawBase(False)
            self._qt.tabBar().setMinimumHeight(tab_height)
            self._qt.setStyleSheet(
                "\n".join(
                    [
                        "QTabWidget::pane { "
                        f"background: transparent; border: 0; top: 0px; "
                        "}",
                        "QTabWidget::tab-bar { left: 0px; }",
                        "QTabBar { background: transparent; border: 0; }",
                        "QTabBar::tab { "
                        f"min-height: {tab_height - 2}px; padding: 0 16px; "
                        f"background: transparent; color: {TOKENS.text_secondary}; "
                        "font-weight: 600; border: 0; "
                        "border-bottom: 3px solid transparent; margin-right: 2px; "
                        "border-top-left-radius: 8px; border-top-right-radius: 8px; "
                        "}",
                        "QTabBar::tab:hover:!selected { "
                        f"background: {TOKENS.surface_hover}; color: {TOKENS.text}; "
                        "}",
                        "QTabBar::tab:selected { "
                        f"background: {TOKENS.accent_tint}; color: {TOKENS.accent_pressed}; "
                        f"border-bottom: 3px solid {TOKENS.accent}; "
                        "}",
                        "QTabBar::tab:focus { "
                        f"outline: 2px solid {TOKENS.focus}; "
                        "}",
                    ]
                )
            )
            return

        pane_border = "#cfdbe7"
        unselected_rules = _style_rules(
            {**unselected_config, "padding": None},
            widget_kind="button",
        )
        selected_rules = _style_rules(
            {**selected_config, "padding": None},
            widget_kind="button",
        )
        hover_rules = _style_rules(
            {**hover_config, "padding": None},
            widget_kind="button",
        )
        common_tab_rules = [
            "padding: 0px 8px;",
            f"min-height: {tab_height - 2}px;",
            "min-width: 0px;",
            "margin: 0px;",
            f"border: 1px solid {pane_border};",
            "border-bottom-left-radius: 0px;",
            "border-bottom-right-radius: 0px;",
        ]
        if self._style_name == "Eval.TNotebook":
            common_tab_rules.extend(
                [
                    "padding: 0px 10px;",
                    "margin-right: -1px;",
                    "border-top-left-radius: 0px;",
                    "border-top-right-radius: 0px;",
                ]
            )
        pane_padding = (
            "padding-left: 1px; padding-right: 1px; padding-bottom: 1px;"
            if self._style_name == "Eval.TNotebook"
            else ""
        )
        stylesheet = "\n".join(
            [
                "QTabWidget::pane { "
                f"background-color: {pane_bg}; border: 1px solid {pane_border}; top: -1px; "
                f"{pane_padding}"
                " }",
                "QTabWidget::tab-bar { left: 0px; }",
                "QTabBar::tab { " + " ".join(unselected_rules + common_tab_rules) + " }",
                "QTabBar::tab:selected { "
                + " ".join(selected_rules + common_tab_rules + [f"border-bottom-color: {pane_bg};"])
                + " }",
                "QTabBar::tab:hover { " + " ".join(hover_rules + common_tab_rules) + " }",
            ]
        )
        self._qt.setStyleSheet(stylesheet)


class PanedWindow(Widget):
    _winfo_class = "TPanedwindow"
    _default_style = "TPanedwindow"
    _style_kind = "frame"

    def __init__(self, parent: Any = None, orient: str = HORIZONTAL, **kwargs: Any) -> None:
        splitter = QtWidgets.QSplitter(
            QtCore.Qt.Orientation.Horizontal
            if orient == HORIZONTAL
            else QtCore.Qt.Orientation.Vertical,
            _qt_parent(parent),
        )
        splitter.setHandleWidth(6)
        super().__init__(splitter, parent, **kwargs)
        self._pending_sash: tuple[int, int] | None = None
        self._splitter_filter = _SplitterResizeFilter(self)
        splitter.installEventFilter(self._splitter_filter)

    def add(self, child: Widget, weight: int = 1, **_: Any) -> None:
        self._qt.addWidget(child._qt)
        self._qt.setStretchFactor(self._qt.count() - 1, int(weight))

    def sashpos(self, index: int, position: int) -> None:
        self._pending_sash = (int(index), int(position))
        self._apply_pending_sash()

    def _apply_pending_sash(self) -> None:
        if self._pending_sash is None:
            return
        index, position = self._pending_sash
        sizes = self._qt.sizes()
        if len(sizes) < 2:
            return
        total = self._qt.width()
        if self._qt.orientation() == QtCore.Qt.Orientation.Vertical:
            total = self._qt.height()
        handle_total = max(0, self._qt.count() - 1) * self._qt.handleWidth()
        total = max(sum(sizes) + handle_total, total, position + 1)
        available = max(1, total - handle_total)
        if index != 0:
            return
        sizes[0] = max(1, min(position, available - 1))
        sizes[1] = max(1, available - sizes[0])
        self._qt.setSizes(sizes)


class _TreeTableModel(QtCore.QAbstractTableModel):
    """Small model backing the transitional Treeview API with QTableView."""

    def __init__(self, owner: "Treeview") -> None:
        super().__init__(owner._qt)
        self.owner = owner

    def rowCount(self, parent: QtCore.QModelIndex = QtCore.QModelIndex()) -> int:
        return 0 if parent.isValid() else len(self.owner._rows)

    def columnCount(self, parent: QtCore.QModelIndex = QtCore.QModelIndex()) -> int:
        return 0 if parent.isValid() else len(self.owner._columns)

    def data(self, index: QtCore.QModelIndex, role: int = QtCore.Qt.ItemDataRole.DisplayRole) -> Any:
        if not index.isValid():
            return None
        row = index.row()
        column = index.column()
        if row >= len(self.owner._rows) or column >= len(self.owner._columns):
            return None
        value = self.owner._rows[row][column]
        if role == QtCore.Qt.ItemDataRole.DisplayRole:
            return value
        if role == QtCore.Qt.ItemDataRole.ToolTipRole:
            return value
        if role == QtCore.Qt.ItemDataRole.TextAlignmentRole:
            return self.owner._column_alignment(column)
        item_id = self.owner._items[row]
        tags = self.owner._item_tags.get(item_id, ())
        if role in {
            QtCore.Qt.ItemDataRole.BackgroundRole,
            QtCore.Qt.ItemDataRole.ForegroundRole,
        }:
            style: dict[str, Any] = {}
            for tag in tags:
                style.update(self.owner._tag_styles.get(tag, {}))
            key = (
                "background"
                if role == QtCore.Qt.ItemDataRole.BackgroundRole
                else "foreground"
            )
            color = _as_color(style.get(key))
            return QtGui.QBrush(QtGui.QColor(color)) if color else None
        return None

    def headerData(
        self,
        section: int,
        orientation: QtCore.Qt.Orientation,
        role: int = QtCore.Qt.ItemDataRole.DisplayRole,
    ) -> Any:
        if (
            orientation == QtCore.Qt.Orientation.Horizontal
            and role == QtCore.Qt.ItemDataRole.DisplayRole
            and section < len(self.owner._columns)
        ):
            column = self.owner._columns[section]
            return self.owner._headings.get(column, column)
        return None

    def flags(self, index: QtCore.QModelIndex) -> QtCore.Qt.ItemFlag:
        if not index.isValid():
            return QtCore.Qt.ItemFlag.NoItemFlags
        return (
            QtCore.Qt.ItemFlag.ItemIsEnabled
            | QtCore.Qt.ItemFlag.ItemIsSelectable
        )


class Treeview(Widget):
    _winfo_class = "Treeview"
    _default_style = "Treeview"
    _style_kind = "tree"

    def __init__(
        self,
        parent: Any = None,
        columns: tuple[str, ...] | list[str] = (),
        show: str | None = None,
        height: int | None = None,
        **kwargs: Any,
    ) -> None:
        table = QtWidgets.QTableView(_qt_parent(parent))
        table.verticalHeader().setVisible(False)
        table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows)
        table.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.SingleSelection)
        super().__init__(table, parent, **kwargs)
        self._columns: list[str] = []
        self._items: list[str] = []
        self._rows: list[list[str]] = []
        self._item_rows: dict[str, int] = {}
        self._headings: dict[str, str] = {}
        self._column_anchors: dict[str, str] = {}
        self._item_tags: dict[str, tuple[str, ...]] = {}
        self._tag_styles: dict[str, dict[str, Any]] = {}
        self._model = _TreeTableModel(self)
        table.setModel(self._model)
        table.setAlternatingRowColors(False)
        self._sync_tree_dimensions()
        if height is not None:
            rowheight = table.verticalHeader().defaultSectionSize()
            header_height = table.horizontalHeader().height()
            table.setMinimumHeight(header_height + height * rowheight + 2)
        self.configure(columns=columns)

    def _sync_tree_dimensions(self) -> None:
        config = _effective_style_config(self._style_name, self._default_style)
        rowheight = config.get("rowheight")
        if rowheight:
            height = int(rowheight)
            self._qt.verticalHeader().setMinimumSectionSize(height)
            self._qt.verticalHeader().setDefaultSectionSize(height)
            for row in range(self._model.rowCount()):
                self._qt.setRowHeight(row, height)

    def configure(self, **kwargs: Any) -> None:
        columns = kwargs.pop("columns", None)
        kwargs.pop("displaycolumns", None)
        yscrollcommand = kwargs.pop("yscrollcommand", None)
        xscrollcommand = kwargs.pop("xscrollcommand", None)
        if columns is not None:
            self._model.beginResetModel()
            self._columns = list(columns)
            width = len(self._columns)
            self._rows = [
                (row[:width] + [""] * max(0, width - len(row)))
                for row in self._rows
            ]
            self._model.endResetModel()
        if yscrollcommand is not None:
            _connect_scroll_command(self._qt.verticalScrollBar(), yscrollcommand)
            self._qt.setVerticalScrollBarPolicy(
                QtCore.Qt.ScrollBarPolicy.ScrollBarAlwaysOff
            )
        if xscrollcommand is not None:
            _connect_scroll_command(self._qt.horizontalScrollBar(), xscrollcommand)
            self._qt.setHorizontalScrollBarPolicy(
                QtCore.Qt.ScrollBarPolicy.ScrollBarAlwaysOff
            )
        super().configure(**kwargs)

    def heading(self, column: str, text: str = "", **_: Any) -> None:
        self._headings[column] = text
        if column in self._columns:
            index = self._columns.index(column)
            self._model.headerDataChanged.emit(
                QtCore.Qt.Orientation.Horizontal,
                index,
                index,
            )

    def column(
        self,
        column: str,
        width: int | None = None,
        minwidth: int | None = None,
        anchor: str | None = None,
        stretch: bool = True,
        **_: Any,
    ) -> None:
        if column not in self._columns:
            return
        index = self._columns.index(column)
        if anchor is not None:
            self._column_anchors[column] = anchor
        if width is not None:
            self._qt.setColumnWidth(index, width)
        if minwidth is not None:
            self._qt.horizontalHeader().setMinimumSectionSize(max(1, int(minwidth)))
        mode = (
            QtWidgets.QHeaderView.ResizeMode.Stretch
            if stretch
            else QtWidgets.QHeaderView.ResizeMode.Interactive
        )
        self._qt.horizontalHeader().setSectionResizeMode(index, mode)
        if self._model.rowCount():
            self._model.dataChanged.emit(
                self._model.index(0, index),
                self._model.index(self._model.rowCount() - 1, index),
                [QtCore.Qt.ItemDataRole.TextAlignmentRole],
            )

    def _column_alignment(self, index: int) -> QtCore.Qt.AlignmentFlag:
        column = self._columns[index] if index < len(self._columns) else ""
        return _qt_alignment(self._column_anchors.get(column, "center"), None)

    def insert(
        self,
        _parent: str,
        _index: Any,
        iid: str | None = None,
        values: tuple[Any, ...] | list[Any] = (),
        tags: tuple[str, ...] | list[str] = (),
        **_: Any,
    ) -> str:
        item_id = iid or f"I{next(_ITEM_IDS)}"
        row = len(self._rows)
        self._model.beginInsertRows(QtCore.QModelIndex(), row, row)
        self._items.append(item_id)
        self._item_rows[item_id] = row
        self._item_tags[item_id] = tuple(str(tag) for tag in tags)
        row_values = [str(value) for value in values[: len(self._columns)]]
        row_values.extend([""] * (len(self._columns) - len(row_values)))
        self._rows.append(row_values)
        self._model.endInsertRows()
        self._sync_tree_dimensions()
        return item_id

    def delete(self, *items: str) -> None:
        if not items:
            return
        removed = set(items)
        self._model.beginResetModel()
        kept = [
            (item_id, row)
            for item_id, row in zip(self._items, self._rows)
            if item_id not in removed
        ]
        self._items = [item_id for item_id, _row in kept]
        self._rows = [row for _item_id, row in kept]
        for item_id in removed:
            self._item_tags.pop(item_id, None)
        self._rebuild_rows()
        self._model.endResetModel()

    def _rebuild_rows(self) -> None:
        self._item_rows = {item_id: index for index, item_id in enumerate(self._items)}

    def get_children(self) -> tuple[str, ...]:
        return tuple(self._items)

    def selection(self) -> tuple[str, ...]:
        rows = {index.row() for index in self._qt.selectionModel().selectedRows()}
        return tuple(self._items[row] for row in sorted(rows) if row < len(self._items))

    def selection_set(self, item_id: str) -> None:
        row = self._item_rows.get(item_id)
        if row is not None:
            self._qt.selectRow(row)

    def focus(self, item_id: str | None = None) -> str | None:
        if item_id is not None:
            self.selection_set(item_id)
            return item_id
        selected = self.selection()
        return selected[0] if selected else None

    def tag_configure(self, tag: str, **kwargs: Any) -> None:
        self._tag_styles.setdefault(tag, {}).update(kwargs)
        if self._model.rowCount() and self._model.columnCount():
            self._model.dataChanged.emit(
                self._model.index(0, 0),
                self._model.index(
                    self._model.rowCount() - 1,
                    self._model.columnCount() - 1,
                ),
                [
                    QtCore.Qt.ItemDataRole.BackgroundRole,
                    QtCore.Qt.ItemDataRole.ForegroundRole,
                ],
            )

    def yview(self, *args: Any) -> tuple[float, float] | None:
        return _scrollbar_view(self._qt.verticalScrollBar(), *args)

    def xview(self, *args: Any) -> tuple[float, float] | None:
        return _scrollbar_view(self._qt.horizontalScrollBar(), *args)


class Menu:
    def __init__(self, parent: Any = None, tearoff: bool = False, **_: Any) -> None:
        self._parent = parent
        self._menu = QtWidgets.QMenu(_qt_parent(parent))
        self._entries: list[dict[str, Any]] = []
        self._style_options: dict[str, Any] = {}

    def configure(self, **kwargs: Any) -> None:
        self._style_options.update(kwargs)
        options = self._style_options
        bg = _as_color(options.get("background"))
        fg = _as_color(options.get("foreground"))
        active_bg = _as_color(options.get("activebackground"))
        active_fg = _as_color(options.get("activeforeground"))
        disabled_fg = _as_color(options.get("disabledforeground"))
        bordercolor = _as_color(options.get("bordercolor")) or "#cbd5e1"
        borderwidth = int(options.get("borderwidth") or 1)
        rules = []
        if bg:
            rules.append(f"background-color: {bg};")
        if fg:
            rules.append(f"color: {fg};")
        rules.extend(_font_rules(options.get("font")))
        rules.append(f"border: {borderwidth}px solid {bordercolor};")
        blocks = [f"QMenu {{ {' '.join(rules)} padding: 2px; }}"]
        item_rules = ["padding: 5px 28px 5px 12px;"]
        if bg:
            item_rules.append(f"background-color: {bg};")
        blocks.append(f"QMenu::item {{ {' '.join(item_rules)} }}")
        selected_rules = []
        if active_bg:
            selected_rules.append(f"background-color: {active_bg};")
        if active_fg:
            selected_rules.append(f"color: {active_fg};")
        if selected_rules:
            blocks.append(f"QMenu::item:selected {{ {' '.join(selected_rules)} }}")
        if disabled_fg:
            blocks.append(f"QMenu::item:disabled {{ color: {disabled_fg}; }}")
        blocks.append(
            "QMenu::separator { height: 1px; "
            f"background: {bordercolor}; margin: 4px 8px; }}"
        )
        self._menu.setStyleSheet("\n".join(blocks))

    config = configure

    def add_command(
        self,
        label: str,
        command: Callable[[], Any] | None = None,
        **kwargs: Any,
    ) -> None:
        action = self._menu.addAction(label)
        state = str(kwargs.get("state", NORMAL))
        action.setEnabled(state != DISABLED)
        if command is not None:
            action.triggered.connect(lambda _checked=False, cb=command: cb())
        self._entries.append(
            {
                "type": "command",
                "label": str(label),
                "state": state,
                "command": command,
                "action": action,
            }
        )

    def add_separator(self) -> None:
        action = self._menu.addSeparator()
        self._entries.append({"type": "separator", "action": action})

    def delete(self, start: int, end: Any = None) -> None:
        self._menu.clear()
        self._entries.clear()

    def index(self, index: Any) -> int | None:
        if index == END:
            return len(self._entries) - 1 if self._entries else None
        return int(index)

    def type(self, index: int) -> str:
        return str(self._entries[index]["type"])

    def entryconfigure(self, index: int, **kwargs: Any) -> None:
        entry = self._entries[int(index)]
        action = entry.get("action")
        if "label" in kwargs and action is not None:
            entry["label"] = str(kwargs["label"])
            action.setText(entry["label"])
        if "state" in kwargs and action is not None:
            state = str(kwargs["state"])
            entry["state"] = state
            action.setEnabled(state != DISABLED)

    def entrycget(self, index: int, option: str) -> str:
        entry = self._entries[int(index)]
        normalized = str(option).lstrip("-")
        if normalized == "label":
            return str(entry.get("label", ""))
        if normalized == "state":
            return str(entry.get("state", NORMAL))
        if normalized == "menu" and "menu" in entry:
            return str(entry["menu"])
        raise TclError(f"unknown option {option!r}")

    def invoke(self, index: int) -> Any:
        entry = self._entries[int(index)]
        if entry.get("type") != "command" or entry.get("state", NORMAL) == DISABLED:
            return None
        command = entry.get("command")
        if command is not None:
            return command()
        action = entry.get("action")
        if action is not None:
            action.trigger()
        return None

    def nametowidget(self, *_args: Any, **_kwargs: Any) -> Any:
        raise TclError("no named widget")


class Style:
    def __init__(self, _root: Any = None) -> None:
        return

    def theme_use(self, _name: str) -> None:
        return

    def configure(self, style_name: str, **kwargs: Any) -> None:
        _STYLE_CONFIGS.setdefault(style_name, {}).update(kwargs)

    def map(self, style_name: str, **kwargs: Any) -> None:
        style_maps = _STYLE_MAPS.setdefault(style_name, {})
        for option, values in kwargs.items():
            normalized: list[tuple[str, Any]] = []
            for value in values:
                if isinstance(value, tuple) and len(value) >= 2:
                    normalized.append((str(value[0]), value[-1]))
            style_maps[option] = normalized

    def layout(self, style_name: str, layout_spec: Any = None, **_kwargs: Any) -> None:
        if style_name.endswith(".Tab") and layout_spec == []:
            _HIDDEN_NOTEBOOK_TABS.add(style_name[: -len(".Tab")])


class PhotoImage:
    def __init__(self, file: str | None = None, **_: Any) -> None:
        self.file = file
        self.pixmap = QtGui.QPixmap(file) if file else QtGui.QPixmap()


def _file_filter(filetypes: Any) -> str:
    if not filetypes:
        return "All Files (*)"
    parts = []
    for label, pattern in filetypes:
        if isinstance(pattern, (tuple, list)):
            pattern_text = " ".join(pattern)
        else:
            pattern_text = str(pattern)
        parts.append(f"{label} ({pattern_text})")
    return ";;".join(parts)


class _FileDialog:
    def askopenfilename(self, **kwargs: Any) -> str:
        _ensure_app()
        path, _filter = QtWidgets.QFileDialog.getOpenFileName(
            _qt_parent(kwargs.get("parent")),
            kwargs.get("title", "Open"),
            str(kwargs.get("initialdir") or Path.home()),
            _file_filter(kwargs.get("filetypes")),
        )
        return path

    def asksaveasfilename(self, **kwargs: Any) -> str:
        _ensure_app()
        initialdir = Path(kwargs.get("initialdir") or Path.home())
        initialfile = kwargs.get("initialfile")
        start = str(initialdir / initialfile) if initialfile else str(initialdir)
        path, _filter = QtWidgets.QFileDialog.getSaveFileName(
            _qt_parent(kwargs.get("parent")),
            kwargs.get("title", "Save"),
            start,
            _file_filter(kwargs.get("filetypes")),
        )
        if path and kwargs.get("defaultextension") and "." not in Path(path).name:
            path += str(kwargs["defaultextension"])
        return path


class _MessageBox:
    def showinfo(self, title: str, message: str) -> None:
        _ensure_app()
        QtWidgets.QMessageBox.information(None, title, message)

    def showerror(self, title: str, message: str) -> None:
        _ensure_app()
        QtWidgets.QMessageBox.critical(None, title, message)


filedialog = _FileDialog()
messagebox = _MessageBox()


tk = SimpleNamespace(
    BooleanVar=BooleanVar,
    BOTH=BOTH,
    Button=Button,
    Canvas=Canvas,
    Checkbutton=Checkbutton,
    Combobox=Combobox,
    DISABLED=DISABLED,
    DoubleVar=DoubleVar,
    END=END,
    Entry=Entry,
    Frame=Frame,
    HORIZONTAL=HORIZONTAL,
    Label=Label,
    LabelFrame=LabelFrame,
    LEFT=LEFT,
    Menu=Menu,
    Menubutton=Menubutton,
    NORMAL=NORMAL,
    Notebook=Notebook,
    PanedWindow=PanedWindow,
    PhotoImage=PhotoImage,
    Radiobutton=Radiobutton,
    RIGHT=RIGHT,
    Scale=Scale,
    Scrollbar=Scrollbar,
    Separator=Separator,
    SOLID=SOLID,
    StringVar=StringVar,
    Style=Style,
    TclError=TclError,
    Text=Text,
    Tk=Tk,
    Toplevel=Toplevel,
    Treeview=Treeview,
    VERTICAL=VERTICAL,
    Widget=Widget,
    WORD=WORD,
    X=X,
)

ttk = SimpleNamespace(
    Button=Button,
    Checkbutton=Checkbutton,
    Combobox=Combobox,
    Entry=Entry,
    Frame=Frame,
    Label=Label,
    LabelFrame=LabelFrame,
    Menubutton=Menubutton,
    Notebook=Notebook,
    PanedWindow=PanedWindow,
    Radiobutton=Radiobutton,
    Scale=Scale,
    Scrollbar=Scrollbar,
    Separator=Separator,
    Style=Style,
    Treeview=Treeview,
)
