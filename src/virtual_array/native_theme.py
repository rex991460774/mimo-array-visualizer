"""Fluent 2 inspired application-wide tokens and native Qt styling.

The compatibility widgets in :mod:`virtual_array.qt_tk` still generate local
styles, so this module deliberately owns the shared colour, geometry and
interaction vocabulary.  New native Qt surfaces should use these tokens and
dynamic roles instead of adding one-off stylesheets.
"""

from __future__ import annotations

from dataclasses import dataclass

from PySide6 import QtCore, QtGui, QtWidgets


@dataclass(frozen=True)
class FluentTokens:
    canvas: str = "#f4f7fb"
    surface: str = "#ffffff"
    surface_subtle: str = "#f8fafc"
    surface_muted: str = "#eef3f8"
    surface_hover: str = "#edf4fb"
    surface_pressed: str = "#e1edf8"
    surface_selected: str = "#e6f2fb"
    border: str = "#d8e1eb"
    border_strong: str = "#b7c3d0"
    control_border: str = "#8a94a6"
    text: str = "#182230"
    text_secondary: str = "#5b687a"
    text_tertiary: str = "#738095"
    accent: str = "#0f6cbd"
    accent_hover: str = "#115ea3"
    accent_pressed: str = "#0c3b5e"
    accent_tint: str = "#e6f2fb"
    focus: str = "#0078d4"
    success: str = "#107c10"
    success_fill: str = "#eef8ee"
    warning: str = "#835b00"
    warning_fill: str = "#fff4ce"
    danger: str = "#c50f1f"
    danger_fill: str = "#fde7e9"
    disabled: str = "#e7edf4"
    radius: int = 8
    card_radius: int = 12
    base_font_pt: int = 10
    caption_font_pt: int = 9


TOKENS = FluentTokens()


def application_font() -> QtGui.QFont:
    """Return a system-friendly CJK-capable UI font."""

    font = QtGui.QFont("Segoe UI Variable Text")
    if hasattr(font, "setFamilies"):
        font.setFamilies(
            [
                "Segoe UI Variable Text",
                "Microsoft YaHei UI",
                "Microsoft YaHei",
                "PingFang SC",
                "Noto Sans CJK SC",
                "Segoe UI",
            ]
        )
    font.setPointSize(TOKENS.base_font_pt)
    return font


def application_palette() -> QtGui.QPalette:
    """Build a complete light palette for controls not covered by QSS."""

    t = TOKENS
    palette = QtGui.QPalette()
    palette.setColor(QtGui.QPalette.ColorRole.Window, QtGui.QColor(t.canvas))
    palette.setColor(QtGui.QPalette.ColorRole.WindowText, QtGui.QColor(t.text))
    palette.setColor(QtGui.QPalette.ColorRole.Base, QtGui.QColor(t.surface))
    palette.setColor(QtGui.QPalette.ColorRole.AlternateBase, QtGui.QColor(t.surface_subtle))
    palette.setColor(QtGui.QPalette.ColorRole.ToolTipBase, QtGui.QColor(t.text))
    palette.setColor(QtGui.QPalette.ColorRole.ToolTipText, QtGui.QColor("#ffffff"))
    palette.setColor(QtGui.QPalette.ColorRole.Text, QtGui.QColor(t.text))
    palette.setColor(QtGui.QPalette.ColorRole.Button, QtGui.QColor(t.surface))
    palette.setColor(QtGui.QPalette.ColorRole.ButtonText, QtGui.QColor(t.text))
    palette.setColor(QtGui.QPalette.ColorRole.Highlight, QtGui.QColor(t.accent_tint))
    palette.setColor(QtGui.QPalette.ColorRole.HighlightedText, QtGui.QColor(t.text))
    palette.setColor(
        QtGui.QPalette.ColorGroup.Disabled,
        QtGui.QPalette.ColorRole.Text,
        QtGui.QColor(t.text_tertiary),
    )
    palette.setColor(
        QtGui.QPalette.ColorGroup.Disabled,
        QtGui.QPalette.ColorRole.ButtonText,
        QtGui.QColor(t.text_tertiary),
    )
    return palette


