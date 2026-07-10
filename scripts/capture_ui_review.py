"""Capture repeatable GUI review screenshots with an isolated application state.

The script deliberately drives the public ``virtual_array.gui`` entrypoint.  It
supports both the current Qt-backed compatibility widgets and the native
PySide6 shell that is replacing them.  Screenshots are painted with
``QWidget.render`` instead of relying on a real desktop or screen-grab API.
"""

from __future__ import annotations

import argparse
import importlib
import inspect
import os
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Sequence


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "outputs" / "ui-review"
DEFAULT_SIZE = (1366, 768)
MAX_NEAR_BLACK_FRACTION = 0.08
RENDER_ATTEMPTS = 3

PAGE_SCREENSHOTS = (
    "01-physical-virtual.png",
    "02-1d-dbf.png",
    "03-2d-dbf.png",
)


@dataclass
class GuiSession:
    """Objects needed to exercise and clean up one GUI instance."""

    app: Any
    gui_module: Any
    controller: Any
    owner: Any
    window: Any


@dataclass
class PageNavigator:
    """Small adapter over QTabWidget or QTabBar/QStackedWidget navigation."""

    controller: Any
    tab_widget: Any = None
    tab_bar: Any = None
    stack: Any = None

    @property
    def count(self) -> int:
        counts = []
        for widget in (self.tab_widget, self.tab_bar, self.stack):
            if widget is not None and hasattr(widget, "count"):
                counts.append(int(widget.count()))
        return max(counts, default=0)

    @property
    def current_index(self) -> int:
        for widget in (self.stack, self.tab_widget, self.tab_bar):
            if widget is not None and hasattr(widget, "currentIndex"):
                return int(widget.currentIndex())
        return -1

    def select(self, index: int) -> None:
        """Select a main page while preserving controller side effects."""

        for method_name in ("_select_main_tab", "select_main_tab", "set_active_tab"):
            method = getattr(self.controller, method_name, None)
            if callable(method):
                method(index)
                break
        else:
            notebook = getattr(self.controller, "main_notebook", None)
            select = getattr(notebook, "select", None)
            if callable(select):
                select(index)

        if self.tab_widget is not None:
            self.tab_widget.setCurrentIndex(index)
        if self.tab_bar is not None:
            self.tab_bar.setCurrentIndex(index)
        if self.stack is not None:
            self.stack.setCurrentIndex(index)


def _qt_modules() -> tuple[Any, Any, Any]:
    from PySide6 import QtCore, QtGui, QtWidgets

    return QtCore, QtGui, QtWidgets


def configure_capture_environment(appdata_dir: Path) -> None:
    """Configure Qt and persistent state before importing the GUI module.

    Windows keeps its native Qt platform for useful CJK font fallback in visual
    review images.  CI/tests can explicitly set ``QT_QPA_PLATFORM=offscreen``;
    non-Windows hosts default to offscreen when no platform was requested.
    """

    if sys.platform != "win32":
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    os.environ["APPDATA"] = str(appdata_dir)
    os.environ["LOCALAPPDATA"] = str(appdata_dir)


def _ensure_import_path() -> None:
    source = str(SRC_DIR)
    if source not in sys.path:
        sys.path.insert(0, source)


def _constructor_owner(gui_module: Any, gui_class: type[Any]) -> Any:
    """Build the QMainWindow or legacy Qt/Tk root expected by VirtualArrayGui."""

    _QtCore, _QtGui, QtWidgets = _qt_modules()
    parameters = list(inspect.signature(gui_class).parameters.values())
    required = [
        parameter
        for parameter in parameters
        if parameter.kind
        in (inspect.Parameter.POSITIONAL_ONLY, inspect.Parameter.POSITIONAL_OR_KEYWORD)
        and parameter.default is inspect.Parameter.empty
    ]
    if not required:
        return None

    first = required[0]
    annotation = str(first.annotation).lower()
    if "qmainwindow" in annotation or "qwidget" in annotation:
        return QtWidgets.QMainWindow()

    legacy_tk = getattr(gui_module, "tk", None)
    legacy_root = getattr(legacy_tk, "Tk", None)
    if legacy_root is not None and ("tk" in annotation or first.name in {"root", "master"}):
        return legacy_root()
    return QtWidgets.QMainWindow()


