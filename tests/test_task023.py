"""Final synthetic Qt journey: consent, restart, conflict and recovery of all bytes."""
from pathlib import Path
import shutil

import pytest

pytest.importorskip('PySide6')
from PySide6.QtCore import Qt
from PySide6.QtGui import QDesktopServices
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QFileDialog, QMessageBox

from app.ui.qt.navigation import Route
from app.ui.qt.window import MainWindow
from tests.test_qt import desktop, pump, qtapp
from tests.test_task020 import open_review

_window_error = MainWindow.error


def test_three_members_cancel_keep_both_quarantine_restart_conflict_restore(
        desktop, collection, monkeypatch):
    window, errors = desktop
    monkeypatch.setattr(QDesktopServices, 'openUrl',
                        lambda _: pytest.fail('unexpected OS launch'))
    shutil.copy2(collection / 'a.png', collection / 'third-čćžšđ.png')
    originals = {p: p.read_bytes() for p in collection.iterdir()}

    window.navigate(Route.SCAN)
    window.scan.add.click()
    chooser = window.findChild(QFileDialog)
    assert chooser is not None and chooser.testOption(QFileDialog.ReadOnly)
    # Exercise the chooser's public result signal without visiting a real library.
    chooser.fileSelected.emit(str(collection))
    chooser.close()
    pump(lambda: not window.controller.busy)
    assert window.roots == [str(collection)]
    window.scan.start.click()
    pump(lambda: window.session and not window.controller.busy, timeout=90)
    assert window.total == 2 and window.status == 'complete'
    open_review(window)
    window.choose_keeper(False)
    window.comparison.both.click()
    assert not window.pending_pairs()
    assert all(p.read_bytes() == data for p, data in originals.items())

    window.comparison.right.keep_photo.click()  # Clear the right-hand retention from Keep Both.
    assert len(window.pending_pairs()) == 1  # The unseen third member is untouched.
    window.comparison.prepare.click()
    pump(lambda: window.plan_dialog is not None)
    dialog = window.plan_dialog
    assert len(dialog.plan.moves) == 1
    QTest.keyClick(dialog, Qt.Key_Escape)
    pump(lambda: window.plan_dialog is None)
    assert all(p.read_bytes() == data for p, data in originals.items())
    window.comparison.prepare.click()
    pump(lambda: window.plan_dialog is not None)
    move = window.plan_dialog.plan.moves[0]
    window.plan_dialog.approve()
    pump(lambda: not window.controller.busy)
    assert not Path(move.source).exists()
    assert Path(move.destination).read_bytes() == originals[Path(move.source)]
    assert all(p.read_bytes() == data for p, data in originals.items() if str(p) != move.source)
    window.close()
    pump(lambda: window.finished)
    assert all(not thread.isRunning() for thread in window.controller.threads)

    # An occupied restore destination survives unchanged across a failed preflight.
    conflict = b'synthetic new file at original path'
    Path(move.source).write_bytes(conflict)
    restarted = MainWindow(window.home)
    restarted.controller.error.connect(lambda action, detail: _window_error(restarted, action, detail))
    restarted.show()
    try:
        pump(lambda: restarted.settings and not restarted.controller.busy)
        restarted.navigate(Route.QUARANTINE)
        index = next(i for i, item in enumerate(restarted.history_rows) if item.id == move.id)
        restarted.history.table.selectRow(index)
        pump(lambda: not restarted.controller.busy)
        restarted.history.restore.click()
        pump(lambda: restarted.history.operation_error and not restarted.controller.busy)
        assert restarted.plan_dialog is None
        assert Path(move.source).read_bytes() == conflict
        assert Path(move.destination).read_bytes() == originals[Path(move.source)]
        for box in restarted.findChildren(QMessageBox):
            box.close()

        # Preserve the conflicting synthetic file too; never delete or overwrite it.
        conflict_path = collection / 'preserved-conflict.bin'
        Path(move.source).rename(conflict_path)
        restarted.history.restore.click()
        pump(lambda: restarted.plan_dialog is not None)
        assert restarted.plan_dialog.plan.moves[0].action == 'restore'
        restarted.plan_dialog.approve()
        pump(lambda: not restarted.controller.busy)
        assert all(p.read_bytes() == data for p, data in originals.items())
        assert conflict_path.read_bytes() == conflict
        assert not Path(move.destination).exists()
        assert any(item.id == move.id and not item.restorable for item in restarted.history_rows)
        assert [action for action, _ in errors] == ['restore']
    finally:
        for box in restarted.findChildren(QMessageBox):
            box.close()
        restarted.close()
        pump(lambda: restarted.finished)
        assert all(not thread.isRunning() for thread in restarted.controller.threads)
