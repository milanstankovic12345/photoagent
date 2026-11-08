"""SQLite and service regressions; all paths and image bytes are synthetic."""
from dataclasses import replace
import hashlib
import json
import os
from pathlib import Path
from queue import Queue
import shutil
import sqlite3
import subprocess
import sys
from threading import Event

from PIL import Image
import pytest

from app.core.models import Approval, Cancelled, Kind, Match, SafetyError
from app.services.application import Application
from app.services.indexing import indexed_scan, pipeline_version
from app.storage.index import Index, PAGE_SIZE, SQL, decode_photo, encode, migrate


@pytest.fixture
def service(tmp_path):
    app = Application(tmp_path / 'home')
    app.initialize()
    try:
        yield app
    finally:
        app.close()


def scan(service, *roots, cancel=None):
    return service.scan([str(r) for r in roots], Queue(), cancel or Event())


def test_cold_warm_and_restart_reuse(service, collection):
    cold = scan(service, collection)
    warm = scan(service, collection)
    assert cold.complete and (cold.photo_count, cold.decodes, cold.hash_reads) == (2, 2, 4)
    assert warm.complete and (warm.cache_hits, warm.decodes, warm.hash_reads) == (2, 0, 2)
    assert service.index.pairs(cold.session_id) == service.index.pairs(warm.session_id)
    service.close()
    service.initialize()
    restarted = scan(service, collection)
    assert restarted.cache_hits == 2 and restarted.decodes == 0


def test_changed_same_size_mtime_detected(service, tmp_path):
    root = tmp_path / 'photos'
    root.mkdir()
    for name in ('a.bmp', 'b.bmp'):
        with Image.new('RGB', (16, 16), 'red') as image:
            image.save(root / name)
    scan(service, root)
    path = root / 'b.bmp'
    st = path.stat()
    with Image.new('RGB', (16, 16), 'blue') as image:
        image.save(path)
    os.utime(path, ns=(st.st_atime_ns, st.st_mtime_ns))
    assert path.stat().st_size == st.st_size
    value = scan(service, root)
    assert value.complete and value.decodes == 1 and value.cache_hits == 1
    assert value.exact_count == 0


def test_new_removed_renamed_and_replaced(service, collection):
    scan(service, collection)
    (collection / 'a.png').rename(collection / 'renamed.png')
    (collection / 'b.png').unlink()
    with Image.new('RGB', (24, 24), 'green') as image:
        image.save(collection / 'new.png')
    result = scan(service, collection)
    states = {Path(r['path']).name: r['state'] for r in service.index.db.execute('SELECT path,state FROM photo_files')}
    assert states == {'a.png': 'moved', 'b.png': 'missing', 'renamed.png': 'present', 'new.png': 'present'}
    assert result.photo_count == 2 and result.decodes == 2
    replacement = collection / 'replacement.png'
    shutil.copy2(collection / 'new.png', replacement)
    replacement.replace(collection / 'new.png')
    assert scan(service, collection).decodes == 1


def test_offline_root_preserves_records_and_reconnects(service, collection):
    scan(service, collection)
    parked = collection.with_name('offline')
    collection.rename(parked)
    missing = scan(service, collection)
    assert not missing.complete and missing.pair_count == 0
    assert {r[0] for r in service.index.db.execute('SELECT state FROM photo_files')} == {'present'}
    parked.rename(collection)
    assert scan(service, collection).complete


def test_different_root_identity_never_sweeps_old_library(service, collection):
    scan(service, collection)
    collection.rename(collection.with_name('original-volume'))
    collection.mkdir()
    result = scan(service, collection)
    assert result.complete and result.photo_count == 0
    assert {r[0] for r in service.index.db.execute('SELECT state FROM photo_files')} == {'present'}
    assert service.index.db.execute('SELECT count(*) FROM scan_roots').fetchone()[0] == 2


def test_partial_traversal_cannot_mark_missing(service, collection, monkeypatch):
    scan(service, collection)
    import app.services.indexing as indexing

    def partial(root, cancel, error, **kwargs):
        yield root / 'a.png'
        error(str(root), PermissionError('synthetic denied'))
    monkeypatch.setattr(indexing, 'discover', partial)
    result = scan(service, collection)
    assert not result.complete and not result.pair_count
    assert {r[0] for r in service.index.db.execute('SELECT state FROM photo_files')} == {'present'}


