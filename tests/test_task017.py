"""Dashboard/scan presentation and stale-attempt guards; synthetic files only."""
from dataclasses import replace
import shutil
from threading import Event

import pytest

pytest.importorskip('PySide6')
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest

from app.core.queries import DashboardSummary, ScanProgress
from app.services.application import Application
from app.ui.qt.localization import language_manager
from app.ui.qt.navigation import Route
from app.ui.qt.strings import tr
from tests.test_qt import desktop, qtapp, pump, scan, assert_toolbar_available
from tests.test_qt_design_system import painted_color
from app.ui.qt.themes import TOKENS


@pytest.mark.parametrize('language', ['en', 'sr_Latn'])
@pytest.mark.parametrize('theme', ['dark', 'light'])
def test_state_guidance_actions_and_disclosures(desktop, language, theme):
    window, errors = desktop
    manager = language_manager()
    manager.set_language(language)
    window.theme.apply(theme)
    try:
        dashboard, screen = window.dashboard, window.scan
        dashboard.set_summary(DashboardSummary(9))
        assert [card.value.text() for card in dashboard.stat_cards] == ['9', '—', '—', '—']
        assert dashboard.scan.property('variant') == 'primary'
        summary = DashboardSummary(20, session_id='synthetic', status='complete',
            photo_count=3, exact=2, exact_groups=1, potential_bytes=999999)
        dashboard.set_summary(summary)
        assert [card.value.text() for card in dashboard.stat_cards] == ['20', '2', '0', '1']
        assert dashboard.review.isEnabled() and dashboard.review.property('variant') == 'primary'
        assert dashboard.scan.property('variant') == 'secondary'
        dashboard.set_scan_active(True)
        assert not dashboard.review.isEnabled() and dashboard.scan.property('variant') == 'primary'
        assert dashboard.next_step.text() == tr('scan_next_running')
        dashboard.set_scan_active(False)
        assert not dashboard.scan_details.toggle.isChecked()
        for status, matches, guidance, review in (
                ('complete', 2, 'scan_next_review', True),
                ('complete', 0, 'scan_next_clear', False),
                ('incomplete', 2, 'scan_next_partial', True),
                ('cancelled', 0, 'scan_next_cancelled', False),
                ('failed', 0, 'scan_next_retry', False)):
            value = replace(summary, status=status, exact=matches, exact_groups=int(bool(matches)))
            dashboard.set_summary(value)
            screen.finish(value)
            assert screen.state == status and not screen.timer.isActive()
            assert screen.review.isEnabled() == review
            assert screen.guidance.text() == dashboard.next_step.text() == tr(guidance)
            token = 'text' if review else 'on_primary'
            assert painted_color(screen.start.icon().pixmap(20, 20).toImage(), TOKENS[theme][token])
            assert sum(c.property('variant') == 'primary' for c in (screen.start, screen.review)) == 1
            for size in ((853, 480), (1440, 900)):
                window.resize(*size)
                for route in (Route.DASHBOARD, Route.SCAN):
                    window.navigate(route)
                    assert_toolbar_available(window, window.screens[route].toolbar)
                    assert window.pages[route].horizontalScrollBar().maximum() == 0
        screen.begin()
        screen.update_progress(ScanProgress('scan', discovered=12, processed=7, skipped=3, failed=2))
        assert screen.status.text() == tr('scan_progress_summary', tr('phase_scan'), 7)
        assert screen.error_summary.text() == tr('scan_error_count', 2)
        assert not screen.details.toggle.isChecked() and not screen.error_section.toggle.isChecked()
        screen.cancelled()
        assert screen.state == 'cancelled' and not screen.timer.isActive()
        screen.details.set_expanded(True)
        window.pages[Route.SCAN].ensureWidgetVisible(screen.details)
        window.activateWindow()
        screen.details.toggle.setFocus()
        QTest.keyClick(screen.details.toggle, Qt.Key_Tab)
        assert screen.reports.hasFocus()
        assert not errors
    finally:
        manager.set_language('en')


def test_overlap_offline_counts_and_source_removal_preserves_files(desktop, collection, tmp_path):
    window, errors = desktop
    nested = collection / 'nested'
    nested.mkdir()
    shutil.copy2(collection / 'a.png', nested / 'third.png')
    originals = {p: p.read_bytes() for p in collection.rglob('*.png')}
    window.roots = [str(collection), str(nested), str(tmp_path / 'offline')]
    window.render_roots()
    window.start_scan()
    pump(lambda: window.session and not window.controller.busy, timeout=90)
    assert window.status == 'incomplete' and not errors
    assert [c.value.text() for c in window.dashboard.stat_cards] == ['3', '2', '0', '1']
    assert not window.scan.source_warning.isHidden()
    assert window.scan.review.isEnabled() and window.scan.guidance.text() == tr('scan_next_partial')
    window.scan.remove_buttons[0].click()
    pump(lambda: not window.controller.busy)
    assert str(collection) not in window.roots
    assert {p: p.read_bytes() for p in collection.rglob('*.png')} == originals
    assert not window.scan.advanced.toggle.isChecked()


def test_cancel_before_session_survives_refresh_and_late_sources(desktop, collection, monkeypatch):
    window, errors = desktop
    scan(window, collection)
    previous = window.session
    entered, release = Event(), Event()
    original = Application.sources

    def delayed(self, folders):
        entered.set()
        assert release.wait(20)
        return original(self, folders)

    monkeypatch.setattr(Application, 'sources', delayed)
    window.start_scan()
    try:
        pump(entered.is_set)
        window.cancel()
        assert window.scan.state == window.status == 'cancelled'
        assert not window.scan.review.isEnabled()
    finally:
        release.set()
    pump(lambda: not window.controller.busy)
    window.refresh()
    pump(lambda: not window.controller.busy)
    assert window.session == previous and window.scan.state == window.status == 'cancelled'
    assert window.scan.guidance.text() == tr('scan_next_cancelled')
    assert not window.scan.review.isEnabled() and not errors
    window.start_scan()
    pump(lambda: window.session != previous and not window.controller.busy, timeout=90)
    assert window.scan.state == window.status == 'complete'
    assert window.scan.review.isEnabled()
