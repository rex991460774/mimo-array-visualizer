"""Carbon-led application-wide tokens and native Qt styling.

The compatibility widgets in :mod:`virtual_array.qt_tk` still generate local
styles, so this module deliberately owns the shared colour, geometry and
interaction vocabulary.  Carbon supplies the dense engineering-workbench
structure; Apple principles are retained for immediate, interruptible feedback
and predictable direct manipulation.  New native Qt surfaces should use these
tokens and dynamic roles instead of adding one-off stylesheets.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass

from PySide6 import QtCore, QtGui, QtWidgets


@dataclass(frozen=True)
class WorkbenchTokens:
    """Light tokens for a dense, neutral engineering workstation.

    The names intentionally remain generic because they are consumed by both
    the native Qt shell and the Tk-compatible adapter.  Values are centralized
    here so visual changes remain reliable and inexpensive to maintain.
    """

    canvas: str = "#f4f4f4"
    surface: str = "#ffffff"
    surface_subtle: str = "#f4f4f4"
    surface_muted: str = "#e8e8e8"
    surface_hover: str = "#e8e8e8"
    surface_pressed: str = "#c6c6c6"
    surface_selected: str = "#d0e2ff"
    chrome_surface: str = "#ffffff"
    border: str = "#e0e0e0"
    border_strong: str = "#c6c6c6"
    control_border: str = "#8d8d8d"
    text: str = "#161616"
    text_secondary: str = "#525252"
    text_tertiary: str = "#6f6f6f"
    accent: str = "#0f62fe"
    accent_hover: str = "#0353e9"
    accent_pressed: str = "#002d9c"
    accent_tint: str = "#d0e2ff"
    focus: str = "#0f62fe"
    primary_fill: str = "#0f62fe"
    primary_hover: str = "#0353e9"
    primary_pressed: str = "#002d9c"
    success: str = "#198038"
    success_fill: str = "#defbe6"
    warning: str = "#8e6a00"
    warning_fill: str = "#fff8e1"
    danger: str = "#da1e28"
    danger_fill: str = "#fff1f1"
    disabled: str = "#e0e0e0"
    radius: int = 4
    card_radius: int = 4
    base_font_pt: int = 10
    caption_font_pt: int = 9


TOKENS = WorkbenchTokens()

# Compatibility for integrations that imported the old class names directly.
AppleTokens = WorkbenchTokens
FluentTokens = WorkbenchTokens


def application_font() -> QtGui.QFont:
    """Return the platform system font with reliable CJK fallbacks."""

    if sys.platform.startswith("win"):
        families = [
            "Microsoft YaHei UI",
            "Segoe UI Variable Text",
            "Segoe UI",
            "Microsoft YaHei",
            "Noto Sans CJK SC",
        ]
    elif sys.platform == "darwin":
        families = [
            "SF Pro Text",
            ".AppleSystemUIFont",
            "PingFang SC",
            "Heiti SC",
        ]
    else:
        families = [
            "Noto Sans CJK SC",
            "Noto Sans",
            "DejaVu Sans",
        ]
    font = QtGui.QFont(families[0])
    if hasattr(font, "setFamilies"):
        font.setFamilies(families)
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
        border: 1px solid #9ac5a2;
        border-radius: {t.radius}px;
        padding: 8px 10px;
    }}
    QLabel[fluentRole="callout-warning"] {{
        background: {t.warning_fill};
        color: {t.warning};
        border: 1px solid #d6b766;
        border-radius: {t.radius}px;
        padding: 8px 10px;
    }}
    QLabel[fluentRole="callout-danger"] {{
        background: {t.danger_fill};
        color: {t.danger};
        border: 1px solid #e5a1aa;
        border-radius: {t.radius}px;
        padding: 8px 10px;
    }}

    QMenuBar {{
        background: {t.chrome_surface};
        border-bottom: 1px solid {t.border};
        min-height: 28px;
        padding: 1px 14px;
        spacing: 4px;
    }}
    QMenuBar::item {{
        background: transparent;
        border-radius: 2px;
        padding: 4px 10px;
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
        padding: 4px;
    }}
    QMenu::item {{
        border-radius: 2px;
        padding: 7px 34px 7px 11px;
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
        padding: 1px 13px;
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
        min-height: 32px;
        background: {t.primary_fill};
        border-color: {t.primary_fill};
        color: white;
        font-weight: 600;
    }}
    QPushButton[fluentRole="primary"]:hover,
    QToolButton[fluentRole="primary"]:hover {{
        background: {t.primary_hover};
        border-color: {t.primary_hover};
    }}
    QPushButton[fluentRole="primary"]:pressed,
    QToolButton[fluentRole="primary"]:pressed {{
        background: {t.primary_pressed};
        border-color: {t.primary_pressed};
    }}
    QPushButton[fluentRole="danger"] {{
        color: {t.danger};
        border-color: #e5a1aa;
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
        border-radius: 2px;
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
        margin-top: 15px;
        padding: 13px 11px 11px 11px;
        font-weight: 600;
    }}
    QGroupBox::title {{
        subcontrol-origin: margin;
        left: 12px;
        padding: 0 5px;
        color: {t.text_secondary};
    }}

    QDialog[workbenchRole="dialog-shell"] {{
        background: {t.canvas};
    }}
    QWidget[workbenchRole="dialog-rail"] {{
        background: {t.canvas};
        border: 0;
        border-radius: 0;
    }}
    QGroupBox[workbenchRole="dialog-rail"] {{
        background: {t.canvas};
        border: 0;
        border-radius: 0;
        margin-top: 18px;
        padding: 12px 8px 8px 8px;
    }}
    QWidget[workbenchRole="dialog-header"] {{
        background: {t.surface};
        border: 0;
        border-bottom: 1px solid {t.border};
        border-radius: 0;
    }}
    QWidget[workbenchRole="dialog-content"] {{
        background: {t.surface};
        border: 0;
        border-radius: 0;
    }}
    QGroupBox[workbenchRole="dialog-section"] {{
        background: {t.surface};
        border: 0;
        border-top: 1px solid {t.border};
        border-radius: 0;
        margin-top: 19px;
        padding: 14px 12px 10px 12px;
    }}
    QGroupBox[workbenchRole="dialog-section"]::title,
    QGroupBox[workbenchRole="dialog-rail"]::title {{
        subcontrol-origin: margin;
        left: 8px;
        padding: 0 4px;
        color: {t.text};
        background: transparent;
        font-weight: 600;
    }}
    QWidget[workbenchRole="dialog-footer"] {{
        background: {t.canvas};
        border: 0;
        border-top: 1px solid {t.border};
        border-radius: 0;
    }}
    QTextBrowser[workbenchRole="dialog-content"],
    QListView[workbenchRole="dialog-content"],
    QTableView[workbenchRole="dialog-content"] {{
        background: {t.surface};
        border: 0;
        border-radius: 0;
    }}
    QTabWidget::pane {{
        background: {t.surface};
        border: 1px solid {t.border};
        border-radius: 0;
    }}
    QTabBar::tab {{
        min-height: 32px;
        min-width: 104px;
        background: transparent;
        color: {t.text_secondary};
        border: 1px solid transparent;
        border-radius: 0;
        padding: 0 14px;
        margin: 2px;
        font-weight: 600;
    }}
    QTabBar::tab:selected {{
        background: {t.surface};
        color: {t.text};
        border-color: {t.border};
    }}
    QTabBar::tab:hover:!selected {{
        background: {t.surface_hover};
        color: {t.text};
    }}

    QTableView, QTreeView, QListView, QTextBrowser, QPlainTextEdit, QTextEdit {{
        background: {t.surface};
        alternate-background-color: {t.surface_subtle};
        border: 1px solid {t.control_border};
        border-radius: 0;
        gridline-color: {t.border};
        outline: 0;
    }}
    QTableView::item, QTreeView::item, QListView::item {{
        min-height: 32px;
        padding: 2px 7px;
        border-bottom: 1px solid {t.border};
    }}
    QTableView::item:hover, QTreeView::item:hover, QListView::item:hover {{
        background: {t.surface_hover};
    }}
    QTableView::item:selected, QTreeView::item:selected, QListView::item:selected {{
        background: {t.surface_selected};
        color: {t.accent_pressed};
        border-bottom: 1px solid {t.accent};
        font-weight: 600;
    }}
    QHeaderView::section {{
        min-height: 32px;
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
        width: 9px;
        margin: 2px;
    }}
    QScrollBar::handle:vertical {{
        background: {t.border_strong};
        min-height: 28px;
        border-radius: 4px;
    }}
    QScrollBar::handle:vertical:hover {{ background: {t.control_border}; }}
    QScrollBar:horizontal {{
        background: transparent;
        height: 9px;
        margin: 2px;
    }}
    QScrollBar::handle:horizontal {{
        background: {t.border_strong};
        min-width: 28px;
        border-radius: 4px;
    }}
    QScrollBar::handle:horizontal:hover {{ background: {t.control_border}; }}
    QScrollBar::add-line, QScrollBar::sub-line {{ width: 0; height: 0; }}
    QScrollBar::add-page, QScrollBar::sub-page {{ background: transparent; }}

    QStatusBar {{
        background: {t.chrome_surface};
        border-top: 1px solid {t.border};
        color: {t.text_secondary};
        min-height: 24px;
        max-height: 24px;
        padding-left: 8px;
    }}
    QStatusBar::item {{ border: 0; }}
    QSplitter::handle {{ background: transparent; }}
    QSplitter::handle:horizontal {{ width: 8px; }}
    QSplitter::handle:vertical {{ height: 8px; }}
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
    QProgressBar[workbenchRole="report-progress"] {{
        min-height: 12px;
        max-height: 12px;
        background: {t.surface_muted};
        border: 1px solid {t.border_strong};
        border-radius: 6px;
        text-align: center;
    }}
    QProgressBar[workbenchRole="report-progress"]::chunk {{
        background: {t.accent};
        border: 0;
        border-radius: 5px;
    }}
    QLabel[workbenchRole="progress-status"] {{
        color: {t.text};
        font-size: {t.base_font_pt}pt;
        font-weight: 500;
        padding: 0 4px;
    }}
    QToolTip {{
        background: {t.text};
        color: white;
        border: 0;
        border-radius: 8px;
        padding: 7px 10px;
    }}
    """