def _unwrap_qwidget(value: Any) -> Any:
    """Return a QWidget hidden behind a compatibility wrapper, if present."""

    _QtCore, _QtGui, QtWidgets = _qt_modules()
    pending = [value]
    visited: set[int] = set()
    while pending:
        candidate = pending.pop(0)
        if candidate is None or id(candidate) in visited:
            continue
        visited.add(id(candidate))
        if isinstance(candidate, QtWidgets.QWidget):
            return candidate
        for name in ("_window", "_qt", "window", "main_window", "root"):
            nested = getattr(candidate, name, None)
            if nested is not None and nested is not candidate:
                pending.append(nested)
    return None


def _resolve_main_window(controller: Any, owner: Any, app: Any) -> Any:
    _QtCore, _QtGui, QtWidgets = _qt_modules()
    candidates = [
        controller,
        getattr(controller, "window", None),
        getattr(controller, "main_window", None),
        getattr(controller, "root", None),
        owner,
    ]
    widgets = [widget for value in candidates if (widget := _unwrap_qwidget(value)) is not None]
    for widget in widgets:
        if isinstance(widget, QtWidgets.QMainWindow):
            return widget
        top_level = widget.window()
        if isinstance(top_level, QtWidgets.QMainWindow):
            return top_level
    if widgets:
        return widgets[0].window()
    for widget in app.topLevelWidgets():
        if isinstance(widget, QtWidgets.QMainWindow):
            return widget
    raise RuntimeError("VirtualArrayGui did not expose a QWidget/QMainWindow")


def process_events(app: Any, cycles: int = 4) -> None:
    QtCore, _QtGui, _QtWidgets = _qt_modules()
    for _ in range(cycles):
        app.processEvents()
        QtCore.QCoreApplication.sendPostedEvents(
            None, QtCore.QEvent.Type.DeferredDelete
        )


def create_gui_session(size: tuple[int, int] = DEFAULT_SIZE) -> GuiSession:
    """Instantiate the canonical GUI without entering QApplication.exec()."""

    _ensure_import_path()
    _QtCore, _QtGui, QtWidgets = _qt_modules()
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication(
        ["capture-ui-review"]
    )
    gui_module = importlib.import_module("virtual_array.gui")
    gui_class = gui_module.VirtualArrayGui
    owner = _constructor_owner(gui_module, gui_class)
    controller = gui_class() if owner is None else gui_class(owner)
    window = _resolve_main_window(controller, owner, app)
    window.resize(*size)
    window.show()
    process_events(app)
    return GuiSession(app, gui_module, controller, owner, window)


def close_gui_session(session: GuiSession) -> None:
    """Close top-level widgets without terminating a shared QApplication."""

    _QtCore, _QtGui, QtWidgets = _qt_modules()
    for widget in list(session.app.topLevelWidgets()):
        if isinstance(widget, QtWidgets.QDialog):
            widget.reject()
    session.window.close()
    process_events(session.app, cycles=2)


def _as_qt_widget(value: Any, expected_type: type[Any]) -> Any:
    widget = _unwrap_qwidget(value)
    return widget if isinstance(widget, expected_type) else None