def test_overlapping_roots_hardlinks_and_root_priority(service, collection):
    sub = collection / 'sub'
    sub.mkdir()
    shutil.copy2(collection / 'a.png', sub / 'first.png')
    os.link(collection / 'a.png', collection / 'hardlink.png')
    result = scan(service, sub, collection, sub)
    assert result.photo_count == 3 and result.exact_count == 2
    assert all(p.keep.root == str(sub) for p in service.index.iter_pairs(result.session_id))


def test_new_hardlink_alias_is_not_misclassified_as_move(service, collection):
    scan(service, collection)
    os.link(collection / 'a.png', collection / '0-alias.png')
    result = scan(service, collection)
    assert result.photo_count == 2
    row = service.index.db.execute('SELECT state FROM photo_files WHERE path=?', (str(collection / 'a.png'),)).fetchone()
    assert row[0] == 'present'


def test_cancelled_scan_keeps_cache_without_operational_results(service, collection, monkeypatch):
    event = Event()
    save = service.index.save_photo

    def stop(*args):
        save(*args)
        event.set()
    monkeypatch.setattr(service.index, 'save_photo', stop)
    result = scan(service, collection, cancel=event)
    assert result.cancelled and result.photo_count == 1 and result.pair_count == 0
    with pytest.raises(SafetyError, match='incomplete_scan'):
        service.prepare_session(result.session_id, Event())
    monkeypatch.setattr(service.index, 'save_photo', save)
    assert scan(service, collection).cache_hits == 1


def test_cancel_matching_discards_partial_pairs(service, collection, monkeypatch):
    import app.services.indexing as indexing

    def stop(*args):
        raise Cancelled()
    monkeypatch.setattr(indexing, 'match_index', stop)
    result = scan(service, collection)
    assert result.cancelled and result.pair_count == 0


def test_decoder_version_and_corrupt_cache_force_redecode(service, collection, monkeypatch):
    scan(service, collection)
    service.index.db.execute("UPDATE image_fingerprints SET checksum=?", ('0' * 64,))
    assert scan(service, collection).decodes == 2
    import app.services.indexing as indexing
    monkeypatch.setattr(indexing, 'pipeline_version', lambda: pipeline_version() + ':changed')
    assert scan(service, collection).decodes == 2


def test_semantically_invalid_cache_even_with_checksum_rejected(service, collection):
    scan(service, collection)
    for row in service.index.db.execute('SELECT * FROM image_fingerprints').fetchall():
        payload = json.loads(row['payload'])
        payload['phash'] = 'not-a-hash'
        text = json.dumps(payload)
        service.index.db.execute('UPDATE image_fingerprints SET payload=?,checksum=? WHERE file_id=?',
                                 (text, hashlib.sha256(text.encode()).hexdigest(), row['file_id']))
    assert scan(service, collection).decodes == 2


def test_corrupt_cached_sha_never_authorizes_move(service, collection):
    result = scan(service, collection)
    pair = service.index.pairs(result.session_id)[0]
    forged = replace(pair.dup, snapshot=replace(pair.dup.snapshot, sha256='0' * 64))
    with pytest.raises(SafetyError, match='candidate_changed'):
        service.prepare([replace(pair, dup=forged)], Event())
    assert (collection / 'a.png').exists() and (collection / 'b.png').exists()
    assert not service.journal.records()


def test_cache_cannot_forge_bulk_decodability(service, tmp_path):
    root = tmp_path / 'photos'
    root.mkdir()
    (root / 'a.png').write_bytes(b'broken image')
    shutil.copy2(root / 'a.png', root / 'b.png')
    result = scan(service, root)
    assert result.exact_count == 1  # Binary matching remains reviewable despite decode errors.
    with pytest.raises(SafetyError, match='incomplete_scan'):
        service.prepare_session(result.session_id, Event())
    photos = service.index.photos(result.session_id)
    forged = [replace(p, decode_error='', phash='0' * 16, dhash='0' * 16, width=1, height=1) for p in photos]
    plan = service.prepare([Match(Kind.EXACT, *forged)], Event(), bulk=True)
    assert not plan.moves


