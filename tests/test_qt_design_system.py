"""Presentation contracts: real Qt rendering, keyboard and preview lifecycle."""
import pytest

pytest.importorskip('PySide6')
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QImage, QPalette
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QCheckBox, QToolTip, QVBoxLayout, QWidget

from app.ui.qt.components import CollapsibleSection, PhotoView, StatusBadge, button
from app.ui.qt.strings import tr
from app.ui.qt.themes import ThemeManager, TOKENS


@pytest.fixture(scope='module')
def qtapp():
    app = QApplication.instance() or QApplication([])
    app.setStyle('Fusion')
    app.setQuitOnLastWindowClosed(False)
    return app


def contrast(a, b):
    def luminance(value):
        c = QColor(value)
        channels = (c.redF(), c.greenF(), c.blueF())
        linear = [v / 12.92 if v <= .04045 else ((v + .055) / 1.055) ** 2.4 for v in channels]
        return sum(a * b for a, b in zip(linear, (.2126, .7152, .0722)))
    low, high = sorted((luminance(a), luminance(b)))
    return (high + .05) / (low + .05)


@pytest.mark.parametrize('name', TOKENS)
def test_semantic_contrast_and_disabled_palette(qtapp, name):
    c = TOKENS[name]
    pairs = [(text, surface) for text in ('text', 'secondary_text', 'link')
             for surface in ('background', 'surface', 'elevated', 'hover', 'selection')]
    pairs += [('on_primary', surface) for surface in ('primary', 'primary_hover')]
    pairs += [('on_danger', surface) for surface in ('danger', 'danger_hover')]
    pairs += [('disabled_text', 'disabled')]
    pairs += [(tone, 'elevated') for tone in ('success', 'warning', 'danger')]
    for foreground, background in pairs:
        assert contrast(c[foreground], c[background]) >= 4.5, (name, foreground, background)
    # Subtle card separators are decorative. Control outlines and focus are not.
    for surface in ('surface', 'background', 'elevated', 'selection', 'hover'):
        for indicator in ('control_border', 'focus'):
            assert contrast(c[indicator], c[surface]) >= 3, (name, indicator, surface)
    for variant in ('primary', 'danger'):
        for surface in (variant, variant + '_hover'):
            assert contrast(c[variant + '_focus'], c[surface]) >= 3, (name, 'focus', surface)
    theme = ThemeManager(qtapp)
    theme.apply(name)
    assert qtapp.palette().color(QPalette.Disabled, QPalette.Text) == QColor(c['disabled_text'])
    assert QToolTip.palette().color(QPalette.ToolTipBase) == QColor(c['elevated'])
    assert QToolTip.palette().color(QPalette.ToolTipText) == QColor(c['text'])
    theme.deleteLater()


@pytest.mark.parametrize('name', TOKENS)
def test_keyboard_focus_geometry_variants_and_section(qtapp, name):
    theme = ThemeManager(qtapp)
    theme.apply(name)
    host = QWidget()
    layout = QVBoxLayout(host)
    primary = button('start', lambda: None, layout)
    secondary = button('refresh', lambda: None, layout)
    danger = button('selected_move', lambda: None, layout)
    section = CollapsibleSection('detail')
    checkbox = QCheckBox(tr('legacy_confirm'))
    section.body_layout.addWidget(checkbox)
    layout.addWidget(section)
    host.show()
    host.activateWindow()
    QApplication.processEvents()
    try:
        assert [w.property('variant') for w in (primary, secondary, danger)] == ['primary', 'secondary', 'danger']
        for widget in (primary, secondary, danger):
            assert widget.accessibleName() == widget.text()
        primary.setFocus()
        QTest.qWait(10)
        assert primary.hasFocus()
        before = [w.geometry() for w in (primary, secondary, danger)]
        focused = primary.grab().toImage()
        QTest.keyClick(primary, Qt.Key_Tab)
        QApplication.processEvents()
        assert secondary.hasFocus()
        assert primary.grab().toImage() != focused  # Focus actually paints differently.
        QTest.mouseMove(primary, primary.rect().center())
        QApplication.processEvents()
        assert before == [w.geometry() for w in (primary, secondary, danger)]
        assert not section.body.isVisible()
        section.toggle.setFocus()
        QTest.keyClick(section.toggle, Qt.Key_Space)
        assert section.body.isVisible() and section.toggle.isChecked()
        assert not section.toggle.icon().isNull()
        assert not section.toggle.icon().pixmap(16, 16).isNull()
        assert section.toggle.accessibleDescription() == tr('section_expanded')
        QTest.keyClick(section.toggle, Qt.Key_Tab)
        assert checkbox.hasFocus()
        QTest.keyClick(checkbox, Qt.Key_Space)
        assert checkbox.isChecked()
    finally:
        host.close()
        theme.deleteLater()


def test_photo_loading_unavailable_ready_and_reset(qtapp, scanned):
    view = PhotoView()
    view.show()
    try:
        assert view.state == 'select_pair'
        view.set_photo(scanned.pairs[0].keep)
        assert view.state == 'preview_loading' and not view.scene.items()
        assert not any(w.isEnabled() for w in view.preview_buttons)
        view.set_image(None, '<decode failed>')
        assert view.state == 'preview_error'
        assert '<decode failed>' in view.placeholder.text()
        assert view.placeholder.textFormat() == Qt.PlainText
        assert view.preview.currentWidget() is view.placeholder
        image = QImage(32, 24, QImage.Format_RGB32)
        image.fill(Qt.gray)
        view.set_image(image, '')
        assert view.state == 'preview_ready' and len(view.scene.items()) == 1
        assert all(w.isEnabled() for w in view.preview_buttons)
        view.reset()
        assert view.state == 'select_pair' and not view.scene.items()
        assert view.metadata.text() == tr('select_pair')
        assert not any(w.isEnabled() for w in view.preview_buttons)
        view.set_image(QImage(), '')
        assert view.state == 'preview_error'
        badge = StatusBadge('state_complete', 'success')
        assert badge.text() == badge.accessibleName() == tr('state_complete')
    finally:
        view.close()