def locate_page_navigator(session: GuiSession) -> PageNavigator | None:
    """Find the three-page workspace without depending on one implementation."""

    _QtCore, _QtGui, QtWidgets = _qt_modules()
    controller = session.controller

    for name in ("main_notebook", "main_tabs", "tab_widget", "main_tab_widget"):
        tab_widget = _as_qt_widget(getattr(controller, name, None), QtWidgets.QTabWidget)
        if tab_widget is not None and tab_widget.count() >= 3:
            return PageNavigator(controller=controller, tab_widget=tab_widget)

    tab_bar = None
    stack = None
    for name in ("main_tab_bar", "tab_bar", "workspace_tab_bar"):
        candidate = _as_qt_widget(getattr(controller, name, None), QtWidgets.QTabBar)
        if candidate is not None:
            tab_bar = candidate
            break
    for name in ("main_stack", "stacked_widget", "main_stacked_widget", "workspace_stack"):
        candidate = _as_qt_widget(
            getattr(controller, name, None), QtWidgets.QStackedWidget
        )
        if candidate is not None:
            stack = candidate
            break
    if stack is not None and stack.count() >= 3:
        return PageNavigator(controller=controller, tab_bar=tab_bar, stack=stack)

    tab_widgets = sorted(
        session.window.findChildren(QtWidgets.QTabWidget),
        key=lambda widget: widget.count(),
        reverse=True,
    )
    if tab_widgets and tab_widgets[0].count() >= 3:
        return PageNavigator(controller=controller, tab_widget=tab_widgets[0])

    stacks = sorted(
        session.window.findChildren(QtWidgets.QStackedWidget),
        key=lambda widget: widget.count(),
        reverse=True,
    )
    if stacks and stacks[0].count() >= 3:
        bars = [bar for bar in session.window.findChildren(QtWidgets.QTabBar) if bar.count() >= 3]
        return PageNavigator(
            controller=controller,
            tab_bar=bars[0] if bars else None,
            stack=stacks[0],
        )
    return None


def _prepare_widget_for_capture(widget: Any) -> None:
    """Flush layouts and paints for every visible child after a page switch."""

    _QtCore, _QtGui, QtWidgets = _qt_modules()
    app = QtWidgets.QApplication.instance()
    widgets = [widget, *widget.findChildren(QtWidgets.QWidget)]
    for child in widgets:
        if not child.isVisible():
            continue
        child.ensurePolished()
        layout = child.layout()
        if layout is not None:
            layout.activate()
        child.updateGeometry()
        child.update()
    if app is not None:
        process_events(app, cycles=4)


def _render_widget_image(widget: Any) -> Any:
    """Render a complete, opaque QWidget image on a CPU-backed paint device."""

    QtCore, QtGui, QtWidgets = _qt_modules()
    size = widget.size()
    if size.width() <= 0 or size.height() <= 0:
        widget.adjustSize()
        size = widget.size()
    ratio = max(1.0, float(widget.devicePixelRatioF()))
    image = QtGui.QImage(
        max(1, round(size.width() * ratio)),
        max(1, round(size.height() * ratio)),
        QtGui.QImage.Format.Format_RGB32,
    )
    image.setDevicePixelRatio(ratio)
    image.fill(widget.palette().color(QtGui.QPalette.ColorRole.Window))
    painter = QtGui.QPainter(image)
    flags = (
        QtWidgets.QWidget.RenderFlag.DrawWindowBackground
        | QtWidgets.QWidget.RenderFlag.DrawChildren
        | QtWidgets.QWidget.RenderFlag.IgnoreMask
    )
    widget.render(
        painter,
        QtCore.QPoint(0, 0),
        QtGui.QRegion(widget.rect()),
        flags,
    )
    painter.end()
    return image