def test_cache_cannot_hide_raw_flags(service, tmp_path):
    root = tmp_path / 'photos'
    root.mkdir()
    (root / 'a.dng').write_bytes(b'broken raw')
    shutil.copy2(root / 'a.dng', root / 'b.dng')
    result = scan(service, root)
    photos = service.index.photos(result.session_id)
    plan = service.prepare([Match(Kind.EXACT, *(replace(p, is_raw=False) for p in photos))], Event())
    assert plan.moves[0].raw
    with pytest.raises(SafetyError, match='raw_confirmation'):
        service.execute(plan, Approval(plan), Event())


def test_plan_confirmation_move_restore_and_projection(service, collection):
    result = scan(service, collection)
    plan = service.prepare_session(result.session_id, Event())
    assert len(plan.moves) == 1
    assert Path(plan.moves[0].source).exists()
    service.execute(plan, Approval(plan), Event())
    assert not service.index.pairs(result.session_id)
    assert 'image_format' not in service.journal.records()[0]['move']['keeper']
    assert service.index.db.execute('SELECT state FROM quarantine_operations').fetchone()[0] == 'complete'
    service.close()
    service.initialize()
    restore = service.restore_plan(Event())
    service.execute(restore, Approval(restore), Event())
    assert (collection / 'a.png').exists() and (collection / 'b.png').exists()


def test_projection_failure_does_not_mask_successful_move(service, collection, monkeypatch):
    result = scan(service, collection)
    plan = service.prepare_session(result.session_id, Event())

    def fail(*args):
        raise sqlite3.OperationalError('synthetic full disk')
    monkeypatch.setattr(service.index, 'project_history', fail)
    moved = service.execute(plan, Approval(plan), Event())
    assert moved and service.journal.records()[0]['state'] == 'complete'
    assert 'synthetic full disk' in service.index_warning


def test_schema_constraints_and_idempotence(tmp_path):
    path = tmp_path / 'index.sqlite3'
    index = Index(path)
    assert index.db.execute('PRAGMA user_version').fetchone()[0] == 1
    assert index.db.execute('PRAGMA foreign_keys').fetchone()[0] == 1
    assert index.db.execute('PRAGMA journal_mode').fetchone()[0] == 'wal'
    migrate(index.db, path)
    with pytest.raises(sqlite3.IntegrityError):
        index.db.execute("INSERT INTO scan_sessions(id,state,started) VALUES('x','invalid',0)")
    index.close()


def test_failed_migration_rolls_back(tmp_path, monkeypatch):
    import app.storage.index as storage
    path = tmp_path / 'index.sqlite3'
    monkeypatch.setitem(storage.MIGRATIONS, 1, SQL + ('INVALID SQL',))
    with pytest.raises(sqlite3.Error):
        Index(path)
    with sqlite3.connect(path) as db:
        assert db.execute('PRAGMA user_version').fetchone()[0] == 0
        assert not db.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()


def test_future_schema_preserved_and_fallback(tmp_path):
    home = tmp_path / 'home'
    home.mkdir()
    path = home / '.photo_agent_index.sqlite3'
    with sqlite3.connect(path) as db:
        db.execute('PRAGMA user_version=99')
    before = path.read_bytes()
    app = Application(home)
    try:
        app.initialize()
        assert app.temporary and 'index_newer_schema' in app.index_warning
        assert path.read_bytes() == before
        assert app.journal.writable
    finally:
        app.close()


def test_corrupt_database_preserved(tmp_path):
    home = tmp_path / 'home'
    home.mkdir()
    path = home / '.photo_agent_index.sqlite3'
    path.write_bytes(b'damaged database')
    app = Application(home)
    try:
        app.initialize()
        assert app.temporary and path.read_bytes() == b'damaged database'
    finally:
        app.close()


def test_competing_instance_uses_temporary_index(service):
    other = Application(service.home)
    try:
        other.initialize()
        assert other.temporary and 'index_busy' in other.index_warning
        assert not other.journal.writable
    finally:
        other.close()


def test_actual_process_cannot_take_index_writer_lease(service):
    script = '''import sys
from app.storage.index import Index
from app.core.models import SafetyError
from pathlib import Path
try:
    index=Index(Path(sys.argv[1]))
except SafetyError as exc:
    assert str(exc)=='index_busy'
else:
    index.close()
    raise AssertionError('competing writer obtained lease')
'''
    result = subprocess.run([sys.executable, '-B', '-c', script, str(service.index.path)],
                            capture_output=True, timeout=20)
    assert result.returncode == 0, result.stderr.decode(errors='replace')