class _InteractiveCursorPolicy(QtCore.QObject):
    """Keep click affordances consistent for current and future Qt widgets."""

    _SYNC_EVENTS = {
        QtCore.QEvent.Type.EnabledChange,
        QtCore.QEvent.Type.Enter,
        QtCore.QEvent.Type.MouseMove,
        QtCore.QEvent.Type.Polish,
        QtCore.QEvent.Type.Show,
    }

    @staticmethod
    def _set_shape(widget: QtWidgets.QWidget, pointing: bool) -> None:
        shape = (
            QtCore.Qt.CursorShape.PointingHandCursor
            if pointing
            else QtCore.Qt.CursorShape.ArrowCursor
        )
        if widget.cursor().shape() != shape:
            widget.setCursor(QtGui.QCursor(shape))

    @staticmethod
    def _event_position(
        widget: QtWidgets.QWidget, event: QtCore.QEvent | None
    ) -> QtCore.QPoint:
        if isinstance(event, QtGui.QMouseEvent):
            return event.position().toPoint()
        return widget.mapFromGlobal(QtGui.QCursor.pos())

    @classmethod
    def _sync_tab_bar(
        cls, tab_bar: QtWidgets.QTabBar, event: QtCore.QEvent | None
    ) -> None:
        tab_bar.setMouseTracking(True)
        index = tab_bar.tabAt(cls._event_position(tab_bar, event))
        cls._set_shape(
            tab_bar,
            tab_bar.isEnabled()
            and index >= 0
            and tab_bar.isTabEnabled(index),
        )

    @classmethod
    def _sync_menu(
        cls,
        menu: QtWidgets.QMenu | QtWidgets.QMenuBar,
        event: QtCore.QEvent | None,
    ) -> None:
        menu.setMouseTracking(True)
        action = menu.actionAt(cls._event_position(menu, event))
        cls._set_shape(
            menu,
            menu.isEnabled()
            and action is not None
            and action.isEnabled()
            and not action.isSeparator(),
        )

    @classmethod
    def _sync_spin_box(
        cls, spin: QtWidgets.QAbstractSpinBox, event: QtCore.QEvent | None
    ) -> None:
        spin.setMouseTracking(True)
        option = QtWidgets.QStyleOptionSpinBox()
        spin.initStyleOption(option)
        sub_control = spin.style().hitTestComplexControl(
            QtWidgets.QStyle.ComplexControl.CC_SpinBox,
            option,
            cls._event_position(spin, event),
            spin,
        )
        pointing = (
            spin.isEnabled()
            and not spin.isReadOnly()
            and sub_control
            in {
                QtWidgets.QStyle.SubControl.SC_SpinBoxUp,
                QtWidgets.QStyle.SubControl.SC_SpinBoxDown,
            }
        )
        cls._set_shape(spin, pointing)

    @classmethod
    def _sync_item_viewport(
        cls, viewport: QtWidgets.QWidget, event: QtCore.QEvent | None
    ) -> bool:
        view = viewport.parentWidget()
        if not isinstance(view, QtWidgets.QAbstractItemView):
            return False
        if not bool(view.property("pointingHandItems")) or viewport is not view.viewport():
            return False
        viewport.setMouseTracking(True)
        index = view.indexAt(cls._event_position(viewport, event))
        flags = index.flags() if index.isValid() else QtCore.Qt.ItemFlag.NoItemFlags
        pointing = (
            view.isEnabled()
            and index.isValid()
            and bool(flags & QtCore.Qt.ItemFlag.ItemIsEnabled)
            and bool(flags & QtCore.Qt.ItemFlag.ItemIsSelectable)
            and not bool(flags & QtCore.Qt.ItemFlag.ItemIsEditable)
        )
        cls._set_shape(viewport, pointing)
        return True

    @classmethod
    def sync_widget(
        cls, widget: QtWidgets.QWidget, event: QtCore.QEvent | None = None
    ) -> None:
        if bool(widget.property("preserveCursor")):
            return
        if isinstance(widget, QtWidgets.QTabBar):
            cls._sync_tab_bar(widget, event)
        elif isinstance(widget, (QtWidgets.QMenu, QtWidgets.QMenuBar)):
            cls._sync_menu(widget, event)
        elif isinstance(widget, QtWidgets.QAbstractSpinBox):
            cls._sync_spin_box(widget, event)
        elif cls._sync_item_viewport(widget, event):
            return
        elif isinstance(
            widget,
            (
                QtWidgets.QAbstractButton,
                QtWidgets.QComboBox,
                QtWidgets.QSlider,
            ),
        ):
            cls._set_shape(widget, widget.isEnabled())

    def eventFilter(
        self, watched: QtCore.QObject, event: QtCore.QEvent
    ) -> bool:  # noqa: N802
        if (
            isinstance(watched, QtWidgets.QWidget)
            and event.type() in self._SYNC_EVENTS
        ):
            self.sync_widget(watched, event)
        return False