def _near_black_fraction(image: Any) -> float:
    """Estimate whether a light-theme capture contains an unpainted black area."""

    width = image.width()
    height = image.height()
    step = max(1, min(width, height) // 180)
    near_black = 0
    samples = 0
    for y in range(0, height, step):
        for x in range(0, width, step):
            color = image.pixelColor(x, y)
            samples += 1
            if color.red() < 16 and color.green() < 16 and color.blue() < 16:
                near_black += 1
    return near_black / max(samples, 1)


def render_widget(widget: Any, output_path: Path) -> Path:
    """Paint and validate a QWidget PNG using QWidget.render()."""

    output_path.parent.mkdir(parents=True, exist_ok=True)
    best_image = None
    best_black_fraction = 1.0
    for _attempt in range(RENDER_ATTEMPTS):
        _prepare_widget_for_capture(widget)
        image = _render_widget_image(widget)
        black_fraction = _near_black_fraction(image)
        if black_fraction < best_black_fraction:
            best_image = image
            best_black_fraction = black_fraction
        if black_fraction <= MAX_NEAR_BLACK_FRACTION:
            break

    if best_image is None or best_black_fraction > MAX_NEAR_BLACK_FRACTION:
        raise RuntimeError(
            "GUI capture contains an unexpectedly large near-black area "
            f"({best_black_fraction:.1%}): {output_path}"
        )
    if not best_image.save(str(output_path), "PNG"):
        raise OSError(f"Failed to save GUI screenshot: {output_path}")
    return output_path


def capture_main_pages(session: GuiSession, output_dir: Path) -> list[Path]:
    """Capture the three canonical pages, or a transitional main-window image."""

    navigator = locate_page_navigator(session)
    if navigator is None or navigator.count < 3:
        fallback = output_dir / "01-main-window.png"
        return [render_widget(session.window, fallback)]

    captured = []
    for index, filename in enumerate(PAGE_SCREENSHOTS):
        navigator.select(index)
        process_events(session.app, cycles=6)
        captured.append(render_widget(session.window, output_dir / filename))
    return captured


def _visible_dialogs(session: GuiSession) -> list[Any]:
    _QtCore, _QtGui, QtWidgets = _qt_modules()
    dialogs: list[Any] = []
    for widget in [
        *session.app.topLevelWidgets(),
        *session.window.findChildren(QtWidgets.QDialog),
    ]:
        if (
            isinstance(widget, QtWidgets.QDialog)
            and widget.isVisible()
            and widget not in dialogs
        ):
            dialogs.append(widget)
    return dialogs


def _capture_dialog_invocation(
    session: GuiSession,
    invocation: Callable[[], Any],
    output_path: Path,
    timeout_ms: int = 5000,
) -> bool:
    """Capture modal or modeless dialog calls without blocking on exec()."""

    QtCore, _QtGui, _QtWidgets = _qt_modules()
    baseline = {id(dialog) for dialog in _visible_dialogs(session)}
    loop = QtCore.QEventLoop()
    watcher = QtCore.QTimer()
    watcher.setInterval(25)
    timeout = QtCore.QTimer()
    timeout.setSingleShot(True)
    captured = False
    candidate = None
    settled_polls = 0
    error: BaseException | None = None

    def invoke() -> None:
        nonlocal error
        try:
            invocation()
        except BaseException as exc:  # surfaced after the nested event loop exits
            error = exc
            loop.quit()

    def poll() -> None:
        nonlocal captured, candidate, settled_polls
        available = [dialog for dialog in _visible_dialogs(session) if id(dialog) not in baseline]
        if not available:
            return
        current = available[-1]
        if current is not candidate:
            candidate = current
            settled_polls = 0
            return
        settled_polls += 1
        if settled_polls < 2:
            return
        process_events(session.app, cycles=2)
        render_widget(current, output_path)
        captured = True
        current.reject()
        loop.quit()

    watcher.timeout.connect(poll)
    timeout.timeout.connect(loop.quit)
    watcher.start()
    timeout.start(timeout_ms)
    QtCore.QTimer.singleShot(0, invoke)
    loop.exec()
    watcher.stop()
    timeout.stop()
    process_events(session.app, cycles=2)
    if error is not None:
        raise error
    return captured


def _first_callable(controller: Any, names: Sequence[str]) -> Callable[..., Any] | None:
    for name in names:
        method = getattr(controller, name, None)
        if callable(method):
            return method
    return None


def _sample_element_pattern() -> Any:
    import numpy as np

    from virtual_array.element_pattern import ElementPattern

    angles = np.linspace(-90.0, 90.0, 181)
    horizontal = -np.minimum((angles / 27.0) ** 2 * 3.0, 35.0)
    elevation = -np.minimum((angles / 34.0) ** 2 * 3.0, 35.0)
    return ElementPattern(
        name="Automated review pattern",
        source_path="isolated-review-pattern.csv",
        angle_column="Angle",
        horizontal_column="Az Gain",
        elevation_column="El Gain",
        angles_deg=angles,
        horizontal_gain_db=horizontal,
        elevation_gain_db=elevation,
    )


def capture_dialogs(session: GuiSession, output_dir: Path) -> list[Path]:
    """Capture the four custom dialogs named in the visual acceptance plan."""

    controller = session.controller
    specs: list[tuple[str, Sequence[str], Callable[[Callable[..., Any]], Callable[[], Any]]]] = [
        (
            "04-dbf-dictionary.png",
            ("open_dbf_dictionary_dialog", "show_dbf_dictionary_dialog"),
            lambda method: method,
        ),
        (
            "05-channel-amplitude-phase.png",
            ("open_channel_patterns_dialog", "show_channel_patterns_dialog"),
            lambda method: method,
        ),
        (
            "06-element-pattern-confirmation.png",
            (
                "_confirm_element_pattern_import",
                "show_element_pattern_confirmation",
            ),
            lambda method: lambda: method(_sample_element_pattern()),
        ),
        (
            "07-user-manual.png",
            ("_show_user_manual_dialog", "show_user_manual_dialog"),
            lambda method: method,
        ),
    ]
    captured: list[Path] = []
    for filename, method_names, invocation_factory in specs:
        method = _first_callable(controller, method_names)
        if method is None:
            continue
        output_path = output_dir / filename
        if _capture_dialog_invocation(
            session,
            invocation_factory(method),
            output_path,
        ):
            captured.append(output_path)
    return captured


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Capture canonical PySide6 GUI pages and dialogs for visual review."
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help=f"PNG destination (default: {DEFAULT_OUTPUT_DIR})",
    )
    parser.add_argument(
        "--skip-dialogs",
        action="store_true",
        help="Capture only the three main pages.",
    )
    parser.add_argument(
        "--width",
        type=int,
        default=DEFAULT_SIZE[0],
        help=f"Logical window width (default: {DEFAULT_SIZE[0]}).",
    )
    parser.add_argument(
        "--height",
        type=int,
        default=DEFAULT_SIZE[1],
        help=f"Logical window height (default: {DEFAULT_SIZE[1]}).",
    )
    parser.add_argument(
        "--language",
        choices=("zh", "en", "ja"),
        default="zh",
        help="UI language for the captured scenario (default: zh).",
    )
    parser.add_argument(
        "--auto-tx",
        type=int,
        default=1,
        help="Auto-layout Tx count for the captured scenario (default: 1).",
    )
    parser.add_argument(
        "--auto-rx",
        type=int,
        default=1,
        help="Auto-layout Rx count for the captured scenario (default: 1).",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    output_dir = args.output_dir.expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="mimo-array-ui-review-") as appdata:
        configure_capture_environment(Path(appdata))
        session = create_gui_session((max(1, args.width), max(1, args.height)))
        try:
            session.controller.set_language(args.language)
            if args.auto_tx != 1 or args.auto_rx != 1:
                session.controller.auto_tx_count.set(str(max(1, args.auto_tx)))
                session.controller.auto_rx_count.set(str(max(1, args.auto_rx)))
                session.controller.apply_auto_array_layout()
            process_events(session.app, cycles=8)
            captured = capture_main_pages(session, output_dir)
            if not args.skip_dialogs:
                captured.extend(capture_dialogs(session, output_dir))
        finally:
            close_gui_session(session)

    for path in captured:
        print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