def test_actual_process_crash_rolls_back_and_marks_interrupted(tmp_path):
    path = tmp_path / 'crash.sqlite3'
    index = Index(path)
    index.close()
    script = '''import os, sqlite3, sys
from pathlib import Path
p=Path(sys.argv[1]); assert p.is_relative_to(Path(os.environ['HOME']))
c=sqlite3.connect(p)
c.execute("INSERT INTO scan_sessions(id,state,started) VALUES('old','running',0)")
c.commit()
c.execute("BEGIN IMMEDIATE")
c.execute("INSERT INTO scan_sessions(id,state,started) VALUES('uncommitted','running',0)")
os._exit(91)
'''
    result = subprocess.run([sys.executable, '-B', '-c', script, str(path)], timeout=20)
    assert result.returncode == 91
    index = Index(path)
    try:
        assert [tuple(r) for r in index.db.execute('SELECT id,state FROM scan_sessions')] == [('old', 'interrupted')]
        assert index.db.execute('PRAGMA integrity_check').fetchone()[0] == 'ok'
    finally:
        index.close()


def test_failed_write_keeps_previous_cache_and_no_candidates(service, collection):
    scan(service, collection)
    service.index.db.execute("CREATE TRIGGER fail_write BEFORE INSERT ON scan_entries BEGIN SELECT RAISE(FAIL, 'synthetic disk failure'); END")
    with pytest.raises(sqlite3.Error, match='synthetic disk failure'):
        scan(service, collection)
    assert service.index.db.execute("SELECT count(*) FROM scan_sessions WHERE state='failed'").fetchone()[0] == 1
    assert service.index.db.execute('SELECT count(*) FROM photo_files').fetchone()[0] == 2


def test_index_decoder_omits_preview(collection):
    from app.scanning.decoder import decode
    value = decode(collection / 'a.png', preview=False)
    assert 'preview' not in value and value['image_format'] == 'PNG'
    assert len(value['phash']) == len(value['dhash']) == 16


def test_indexed_matching_equivalent_and_paged(service, collection, monkeypatch):
    from app.matching.matcher import match
    from app.matching.indexed import match_index
    from app.safety.paths import identity
    result = scan(service, collection)
    original = service.index.photos(result.session_id)[0]
    # Synthetic model rows exercise disk sorting/paging without 205 decoder processes.
    rank = 0
    root_id = service.index.root(str(collection), identity(collection))
    for n in range(205):
        snap = replace(original.snapshot, identity=replace(original.snapshot.identity, inode=9000000 + n))
        p = replace(original, path=str(collection / f'synthetic-{n:04d}.png'), snapshot=snap)
        service.index.save_photo(result.session_id, root_id, rank, p, pipeline_version())
    service.index.db.execute('DELETE FROM match_results WHERE session_id=?', (result.session_id,))
    match_index(service.index, result.session_id, Event())
    first = service.index.pairs(result.session_id)
    second = service.index.pairs(result.session_id, PAGE_SIZE)
    assert len(first) == 200 and len(second) == 6
    photos = service.index.photos(result.session_id) + service.index.photos(result.session_id, PAGE_SIZE)
    assert tuple(service.index.iter_pairs(result.session_id)) == match(photos, [str(collection)])
    from app.services.reports import make_report
    report = make_report(service.index.iter_pairs(result.session_id), (), service.home / 'reports')
    assert len(report.read_text(encoding='utf-8-sig').splitlines()) == 207


def test_no_gui_import_in_storage_or_orchestration():
    result = subprocess.run([sys.executable, '-B', '-c',
                             "import sys; import app.storage.index, app.services.application; assert 'tkinter' not in sys.modules"],
                            capture_output=True, timeout=20)
    assert result.returncode == 0, result.stderr.decode(errors='replace')


