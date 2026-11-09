"""Stage H: rendered primary-flow geometry, including loaded photo panels."""
import os

import pytest

pytest.importorskip('PySide6')
from PySide6.QtWidgets import QApplication

from app.core.queries import MatchRow
from app.ui.qt.navigation import Route
from tests.test_qt import desktop, pump, qtapp
from tools.capture_task011 import RESOLUTIONS, inspect_layout, isolated_environment


@pytest.mark.parametrize('theme', ('dark', 'light'))
def test_primary_flow_geometry_at_target_sizes(desktop, scanned, theme):
    window, errors = desktop
    window.theme.apply(theme)
    window.status = 'complete'
    window.duplicates.model.replace((MatchRow(1, 1, scanned.pairs[0]),))
    window.duplicates.set_state('', True)
    window.scan.set_sources([scanned.photos[0].root], {scanned.photos[0].root: 'available'})
    window.preferences.show_roots([scanned.photos[0].root])
    window.preferences.load_matching(13, 17)
    scale = float(os.environ.get('QT_SCALE_FACTOR', '1'))
    for physical in RESOLUTIONS:
        logical = [round(n / scale) for n in physical]
        window.resize(*logical)
        assert window.grab().devicePixelRatio() == pytest.approx(scale)
        for route in Route:
            window.duplicates_flow.show_comparison(False)
            window.navigate(route)
            QApplication.processEvents()
            layout = inspect_layout(window)
            assert not layout['page_horizontal_max'], (physical, theme, route, layout)
            assert not layout['toolbar_outside'] and not layout['toolbar_overlaps'], layout
            assert [window.width(), window.height()] == logical
        window.navigate(Route.DUPLICATES)
        window.duplicates.table.selectRow(0)
        window.compare()
        pump(lambda: not window.controller.busy)
        pump(lambda: window.comparison.left.state == window.comparison.right.state == 'preview_ready')
        layout = inspect_layout(window)
        assert not layout['page_horizontal_max'] and not layout['toolbar_outside'], layout
        for photo in (window.comparison.left, window.comparison.right):
            assert photo.scene.items() and photo.preview.currentWidget() is photo.view
            assert photo.view.viewport().width() >= 100 and photo.view.viewport().height() >= 100
        window.comparison.right.details.set_expanded(True)
        QApplication.processEvents()
        assert inspect_layout(window)['page_horizontal_max'] == 0
        window.comparison.right.details.set_expanded(False)
        window.back_to_duplicates()
    # Make the geometry probe fail on a real primary-page overflow.
    window.navigate(Route.SETTINGS)
    window.preferences.setMinimumWidth(window.width() + 300)
    QApplication.processEvents()
    assert inspect_layout(window)['page_horizontal_max'] > 0
    assert not errors


def test_capture_environment_restored_even_on_failure(tmp_path, monkeypatch):
    monkeypatch.setenv('HOME', 'synthetic-old-home')
    monkeypatch.delenv('TMPDIR', raising=False)
    keys = ('HOME', 'USERPROFILE', 'TMP', 'TEMP', 'TMPDIR')
    before = {key: os.environ.get(key) for key in keys}
    with pytest.raises(RuntimeError, match='synthetic capture failure'):
        with isolated_environment(tmp_path):
            assert all(os.environ[key] == str(tmp_path) for key in keys)
            raise RuntimeError('synthetic capture failure')
    assert {key: os.environ.get(key) for key in keys} == before
