from __future__ import annotations

import os

import pytest


os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

QtCore = pytest.importorskip("PySide6.QtCore")
QtGui = pytest.importorskip("PySide6.QtGui")
QtTest = pytest.importorskip("PySide6.QtTest")
QtWidgets = pytest.importorskip("PySide6.QtWidgets")

from virtual_array.qt_tk import AppleSwitch, BooleanVar, Checkbutton, _ensure_app  # noqa: E402


@pytest.fixture(scope="module")
def app():
    return _ensure_app()


def test_ttk_checkbutton_uses_accessible_apple_switch(app):
    variable = BooleanVar(False)
    calls: list[bool] = []
    wrapper = Checkbutton(
        text="导入字典按90°相位校准",
        variable=variable,
        command=lambda: calls.append(variable.get()),
    )
    switch = wrapper._qt

    assert isinstance(switch, AppleSwitch)
    assert isinstance(switch, QtWidgets.QCheckBox)
    assert switch.accessibleName() == "导入字典按90°相位校准"
    assert switch.animationDuration() == 180
    assert switch.minimumSizeHint().height() >= 28

    switch.show()
    switch.setFocus()
    QtTest.QTest.keyClick(switch, QtCore.Qt.Key.Key_Space)
    app.processEvents()

    assert switch.isChecked()
    assert variable.get() is True
    assert calls == [True]

    switch.setEnabled(False)
    QtTest.QTest.keyClick(switch, QtCore.Qt.Key.Key_Space)
    app.processEvents()
    assert switch.isChecked()
    switch.close()


def test_switch_animation_retargets_from_live_position(app):
    switch = AppleSwitch("动画开关")
    switch.resize(switch.sizeHint())
    switch.show()
    app.processEvents()

    if not switch._animations_enabled():
        pytest.skip("the active Qt style disables widget animation")

    switch.setChecked(True)
    QtTest.QTest.qWait(60)
    live_position = switch.switchPosition()
    assert 0.0 < live_position < 1.0

    switch.setChecked(False)
    assert switch.switchPosition() == pytest.approx(live_position, abs=0.03)
    QtTest.QTest.qWait(220)
    assert switch.switchPosition() == pytest.approx(0.0, abs=0.0001)
    switch.close()


class _NoWidgetAnimationStyle(QtWidgets.QProxyStyle):
    def styleHint(self, hint, option=None, widget=None, return_data=None):  # noqa: N802
        if hint == QtWidgets.QStyle.StyleHint.SH_Widget_Animate:
            return 0
        return super().styleHint(hint, option, widget, return_data)


def test_switch_honors_qt_animation_style_hint(app):
    switch = AppleSwitch("减少动画")
    style = _NoWidgetAnimationStyle()
    switch.setStyle(style)
    switch.show()
    app.processEvents()

    switch.setChecked(True)
    assert switch.switchPosition() == pytest.approx(1.0)

    image = QtGui.QImage(
        switch.sizeHint(),
        QtGui.QImage.Format.Format_ARGB32_Premultiplied,
    )
    image.fill(QtCore.Qt.GlobalColor.transparent)
    switch.render(image)
    assert not image.isNull()
    switch.close()