def application_stylesheet() -> str:
    t = TOKENS
    return f"""
    QMainWindow {{
        background: {t.canvas};
        color: {t.text};
    }}
    QDialog, QMessageBox, QProgressDialog {{
        background: {t.surface};
        color: {t.text};
    }}
    QWidget {{
        color: {t.text};
        selection-background-color: {t.surface_selected};
        selection-color: {t.text};
    }}
    QFrame[surfaceRole="card"] {{
        background: {t.surface};
        border: 1px solid {t.border};
        border-radius: {t.card_radius}px;
    }}
    QLabel[fluentRole="caption"] {{
        color: {t.text_secondary};
        font-size: {t.caption_font_pt}pt;
    }}
    QLabel[fluentRole="muted"] {{ color: {t.text_secondary}; }}
    QLabel[fluentRole="success"] {{ color: {t.success}; }}
    QLabel[fluentRole="warning"] {{ color: {t.warning}; }}
    QLabel[fluentRole="danger"] {{ color: {t.danger}; }}
    QLabel[fluentRole="callout-neutral"] {{
        background: {t.surface_subtle};
        color: {t.text_secondary};
        border: 1px solid {t.border};
        border-radius: {t.radius}px;
        padding: 8px 10px;
    }}
    QLabel[fluentRole="callout-success"] {{
        background: {t.success_fill};
        color: {t.success};
        border: 1px solid #9ac99a;
        border-radius: {t.radius}px;
        padding: 8px 10px;
    }}
    QLabel[fluentRole="callout-warning"] {{
        background: {t.warning_fill};
        color: {t.warning};
        border: 1px solid #d2b866;
        border-radius: {t.radius}px;
        padding: 8px 10px;
    }}
    QLabel[fluentRole="callout-danger"] {{
        background: {t.danger_fill};
        color: {t.danger};
        border: 1px solid #d99aa2;
        border-radius: {t.radius}px;
        padding: 8px 10px;
    }}

    QMenuBar {{
        background: {t.surface};
        border-bottom: 1px solid {t.border};
        padding: 2px 12px;
        spacing: 2px;
    }}
    QMenuBar::item {{
        background: transparent;
        border-radius: {t.radius}px;
        padding: 6px 11px;
    }}
    QMenuBar::item:selected {{
        background: {t.surface_hover};
        color: {t.accent_pressed};
    }}
    QMenuBar::item:pressed {{ background: {t.surface_pressed}; }}
    QMenu {{
        background: {t.surface};
        border: 1px solid {t.border_strong};
        border-radius: {t.radius}px;
        padding: 6px;
    }}
    QMenu::item {{
        border-radius: 6px;
        padding: 7px 34px 7px 10px;
    }}
    QMenu::item:selected {{
        background: {t.surface_selected};
        color: {t.accent_pressed};
    }}
    QMenu::separator {{
        height: 1px;
        background: {t.border};
        margin: 5px 8px;
    }}

    QPushButton, QToolButton {{
        min-height: 32px;
        background: {t.surface};
        border: 1px solid {t.control_border};
        border-radius: {t.radius}px;
        padding: 1px 12px;
    }}
    QPushButton:hover, QToolButton:hover {{
        background: {t.surface_hover};
        border-color: {t.control_border};
    }}
    QPushButton:pressed, QToolButton:pressed {{
        background: {t.surface_pressed};
        border-color: {t.accent_pressed};
    }}
    QPushButton:checked, QToolButton:checked,
    QPushButton[fluentState="active"], QToolButton[fluentState="active"] {{
        background: {t.accent_tint};
        border-color: {t.accent};
        color: {t.accent_pressed};
        font-weight: 600;
    }}
    QPushButton:focus, QToolButton:focus,
    QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QDoubleSpinBox:focus,
    QAbstractItemView:focus {{
        border: 2px solid {t.focus};
    }}
    QPushButton:disabled, QToolButton:disabled {{
        background: {t.disabled};
        border-color: {t.border};
        color: {t.text_tertiary};
    }}
    QPushButton[fluentRole="primary"], QToolButton[fluentRole="primary"] {{
        min-height: 34px;
        background: {t.accent};
        border-color: {t.accent};
        color: white;
        font-weight: 600;
    }}
    QPushButton[fluentRole="primary"]:hover,
    QToolButton[fluentRole="primary"]:hover {{
        background: {t.accent_hover};
        border-color: {t.accent_hover};
    }}
    QPushButton[fluentRole="primary"]:pressed,
    QToolButton[fluentRole="primary"]:pressed {{
        background: {t.accent_pressed};
        border-color: {t.accent_pressed};
    }}
    QPushButton[fluentRole="danger"] {{
        color: {t.danger};
        border-color: #d99aa2;
    }}
    QPushButton[fluentRole="danger"]:hover {{ background: {t.danger_fill}; }}
    QPushButton[fluentRole="quiet"], QToolButton[fluentRole="quiet"] {{
        background: transparent;
        border-color: transparent;
        color: {t.text_secondary};
    }}
    QPushButton[fluentRole="quiet"]:hover, QToolButton[fluentRole="quiet"]:hover {{
        background: {t.surface_hover};
        color: {t.text};
    }}

    QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox {{
        min-height: 32px;
        background: {t.surface};
        border: 1px solid {t.control_border};
        border-radius: {t.radius}px;
        padding: 1px 9px;
    }}
    QLineEdit:hover, QComboBox:hover, QSpinBox:hover, QDoubleSpinBox:hover {{
        border-color: {t.accent};
    }}
    QLineEdit:disabled, QComboBox:disabled, QSpinBox:disabled, QDoubleSpinBox:disabled {{
        background: {t.disabled};
        border-color: {t.border};
        color: {t.text_tertiary};
    }}
    QComboBox::drop-down {{ border: 0; width: 28px; }}
    QComboBox QAbstractItemView {{
        background: {t.surface};
        border: 1px solid {t.control_border};
        selection-background-color: {t.surface_selected};
        outline: 0;
    }}
    QCheckBox, QRadioButton {{ spacing: 7px; }}
    QCheckBox:hover, QRadioButton:hover {{ color: {t.accent_pressed}; }}

    QGroupBox {{
        background: {t.surface};
        border: 1px solid {t.border};
        border-radius: {t.card_radius}px;
        margin-top: 14px;
        padding: 12px 10px 10px 10px;
        font-weight: 600;
    }}
    QGroupBox::title {{
        subcontrol-origin: margin;
        left: 12px;
        padding: 0 5px;
        color: {t.text_secondary};
    }}
    QTabWidget::pane {{
        background: {t.surface};
        border: 1px solid {t.border};
        border-radius: {t.card_radius}px;
    }}
    QTabBar::tab {{
        min-height: 36px;
        min-width: 104px;
        background: transparent;
        color: {t.text_secondary};
        border: 0;
        border-bottom: 3px solid transparent;
        padding: 0 14px;
        margin-right: 2px;
        font-weight: 600;
    }}
    QTabBar::tab:selected {{
        background: {t.surface_selected};
        color: {t.accent_pressed};
        border-bottom-color: {t.accent};
    }}
    QTabBar::tab:hover:!selected {{
        background: {t.surface_hover};
        color: {t.text};
    }}

    QTableView, QTreeView, QListView, QTextBrowser, QPlainTextEdit, QTextEdit {{
        background: {t.surface};
        alternate-background-color: {t.surface_subtle};
        border: 1px solid {t.control_border};
        border-radius: {t.radius}px;
        gridline-color: {t.border};
        outline: 0;
    }}
    QTableView::item, QTreeView::item, QListView::item {{
        min-height: 30px;
        padding: 2px 7px;
        border-bottom: 1px solid {t.border};
    }}
    QTableView::item:hover, QTreeView::item:hover, QListView::item:hover {{
        background: {t.surface_hover};
    }}
    QTableView::item:selected, QTreeView::item:selected, QListView::item:selected {{
        background: {t.surface_selected};
        color: {t.accent_pressed};
        border-bottom: 2px solid {t.accent};
        font-weight: 600;
    }}
    QHeaderView::section {{
        min-height: 34px;
        background: {t.surface_muted};
        color: {t.text_secondary};
        border: 0;
        border-right: 1px solid {t.border};
        border-bottom: 1px solid {t.border_strong};
        padding: 2px 8px;
        font-weight: 600;
    }}
    QTextBrowser, QPlainTextEdit, QTextEdit {{ padding: 8px; }}

    QScrollBar:vertical {{
        background: transparent;
        width: 11px;
        margin: 2px;
    }}
    QScrollBar::handle:vertical {{
        background: {t.control_border};
        min-height: 28px;
        border-radius: 4px;
    }}
    QScrollBar::handle:vertical:hover {{ background: {t.control_border}; }}
    QScrollBar:horizontal {{
        background: transparent;
        height: 11px;
        margin: 2px;
    }}
    QScrollBar::handle:horizontal {{
        background: {t.control_border};
        min-width: 28px;
        border-radius: 4px;
    }}
    QScrollBar::handle:horizontal:hover {{ background: {t.control_border}; }}
    QScrollBar::add-line, QScrollBar::sub-line {{ width: 0; height: 0; }}
    QScrollBar::add-page, QScrollBar::sub-page {{ background: transparent; }}

    QStatusBar {{
        background: {t.surface};
        border-top: 1px solid {t.border};
        color: {t.text_secondary};
        min-height: 26px;
        padding-left: 8px;
    }}
    QStatusBar::item {{ border: 0; }}
    QSplitter::handle {{ background: transparent; }}
    QSplitter::handle:horizontal {{ width: 10px; }}
    QSplitter::handle:vertical {{ height: 10px; }}
    QSplitter::handle:hover {{
        background: {t.surface_selected};
        border-radius: 4px;
    }}
    QProgressBar {{
        min-height: 8px;
        max-height: 8px;
        background: {t.surface_muted};
        border: 0;
        border-radius: 4px;
        text-align: center;
    }}
    QProgressBar::chunk {{
        background: {t.accent};
        border-radius: 4px;
    }}
    QToolTip {{
        background: {t.text};
        color: white;
        border: 0;
        border-radius: 6px;
        padding: 6px 9px;
    }}
    """