def install_interactive_cursor_policy(app: QtWidgets.QApplication) -> None:
    """Install one state-aware pointer policy across native and wrapped Qt UI."""

    policy = getattr(app, "_workbench_interactive_cursor_policy", None)
    if not isinstance(policy, _InteractiveCursorPolicy):
        policy = _InteractiveCursorPolicy(app)
        app.installEventFilter(policy)
        app._workbench_interactive_cursor_policy = policy  # type: ignore[attr-defined]
    for widget in app.allWidgets():
        policy.sync_widget(widget)


def apply_native_theme(app: QtWidgets.QApplication) -> None:
    """Apply one deterministic Carbon-led light theme application-wide."""

    if "Fusion" in QtWidgets.QStyleFactory.keys():
        app.setStyle("Fusion")
    app.setFont(application_font())
    app.setPalette(application_palette())
    app.setStyleSheet(application_stylesheet())
    install_interactive_cursor_policy(app)


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
        min-height: 32px;
        background: {TOKENS.primary_fill};
        border: 1px solid {TOKENS.primary_fill};
        border-radius: {TOKENS.radius}px;
        color: white;
        font-weight: 600;
    }}
    {selector}:hover {{
        background: {TOKENS.primary_hover};
        border-color: {TOKENS.primary_hover};
    }}
    {selector}:pressed {{
        background: {TOKENS.primary_pressed};
        border-color: {TOKENS.primary_pressed};
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


def mark_workbench_role(widget: QtWidgets.QWidget, role: str) -> None:
    """Apply one shared region role used by every custom workbench dialog."""

    normalized = role if role in {
        "dialog-shell",
        "dialog-rail",
        "dialog-header",
        "dialog-content",
        "dialog-section",
        "dialog-footer",
        "progress-dialog",
        "progress-status",
        "report-progress",
    } else "dialog-content"
    widget.setProperty("workbenchRole", normalized)
    _repolish(widget)


def mark_callout(widget: QtWidgets.QWidget, role: str) -> None:
    """Apply a semantic, non-blocking callout treatment to a label."""

    normalized = role if role in {"neutral", "success", "warning", "danger"} else "neutral"
    widget.setProperty("fluentRole", f"callout-{normalized}")
    palette = {
        "neutral": (TOKENS.surface_subtle, TOKENS.text_secondary, TOKENS.border),
        "success": (TOKENS.success_fill, TOKENS.success, "#9ac5a2"),
        "warning": (TOKENS.warning_fill, TOKENS.warning, "#d6b766"),
        "danger": (TOKENS.danger_fill, TOKENS.danger, "#e5a1aa"),
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
