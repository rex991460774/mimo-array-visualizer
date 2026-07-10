"""Fluent 2 inspired application-wide tokens and native Qt styling."""

from __future__ import annotations

from dataclasses import dataclass

from PySide6 import QtGui, QtWidgets


@dataclass(frozen=True)
class FluentTokens:
    canvas: str = "#f3f8fd"
    surface: str = "#ffffff"
    surface_subtle: str = "#f7fbff"
    surface_selected: str = "#dff1ff"
    border: str = "#cfddea"
    control_border: str = "#8a94a6"
    text: str = "#1f2937"
    text_secondary: str = "#64748b"
    accent: str = "#0078d4"
    accent_hover: str = "#106ebe"
    accent_pressed: str = "#005a9e"
    success: str = "#107c10"
    warning: str = "#8a5a00"
    warning_fill: str = "#fff4ce"
    danger: str = "#c50f1f"
    danger_fill: str = "#fde7e9"
    disabled: str = "#e8eef5"
    radius: int = 6
    card_radius: int = 8
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


def application_stylesheet() -> str:
    t = TOKENS
    return f"""
    QMainWindow, QDialog {{
        background: {t.canvas};
        color: {t.text};
    }}
    QWidget {{
        color: {t.text};
        selection-background-color: {t.surface_selected};
        selection-color: {t.text};
    }}
    QMenuBar {{
        background: {t.surface};
        border-bottom: 1px solid {t.border};
        padding: 4px 10px;
        spacing: 2px;
    }}
    QMenuBar::item {{
        background: transparent;
        border-radius: {t.radius}px;
        padding: 7px 12px;
    }}
    QMenuBar::item:selected {{
        background: {t.surface_selected};
        color: {t.accent_pressed};
    }}
    QMenu {{
        background: {t.surface};
        border: 1px solid {t.control_border};
        border-radius: {t.radius}px;
        padding: 6px;
    }}
    QMenu::item {{
        border-radius: 4px;
        padding: 7px 28px 7px 10px;
    }}
    QMenu::item:selected {{
        background: {t.surface_selected};
        color: {t.accent_pressed};
    }}
    QPushButton, QToolButton {{
        min-height: 30px;
        background: {t.surface};
        border: 1px solid {t.control_border};
        border-radius: {t.radius}px;
        padding: 2px 12px;
    }}
    QPushButton:hover, QToolButton:hover {{
        background: {t.surface_selected};
        border-color: {t.accent};
    }}
    QPushButton:pressed, QToolButton:pressed {{
        background: #cfe8fb;
        border-color: {t.accent_pressed};
    }}
    QPushButton:focus, QToolButton:focus,
    QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QDoubleSpinBox:focus {{
        border: 2px solid {t.accent};
    }}
    QPushButton:disabled, QToolButton:disabled {{
        background: {t.disabled};
        border-color: {t.border};
        color: {t.control_border};
    }}
    QPushButton[fluentRole="primary"], QToolButton[fluentRole="primary"] {{
        min-height: 32px;
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
    QPushButton[fluentRole="danger"] {{
        color: {t.danger};
        border-color: #d99aa2;
    }}
    QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox {{
        min-height: 30px;
        background: {t.surface};
        border: 1px solid {t.control_border};
        border-radius: {t.radius}px;
        padding: 1px 8px;
    }}
    QGroupBox {{
        background: {t.surface};
        border: 1px solid {t.border};
        border-radius: {t.card_radius}px;
        margin-top: 12px;
        padding-top: 8px;
        font-weight: 600;
    }}
    QGroupBox::title {{
        subcontrol-origin: margin;
        left: 10px;
        padding: 0 4px;
    }}
    QTabWidget::pane {{
        background: {t.surface};
        border: 1px solid {t.border};
        border-radius: {t.card_radius}px;
    }}
    QTabBar::tab {{
        min-height: 34px;
        min-width: 116px;
        background: transparent;
        color: {t.text_secondary};
        border: 0;
        border-radius: {t.radius}px;
        padding: 0 16px;
        margin-right: 4px;
        font-weight: 600;
    }}
    QTabBar::tab:selected {{
        background: {t.surface_selected};
        color: {t.accent_pressed};
    }}
    QTabBar::tab:hover:!selected {{
        background: #ebf4fc;
        color: {t.text};
    }}
    QTableView, QTreeView, QTextBrowser, QPlainTextEdit, QTextEdit {{
        background: {t.surface};
        alternate-background-color: {t.surface_subtle};
        border: 1px solid {t.control_border};
        border-radius: {t.radius}px;
        gridline-color: {t.border};
    }}
    QHeaderView::section {{
        min-height: 30px;
        background: #eaf3fb;
        color: {t.text};
        border: 0;
        border-right: 1px solid {t.border};
        border-bottom: 1px solid {t.control_border};
        padding: 3px 8px;
        font-weight: 600;
    }}
    QStatusBar {{
        background: {t.surface_subtle};
        border-top: 1px solid {t.border};
        color: {t.text_secondary};
        min-height: 24px;
    }}
    QSplitter::handle {{
        background: transparent;
        width: 6px;
    }}
    QSplitter::handle:hover {{
        background: {t.surface_selected};
    }}
    QToolTip {{
        background: {t.text};
        color: white;
        border: 0;
        padding: 5px 8px;
    }}
    """


def apply_native_theme(app: QtWidgets.QApplication) -> None:
    app.setFont(application_font())
    app.setStyleSheet(application_stylesheet())


def mark_primary(widget: QtWidgets.QWidget) -> None:
    widget.setProperty("fluentRole", "primary")
    if not widget.objectName():
        widget.setObjectName(f"fluentPrimary_{id(widget)}")
    selector = f"#{widget.objectName()}"
    local_rules = f"""
    {selector} {{
        min-height: 32px;
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
        color: {TOKENS.control_border};
    }}
    {selector}:focus {{ border: 2px solid {TOKENS.accent_pressed}; }}
    """
    widget.setStyleSheet(f"{widget.styleSheet()}\n{local_rules}")
    widget.style().unpolish(widget)
    widget.style().polish(widget)


def mark_danger(widget: QtWidgets.QWidget) -> None:
    widget.setProperty("fluentRole", "danger")
    widget.style().unpolish(widget)
    widget.style().polish(widget)