def test_forward_migration_backup_and_failure_preserve_data(tmp_path, monkeypatch):
    import app.storage.index as storage
    path = tmp_path / 'upgrade.sqlite3'
    index = Index(path)
    index.db.execute("INSERT INTO scan_sessions(id,state,started) VALUES('history','complete',0)")
    index.close()
    monkeypatch.setattr(storage, 'SCHEMA_VERSION', 2)
    monkeypatch.setitem(storage.MIGRATIONS, 2, ('ALTER TABLE scan_sessions ADD COLUMN example INTEGER', 'INVALID SQL'))
    with pytest.raises(sqlite3.Error):
        Index(path)
    with sqlite3.connect(path) as db:
        assert db.execute('PRAGMA user_version').fetchone()[0] == 1
        assert db.execute('SELECT id FROM scan_sessions').fetchone()[0] == 'history'
        assert 'example' not in [r[1] for r in db.execute('PRAGMA table_info(scan_sessions)')]
    backups = list(tmp_path.glob('*.bak'))
    assert len(backups) == 1
    with sqlite3.connect(backups[0]) as backup:
        assert backup.execute('SELECT id FROM scan_sessions').fetchone()[0] == 'history'
    monkeypatch.setitem(storage.MIGRATIONS, 2, ('ALTER TABLE scan_sessions ADD COLUMN example INTEGER',))
    upgraded = Index(path)
    try:
        assert upgraded.db.execute('PRAGMA user_version').fetchone()[0] == 2
        assert upgraded.db.execute('SELECT id,example FROM scan_sessions').fetchone()[0] == 'history'
    finally:
        upgraded.close()


def test_busy_transaction_wait_is_cancellable(service):
    from threading import Timer
    external = sqlite3.connect(service.index.path, timeout=0)
    cancel = Event()
    service.index.cancel = cancel
    timer = Timer(.1, cancel.set)
    try:
        external.execute('BEGIN IMMEDIATE')
        timer.start()
        with pytest.raises(Cancelled):
            with service.index.transaction():
                pytest.fail('must not enter locked transaction')
    finally:
        timer.join()
        external.rollback()
        external.close()
        service.index.cancel = None


def test_indexed_visual_matching_equals_reference_and_not_transitive(service, collection):
    from app.matching.indexed import match_index
    from app.matching.matcher import match
    result = scan(service, collection)
    base = service.index.photos(result.session_id)[0]
    service.index.db.execute('DELETE FROM match_results')
    service.index.db.execute('DELETE FROM scan_entries')
    root_id = service.index.db.execute('SELECT id FROM scan_roots').fetchone()[0]
    photos = []
    for n, (name, phash) in enumerate((('z.png', '0000000000000000'), ('y.png', '000000000000000f'), ('x.png', '00000000000000ff'))):
        p = replace(base, path=str(collection / name), phash=phash, dhash='0' * 16,
                    snapshot=replace(base.snapshot, sha256=str(n) * 64,
                                     identity=replace(base.snapshot.identity, inode=8000000 + n)))
        photos.append(p)
        service.index.save_photo(result.session_id, root_id, 0, p, pipeline_version())
    match_index(service.index, result.session_id, Event())
    pairs = tuple(service.index.iter_pairs(result.session_id))
    assert pairs == match(photos, [str(collection)])
    assert len(pairs) == 1 and pairs[0].dup.path.endswith('y.png')


def test_sqlite_memory_policy_and_dedup_queries_use_indexes(service):
    db = service.index.db
    assert db.execute('PRAGMA cache_size').fetchone()[0] == -8192
    assert db.execute('PRAGMA temp_store').fetchone()[0] == 1
    assert PAGE_SIZE == 200
    details = ' '.join(r[3] for r in db.execute("EXPLAIN QUERY PLAN SELECT 1 FROM scan_entries WHERE session_id=? AND device=? AND inode=? AND photo IS NOT NULL", ('s', '1', '2')))
    assert 'entries_identity' in details and 'SEARCH' in details


def test_index_worker_confined_decoder_and_error_retention(service, tmp_path):
    root = tmp_path / 'photos'
    root.mkdir()
    (root / 'broken.raw').write_bytes(b'unsupported extension')
    (root / 'broken.dng').write_bytes(b'malformed RAW')
    result = scan(service, root)
    assert not result.complete and result.photo_count == 1 and result.error_count == 1
    assert service.index.errors(result.session_id)
    assert scan(service, root).decodes == 1  # Errors are retried, never immortal cache hits.