def apply_native_theme(app: QtWidgets.QApplication) -> None:
    """Apply one deterministic light theme to the whole application."""

    if "Fusion" in QtWidgets.QStyleFactory.keys():
        app.setStyle("Fusion")
    app.setFont(application_font())
    app.setPalette(application_palette())
    app.setStyleSheet(application_stylesheet())


def _repolish(widget: QtWidgets.QWidget) -> None:
    widget.style().unpolish(widget)
    widget.style().polish(widget)
    widget.update()


def mark_primary(widget: QtWidgets.QWidget) -> None:
    """Give a button the single primary-action treatment.

    A local rule is retained for compatibility buttons whose generated widget
    stylesheet would otherwise outrank the application property selector.
    """

    widget.setProperty("fluentRole", "primary")
    if not widget.objectName():
        widget.setObjectName(f"fluentPrimary_{id(widget)}")
    selector = f"#{widget.objectName()}"
    local_rules = f"""
    {selector} {{
        min-height: 34px;
        background: {TOKENS.accent};
        border: 1px solid {TOKENS.accent};
        border-radius: {TOKENS.radius}px;
        color: white;
        font-weight: 600;
    }}
    {selector}:hover {{
        background: {TOKENS.accent_hover};
        border-color: {TOKENS.accent_hover};
    }}
    {selector}:pressed {{
        background: {TOKENS.accent_pressed};
        border-color: {TOKENS.accent_pressed};
    }}
    {selector}:disabled {{
        background: {TOKENS.disabled};
        border-color: {TOKENS.border};
        color: {TOKENS.text_tertiary};
    }}
    {selector}:focus {{ border: 2px solid {TOKENS.focus}; }}
    """
    widget.setStyleSheet(f"{widget.styleSheet()}\n{local_rules}")
    _repolish(widget)


