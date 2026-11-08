"""Hidden Tk integration: real event loop, synthetic files, no user libraries."""
import threading
import time
import tkinter as tk

import pytest

from app.ui.tk_app import PhotoApp


def pump(root, predicate, timeout=20):
    end = time.monotonic() + timeout
    while not predicate():
        if time.monotonic() > end:
            raise AssertionError("Tk worker did not finish")
        root.update()
        time.sleep(0.01)


@pytest.fixture(scope="module")
def tk_host():
    # One Tcl/Tk interpreter per process; each test gets its own Toplevel.
    # Reinitializing Tcl after repeated root destruction is unreliable on the
    # Microsoft Store Python distribution used by the development machine.
    try:
        host = tk.Tk()
    except tk.TclError as exc:
        pytest.skip(f"Tk display unavailable: {exc}")
    host.withdraw()
    yield host
    host.destroy()


@pytest.fixture
def desktop(tmp_path, monkeypatch, tk_host):
    import app.ui.tk_app as ui
    main_thread = threading.get_ident()
    dialogs = []

    def dialog(*args, **kwargs):
        assert threading.get_ident() == main_thread
        dialogs.append(args)
        return False

    for name in ("showerror", "showinfo", "showwarning", "askyesno"):
        monkeypatch.setattr(ui.messagebox, name, dialog)
    root = tk.Toplevel(tk_host)
    root.withdraw()
    app = PhotoApp(root, home=tmp_path)
    pump(root, lambda: app.journal is not None and not app.busy)
    try:
        yield root, app, dialogs
    finally:
        if not app.closing:
            app.close()
        pump(root, lambda: not app.futures)
        # Drain the final poll if no root.update was needed by the predicate.
        try:
            root.update()
        except tk.TclError:
            pass
        app.executor.shutdown(wait=True)
        if app.journal and not app.journal._lock.closed:
            app.journal.close()
        try:
            root.destroy()
        except tk.TclError:
            pass


def test_report_failure_keeps_polling_and_ui_responsive(desktop, collection, monkeypatch):
    root, app, dialogs = desktop
    import app.ui.tk_app as ui

    def fail_report(*args):
        assert threading.current_thread() is not threading.main_thread()
        raise PermissionError("synthetic report denial")

    monkeypatch.setattr(ui, "make_report", fail_report)
    app.folder_list.insert("end", str(collection))
    app.start_scan()
    heartbeats = []
    root.after(1, lambda: heartbeats.append(True))
    pump(root, lambda: not app.busy)
    assert heartbeats and len(app.pairs) == 1
    assert "synthetic report denial" in app.status.get()
    # A second worker result proves polling was rescheduled after report failure.
    app._submit("settings_saved", lambda: None)
    pump(root, lambda: not app.busy)


def test_stale_preview_discarded_and_result_dependencies_invalidated(desktop, scanned, monkeypatch):
    root, app, _ = desktop
    app.photos = list(scanned.photos)
    app.pairs = list(scanned.pairs)
    app._populate()
    shown = []
    monkeypatch.setattr(app, "_display_preview", lambda payload: shown.append(payload))
    app.preview_token = 10
    app.updates.put(("preview", (True, "old", 9)))
    app.updates.put(("preview", (True, "current", 10)))
    app.poll()
    assert shown == ["current"]
    app._invalidate({scanned.pairs[0].keep.path})
    assert not app.pairs and not app.tree.get_children()


def test_poll_rescheduled_after_render_exception(desktop, monkeypatch):
    root, app, _ = desktop
    scheduled = []
    real_after = root.after

    def after(ms, callback):
        scheduled.append(callback)
        return real_after(ms, callback)

    monkeypatch.setattr(root, "after", after)

    def fail(data):
        raise RuntimeError("synthetic rendering error")

    monkeypatch.setattr(app, "_display_preview", fail)
    app.updates.put(("preview", (True, None, app.preview_token)))
    app.poll()
    assert app.poll in scheduled
    assert "synthetic rendering error" in app.status.get()


