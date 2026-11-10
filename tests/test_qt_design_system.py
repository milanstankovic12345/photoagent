"""Presentation contracts: real Qt rendering, keyboard and preview lifecycle."""
import pytest

pytest.importorskip('PySide6')
from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QColor, QIcon, QImage, QPalette
from PySide6.QtTest import QTest
from PySide6.QtWidgets import (QApplication, QCheckBox, QLineEdit, QTableWidget,
                              QTableWidgetItem, QToolTip, QVBoxLayout, QWidget)

from app.ui.qt.components import CollapsibleSection, PhotoView, StatusBadge, button
from app.ui.qt.strings import tr
from app.ui.qt.themes import ThemeManager, TOKENS
from app.ui.qt.icons import ICON_NAMES, icon
from app.ui.qt.navigation import Route, Sidebar


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
        assert view.placeholder.text() == tr('preview_error')
        assert view.error_details.text.toPlainText() == '<decode failed>'
        assert view.error_details.body.isHidden()
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


def painted_color(image: QImage, color: str) -> bool:
    target = QColor(color).rgb()
    return any(image.pixelColor(x, y).alpha() > 200 and image.pixelColor(x, y).rgb() == target
               for x in range(image.width()) for y in range(image.height()))


@pytest.mark.parametrize('name', ICON_NAMES)
def test_local_icons_recolor_same_instance_across_system_changes(qtapp, name):
    theme = ThemeManager(qtapp)
    glyph = icon(name)
    try:
        for scheme, active in ((Qt.ColorScheme.Light, 'light'), (Qt.ColorScheme.Dark, 'dark'),
                               (Qt.ColorScheme.Unknown, 'dark')):
            theme.apply('system', scheme)
            assert theme.preference == 'system' and theme.active == active
            colors = TOKENS[active]
            for mode, token in ((QIcon.Normal, 'text'), (QIcon.Active, 'text'),
                                (QIcon.Selected, 'text'), (QIcon.Disabled, 'disabled_text')):
                for state in (QIcon.Off, QIcon.On):
                    pixmap = glyph.pixmap(QSize(20, 20), 2.0, mode, state)
                    assert not pixmap.isNull() and pixmap.devicePixelRatio() == 2.0
                    assert pixmap.size() == QSize(40, 40)
                    assert painted_color(pixmap.toImage(), colors[token]), (name, active, mode, state)
                    backgrounds = ('disabled',) if mode == QIcon.Disabled else ('surface', 'elevated', 'selection', 'hover')
                    assert all(contrast(colors[token], colors[b]) >= 3 for b in backgrounds)
    finally:
        theme.deleteLater()


@pytest.mark.parametrize('active', TOKENS)
def test_action_icons_and_disabled_controls_use_readable_rendered_colors(qtapp, active):
    theme = ThemeManager(qtapp)
    theme.apply(active)
    host = QWidget()
    layout = QVBoxLayout(host)
    controls = [button(key, lambda: None, layout, variant=variant) for key, variant in
                (('start', 'primary'), ('settings', 'secondary'), ('move_copy', 'danger'))]
    host.show()
    QApplication.processEvents()
    try:
        for control, foreground in zip(controls, ('on_primary', 'text', 'on_danger')):
            assert painted_color(control.icon().pixmap(20, 20).toImage(), TOKENS[active][foreground])
            control.setEnabled(False)
            QApplication.processEvents()
            image = control.grab().toImage()
            assert painted_color(image, TOKENS[active]['disabled'])
            assert painted_color(control.icon().pixmap(20, 20, QIcon.Disabled).toImage(),
                                 TOKENS[active]['disabled_text'])
    finally:
        host.close()
        theme.deleteLater()


def test_icons_preserve_filter_language_and_theme_choices_on_live_changes(qtapp):
    from app.ui.qt.localization import language_manager
    from app.ui.qt.quarantine_settings import SettingsScreen
    from app.ui.qt.screens import DuplicatesScreen

    theme = ThemeManager(qtapp)
    language = language_manager()
    previous_language = language.language
    noop = lambda *args: None
    listing = DuplicatesScreen(*([noop] * 10))
    settings = SettingsScreen(*([noop] * 4))
    listing.kind.setCurrentIndex(listing.kind.findData('EXACT'))
    listing.search.setText('synthetic.png')
    settings.theme.setCurrentIndex(settings.theme.findData('system'))
    settings.language.setCurrentIndex(settings.language.findData('sr_Latn'))
    try:
        for locale, scheme in (('sr_Latn', Qt.ColorScheme.Light), ('en', Qt.ColorScheme.Dark)):
            language.set_language(locale)
            theme.apply('system', scheme)
            assert listing.kind.currentData() == 'EXACT' and listing.search.text() == 'synthetic.png'
            assert settings.theme.currentData() == 'system' and settings.language.currentData() == 'sr_Latn'
            assert not listing.search.actions()[0].icon().isNull()
            for control, role in ((listing.kind, 'filter'), (listing.sort_order, 'sort'),
                                  (settings.theme, 'theme'), (settings.language, 'language')):
                assert control.property('icon_role') == role
                assert control.accessibleName()
                for index in range(control.count()):
                    assert painted_color(control.itemIcon(index).pixmap(20, 20).toImage(),
                                         TOKENS[theme.active]['text'])
    finally:
        listing.close()
        settings.close()
        language.set_language(previous_language)
        theme.deleteLater()


@pytest.mark.parametrize('active', TOKENS)
def test_selected_navigation_focus_and_control_content_geometry(qtapp, active):
    theme = ThemeManager(qtapp)
    theme.apply(active)
    host = QWidget()
    layout = QVBoxLayout(host)
    sidebar = Sidebar()
    layout.addWidget(sidebar)
    field = QLineEdit('synthetic')
    layout.addWidget(field)
    table = QTableWidget(2, 1)
    table.setItem(0, 0, QTableWidgetItem('Synthetic A'))
    table.setItem(1, 0, QTableWidgetItem('Synthetic B'))
    layout.addWidget(table)
    host.show()
    host.activateWindow()
    QApplication.processEvents()
    try:
        control = sidebar.buttons[Route.SCAN]
        assert [w.property('icon_role') for w in sidebar.buttons.values()] == [
            'dashboard', 'scan', 'duplicates', 'quarantine', 'settings']
        before = (control.geometry(), control.contentsRect(), field.geometry(), field.contentsRect(),
                  table.geometry(), table.visualRect(table.model().index(0, 0)))
        for selected in (Route.SCAN, Route.DASHBOARD, Route.SCAN):
            sidebar.select(selected)
            control.setFocus()
            QTest.mouseMove(control, control.rect().center())
            QApplication.processEvents()
            assert painted_color(control.grab().toImage(), TOKENS[active]['focus'])
            table.selectRow(1)
            assert before == (control.geometry(), control.contentsRect(), field.geometry(), field.contentsRect(),
                              table.geometry(), table.visualRect(table.model().index(0, 0)))
        for target in (field, table):
            target.setFocus()
            QApplication.processEvents()
            assert painted_color(target.grab().toImage(), TOKENS[active]['focus'])
    finally:
        host.close()
        theme.deleteLater()