def mark_danger(widget: QtWidgets.QWidget) -> None:
    widget.setProperty("fluentRole", "danger")
    _repolish(widget)


def mark_quiet(widget: QtWidgets.QWidget) -> None:
    widget.setProperty("fluentRole", "quiet")
    _repolish(widget)


def mark_callout(widget: QtWidgets.QWidget, role: str) -> None:
    """Apply a semantic, non-blocking callout treatment to a label."""

    normalized = role if role in {"neutral", "success", "warning", "danger"} else "neutral"
    widget.setProperty("fluentRole", f"callout-{normalized}")
    palette = {
        "neutral": (TOKENS.surface_subtle, TOKENS.text_secondary, TOKENS.border),
        "success": (TOKENS.success_fill, TOKENS.success, "#9ac99a"),
        "warning": (TOKENS.warning_fill, TOKENS.warning, "#d2b866"),
        "danger": (TOKENS.danger_fill, TOKENS.danger, "#d99aa2"),
    }
    fill, color, border = palette[normalized]
    if not widget.objectName():
        widget.setObjectName(f"fluentCallout_{id(widget)}")
    base_stylesheet = widget.property("fluentCalloutBaseStyleSheet")
    if base_stylesheet is None:
        base_stylesheet = widget.styleSheet()
        widget.setProperty("fluentCalloutBaseStyleSheet", base_stylesheet)
    selector = f"#{widget.objectName()}"
    widget.setStyleSheet(
        f"{base_stylesheet}\n{selector} {{ background: {fill}; color: {color}; "
        f"border: 1px solid {border}; border-radius: {TOKENS.radius}px; "
        "padding: 8px 10px; }}"
    )
    _repolish(widget)