def test_worker_never_sets_widgets_and_close_waits(desktop, monkeypatch):
    root, app, _ = desktop
    main = threading.get_ident()
    original = app.status.set

    def set_status(value):
        assert threading.get_ident() == main
        original(value)

    monkeypatch.setattr(app.status, "set", set_status)
    started, release = threading.Event(), threading.Event()

    def work():
        assert threading.get_ident() != main
        started.set()
        release.wait(2)

    app._submit("settings_saved", work)
    assert started.wait(2)
    app.close()
    assert app.futures and not app.futures[0].done()
    release.set()
    pump(root, lambda: not app.futures)


def test_cancel_plan_preview_performs_no_operation(desktop, scanned):
    from pathlib import Path
    from app.safety.operations import make_plan
    root, app, _ = desktop
    plan = make_plan(list(scanned.pairs))
    previews = []

    def cancel_preview():
        for child in root.winfo_children():
            if isinstance(child, tk.Toplevel):
                previews.append(child)
                child.destroy()

    root.after(10, cancel_preview)
    app._confirm(plan)
    assert previews
    assert Path(plan.moves[0].source).exists()
    assert not app.journal.records()


def test_close_while_plan_dialog_is_open_never_moves(desktop, scanned):
    from pathlib import Path
    from app.safety.operations import make_plan
    root, app, _ = desktop
    plan = make_plan(list(scanned.pairs))
    root.after(10, app.close)
    app._confirm(plan)
    assert app.closing and app.confirmation_dialog is None
    assert Path(plan.moves[0].source).exists()
    assert not app.journal.records()


def test_pagination_and_bulk_use_entire_session_on_worker(desktop, collection, monkeypatch):
    from dataclasses import replace
    from queue import Queue
    from threading import Event
    from app.core.models import Plan
    from app.matching.indexed import match_index
    from app.services.indexing import pipeline_version
    from app.services.reports import make_report
    root, app, _ = desktop
    main_thread = threading.get_ident()

    def prepare_pages():
        assert threading.get_ident() != main_thread
        summary = app.service.scan([str(collection)], Queue(), Event())
        index = app.service.index
        photo = index.photos(summary.session_id)[0]
        root_id = index.db.execute('SELECT id FROM scan_roots').fetchone()[0]
        for n in range(205):
            p = replace(photo, path=str(collection / f'row-{n:04d}.png'),
                        snapshot=replace(photo.snapshot, identity=replace(photo.snapshot.identity, inode=7000000 + n)))
            index.save_photo(summary.session_id, root_id, 0, p, pipeline_version())
        index.db.execute('DELETE FROM match_results')
        match_index(index, summary.session_id, Event())
        summary = replace(summary, photo_count=207, pair_count=206, exact_count=206)
        report = make_report(index.iter_pairs(summary.session_id), (), app.reports)
        return summary, report, '', app.service.page(summary.session_id, 0), [], ''

    app._submit('scanned', prepare_pages)
    pump(root, lambda: not app.busy)
    assert len(app.pairs) == 200 and app.page_total == 206
    app.change_page(1)
    pump(root, lambda: not app.busy)
    assert app.page_offset == 200 and len(app.pairs) == 6
    assert len(app.tree.get_children()) == 6
    counts = []

    def prepare_all(session, cancel):
        assert threading.get_ident() != main_thread
        counts.append(len(list(app.service.index.iter_pairs(session, exact=True))))
        return Plan('test-empty-plan', (), True)
    monkeypatch.setattr(app.service, 'prepare_session', prepare_all)
    app.move_exact()
    pump(root, lambda: not app.busy)
    assert counts == [206]
    app.change_page(-1)
    pump(root, lambda: not app.busy)
    assert app.page_offset == 0 and len(app.pairs) == 200


def test_incomplete_scan_is_review_only(desktop, monkeypatch):
    root, app, dialogs = desktop
    app.session_id = 'incomplete-session'
    app.scan_complete = False
    called = []
    monkeypatch.setattr(app.service, 'prepare_session', lambda *a: called.append(True))
    app.move_exact()
    assert not called and dialogs