def fit_dialog_to_parent(
    dialog: QtWidgets.QDialog,
    parent: QtWidgets.QWidget | None,
    *,
    preferred_size: tuple[int, int],
    minimum_size: tuple[int, int] = (620, 440),
    margin: int = 24,
) -> QtCore.QRect:
    """Size and centre a dialog inside both its parent and working screen.

    This keeps configuration windows usable after DPI, monitor or remote
    desktop changes.  The requested minimum is itself clamped instead of
    forcing the top-level window outside a small workspace.
    """

    screen = dialog.screen() or QtGui.QGuiApplication.primaryScreen()
    if screen is None:
        target = QtCore.QRect(0, 0, *preferred_size)
    else:
        available = screen.availableGeometry().adjusted(margin, margin, -margin, -margin)
        bounds = QtCore.QRect(available)
        if parent is not None and parent.isVisible():
            parent_bounds = parent.frameGeometry().adjusted(
                margin, margin, -margin, -margin
            )
            intersection = bounds.intersected(parent_bounds)
            if intersection.width() >= 480 and intersection.height() >= 360:
                bounds = intersection

        width = max(360, min(int(preferred_size[0]), bounds.width()))
        height = max(300, min(int(preferred_size[1]), bounds.height()))
        target = QtCore.QRect(0, 0, width, height)
        target.moveCenter(bounds.center())
        if target.left() < bounds.left():
            target.moveLeft(bounds.left())
        if target.top() < bounds.top():
            target.moveTop(bounds.top())

    dialog.setMinimumSize(
        min(int(minimum_size[0]), target.width()),
        min(int(minimum_size[1]), target.height()),
    )
    dialog.resize(target.size())
    dialog.move(target.topLeft())
    return target
