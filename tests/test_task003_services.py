from dataclasses import replace
import json
import os
from pathlib import Path
from queue import Queue
import shutil
from threading import Event

import pytest

from app.core.models import Approval, Kind, SafetyError
from app.core.queries import MatchQuery, MatchingOptions
from app.services.application import Application
from app.services.state import load_state, validated_settings
from app.storage.index import encode


@pytest.fixture
def service(tmp_path):
    app = Application(tmp_path / 'home')
    app.initialize()
    try:
        yield app
    finally:
        app.close()


def test_settings_preserve_extensions_and_tk_save(service):
    service.update_settings({'theme': 'light', 'custom_extension': {'enabled': True}})
    service.save_settings({'roots': ['synthetic'], 'moves': []})
    state = load_state(service.home / '.photo_agent_state.json')
    assert state['theme'] == 'light' and state['custom_extension'] == {'enabled': True}
    assert state['roots'] == ['synthetic']
    with pytest.raises(ValueError):
        service.update_settings({'theme': 'invalid'})
    assert load_state(service.home / '.photo_agent_state.json') == state
    fixed, warnings = validated_settings({'theme': [], 'phash_max': True, 'moves': []})
    assert fixed['theme'] == 'dark' and fixed['phash_max'] == 4 and len(warnings) == 2


def test_corrupt_history_not_repaired_by_settings(service):
    (service.home / '.photo_agent_state.json').write_text('{broken', encoding='utf-8')
    with pytest.raises(ValueError):
        service.update_settings({'theme': 'light'})
    assert (service.home / '.photo_agent_state.json').read_text() == '{broken'


def test_progress_options_and_direct_groups(service, collection):
    shutil.copy2(collection / 'a.png', collection / 'c.png')
    service.update_settings({'phash_max': 0, 'dhash_max': 1})
    events = []
    result = service.scan([str(collection), str(collection)], Queue(), Event(), events.append)
    assert result.complete
    assert events[-1].processed == events[-1].discovered == 3
    assert events[-1].phase == 'complete'
    metrics = json.loads(service.index.db.execute('SELECT metrics FROM scan_sessions').fetchone()[0])
    assert metrics['matching_options'] == {'phash_max': 0, 'dhash_max': 1}
    groups = service.query_groups(result.session_id, MatchQuery())
    assert groups.total == 1 and groups.items[0].members == 3
    summary = service.dashboard()
    assert summary.indexed == 3 and summary.exact == 2
    assert summary.photo_count == 3 and summary.exact_groups == 1
    assert summary.finished >= summary.started > 0
    assert len(summary.candidates) == 2
    assert summary.potential_bytes == 2 * (collection / 'a.png').stat().st_size
    assert not service.query_matches(result.session_id, MatchQuery(kind='DERIVATIVE')).items
    assert not service.query_matches(result.session_id, MatchQuery(kind='SIMILAR_CAPTURE')).items


def test_global_search_numeric_sort_stable_ids(service, collection):
    result = service.scan([str(collection)], Queue(), Event())
    index = service.index
    entry = index.db.execute('SELECT * FROM scan_entries ORDER BY id DESC LIMIT 1').fetchone()
    photo = index.photos(result.session_id)[1]
    keeper = index.db.execute('SELECT keeper FROM match_results').fetchone()[0]
    # Large synthetic index, with no image decoding beyond the two source fixtures.
    with index.transaction():
        for i in range(220):
            path = str(collection / f'z{i:04d}.png')
            p = replace(photo, path=path, snapshot=replace(photo.snapshot, size=1000 + i))
            cursor = index.db.execute('''INSERT INTO scan_entries(session_id,path,path_key,photo,size,folded,pixels)
                VALUES(?,?,?,?,?,?,?)''', (result.session_id, path, path, encode(p), p.size, path.casefold(), i))
            index.db.execute("INSERT INTO match_results(session_id,keeper,duplicate,kind,pd,dd) VALUES(?,?,?,'EXACT',0,0)",
                (result.session_id, keeper, cursor.lastrowid))
    page = service.query_matches(result.session_id, MatchQuery(sort='size', descending=True))
    following = service.query_matches(result.session_id, MatchQuery(sort='size', descending=True, offset=200))
    sizes = [r.match.dup.size for r in (*page.items, *following.items)]
    assert len(page.items) == 200 and page.total == 221 and sizes == sorted(sizes, reverse=True)
    assert not {r.id for r in page.items} & {r.id for r in following.items}
    found = service.query_matches(result.session_id, MatchQuery(text='z0219'))
    assert found.total == 1 and found.items[0].match.dup.path.endswith('z0219.png')
    assert service.query_matches(result.session_id, MatchQuery(text='%')).total == 0
    with pytest.raises(ValueError):
        MatchQuery(sort='size; DROP TABLE photo_files')
    with pytest.raises(ValueError):
        MatchQuery(limit=201)


def test_group_gallery_global_sort_search_and_bounded_samples(service, collection):
    result = service.scan([str(collection)], None, Event())
    base = service.index.photos(result.session_id)[0]
    from app.core.models import Identity
    # Synthetic cache rows test global paging without decoding 54 extra images.
    # These fabricated paths are never submitted to file-operation services.
    with service.index.transaction():
        for i in range(27):
            entries = []
            for side in ('original', 'copy'):
                path = str(collection / f'group-{i:02d}-{side}.png')
                identity = Identity(1, 1000 + i * 2 + len(entries))
                photo = replace(base, path=path, snapshot=replace(base.snapshot,
                    identity=identity, size=10000 + i, sha256=f'{i:064x}'))
                cursor = service.index.db.execute('''INSERT INTO scan_entries
                    (session_id,path,path_key,photo,size,folded,pixels,device,inode)
                    VALUES(?,?,?,?,?,?,?,?,?)''', (result.session_id, path, path, encode(photo),
                    photo.size, path.casefold(), i, identity.device, identity.inode))
                entries.append(cursor.lastrowid)
            service.index.db.execute('''INSERT INTO match_results
                (session_id,keeper,duplicate,kind,pd,dd) VALUES(?,?,?,'EXACT',0,0)''',
                (result.session_id, *entries))
    first = service.query_groups(result.session_id, MatchQuery(sort='size', descending=True, limit=5))
    second = service.query_groups(result.session_id, MatchQuery(sort='size', descending=True, offset=5, limit=5))
    assert first.total == second.total == 28 and len(first.items) == len(second.items) == 5
    assert not {g.keeper_id for g in first.items} & {g.keeper_id for g in second.items}
    assert first.items[0].keeper_path.endswith('group-26-original.png')
    assert all(len(g.samples) == 2 for g in (*first.items, *second.items))
    found = service.query_groups(result.session_id, MatchQuery(text='group-00-copy'))
    assert found.total == 1 and found.items[0].members == 2
    assert found.items[0].potential_bytes == 10000
    assert (collection / 'a.png').read_bytes() == (collection / 'b.png').read_bytes()


def test_selected_restore_never_falls_back(service, collection):
    shutil.copy2(collection / 'a.png', collection / 'c.png')
    result = service.scan([str(collection)], Queue(), Event())
    plan = service.prepare_session(result.session_id, Event())
    service.execute(plan, Approval(plan), Event())
    history = service.history()
    assert history.total == 2 and all(e.restorable for e in history.items)
    selected = plan.moves[0]
    restore = service.restore_plan(Event(), operation_id=selected.id)
    assert restore.moves[0].restores == selected.id
    service.execute(restore, Approval(restore), Event())
    assert Path(selected.source).exists()
    with pytest.raises(SafetyError, match='no_restore_candidates'):
        service.restore_plan(Event(), operation_id=selected.id)
    with pytest.raises(SafetyError, match='no_restore_candidates'):
        service.restore_plan(Event(), operation_id='missing')
    remaining = next(m for m in plan.moves if m.id != selected.id)
    Path(remaining.source).write_bytes(b'occupied')
    with pytest.raises(SafetyError, match='destination_occupied'):
        service.restore_plan(Event(), operation_id=remaining.id)


def test_matching_defaults_equal_reference(scanned):
    from app.matching.matcher import match
    roots = list(dict.fromkeys(p.root for p in scanned.photos))
    assert match(list(scanned.photos), roots) == match(list(scanned.photos), roots, options=MatchingOptions())
    with pytest.raises(ValueError):
        MatchingOptions(phash_max=65)


def test_dashboard_hardlinks_overlap_offline_and_warning(service, collection):
    try:
        os.link(collection / 'a.png', collection / 'alias.png')
    except OSError as exc:
        pytest.skip(f'Host cannot create a synthetic hardlink: {exc}')
    result = service.scan([str(collection), str(collection.parent)], Queue(), Event())
    summary = service.dashboard(result.session_id)
    assert summary.indexed == 2 and summary.exact == 1
    assert summary.photo_count == 2 and summary.exact_groups == 1
    assert summary.potential_bytes == (collection / 'a.png').stat().st_size
    offline = collection.with_name('offline')
    collection.rename(offline)
    summary = service.dashboard(result.session_id)
    assert 'unavailable_source' in summary.warnings
    assert summary.indexed == 2
    assert (str(collection), 'unavailable') in summary.roots


def test_invalid_ui_defaults_warn_without_damaging_history(service):
    path = service.home / '.photo_agent_state.json'
    path.write_text(json.dumps({'roots': [], 'moves': [], 'theme': 'broken', 'extension': 7}), encoding='utf-8')
    service.close()
    journal, state, issues = service.initialize()
    assert journal.writable and state['theme'] == 'dark'
    assert 'invalid_setting:theme' in issues
    service.save_settings({'roots': [], 'moves': []})
    assert load_state(path)['extension'] == 7 and load_state(path)['theme'] == 'dark'


@pytest.mark.parametrize('report_error', [OSError('report disk failure'), SafetyError('symlink_or_junction')])
def test_report_failure_retains_successful_scan(service, collection, report_error):
    def failed(*args):
        raise report_error
    summary, report, error, page, _, _ = service.scan_with_report(
        [str(collection)], Queue(), Event(), report_writer=failed)
    assert summary.complete and report is None and error == str(report_error)
    assert page[2] == 1


def test_corrupt_settings_allow_scan_but_block_operations(service, collection):
    (service.home / '.photo_agent_state.json').write_text('{broken', encoding='utf-8')
    result = service.scan([str(collection)], Queue(), Event())
    assert result.complete and not service.journal.writable
    with pytest.raises(SafetyError):
        service.prepare_session(result.session_id, Event())


@pytest.mark.parametrize('copies', [0, 1, 2, 4])
def test_dashboard_session_measurements_and_bounded_candidates(service, tmp_path, copies):
    from PIL import Image
    root = tmp_path / 'generated'
    root.mkdir()
    if copies:
        with Image.new('RGB', (40, 30), '#802030') as image:
            image.save(root / '0.png')
        for i in range(1, copies):
            shutil.copy2(root / '0.png', root / f'{i}.png')
    result = service.scan([str(root)], None, Event())
    changes = service.index.db.total_changes
    summary = service.dashboard(result.session_id)
    assert service.index.db.total_changes == changes  # Read-only contract, no schema changes.
    assert summary.status == 'complete' and summary.photo_count == summary.indexed == copies
    assert summary.exact == max(0, copies - 1) and summary.visual == 0
    assert summary.exact_groups == int(copies > 1)
    assert summary.potential_bytes == ((root / '0.png').stat().st_size * (copies - 1) if copies else 0)
    assert len(summary.candidates) == min(3, max(0, copies - 1))


def test_dashboard_whole_index_is_distinct_from_latest_session(service, collection, tmp_path):
    assert service.dashboard().session_id == ''
    first = service.scan([str(collection)], None, Event())
    empty = tmp_path / 'empty'
    empty.mkdir()
    latest = service.scan([str(empty)], None, Event())
    summary = service.dashboard()
    assert summary.session_id == latest.session_id and summary.photo_count == 0
    assert summary.indexed == 2 and summary.exact == summary.exact_groups == 0
    assert not summary.candidates
    assert service.dashboard(first.session_id).photo_count == 2


def test_dashboard_visual_bytes_offline_and_stale(service, collection, tmp_path):
    from PIL import Image
    other_drive = tmp_path / 'other-drive'
    other_drive.mkdir()
    with Image.open(collection / 'a.png') as image:
        image.save(other_drive / 'render.jpg', quality=95)
    missing = tmp_path / 'offline'
    result = service.scan([str(collection), str(other_drive), str(missing)], None, Event())
    summary = service.dashboard(result.session_id)
    assert summary.status == 'incomplete'
    assert summary.photo_count == summary.indexed == 3
    assert summary.exact == summary.exact_groups == summary.visual == summary.errors == 1
    assert summary.potential_bytes == (collection / 'b.png').stat().st_size
    assert {row.match.kind.value for row in summary.candidates} == {'EXACT', 'VISUAL'}
    assert 'scan_review_only' in summary.warnings and 'unavailable_source' in summary.warnings
    with pytest.raises(SafetyError, match='incomplete_scan'):
        service.prepare_session(result.session_id, Event())
    service.index.invalidate({str(collection / 'b.png')})
    assert 'stale_results' in service.dashboard(result.session_id).warnings


def test_dashboard_only_hardlink_has_no_reclaimable_bytes(service, collection):
    (collection / 'b.png').unlink()  # Synthetic fixture only.
    try:
        os.link(collection / 'a.png', collection / 'alias.png')
    except OSError as exc:
        pytest.skip(f'Host cannot create a synthetic hardlink: {exc}')
    result = service.scan([str(collection), str(collection.parent)], None, Event())
    summary = service.dashboard(result.session_id)
    assert summary.photo_count == summary.indexed == 1
    assert summary.exact == summary.exact_groups == summary.potential_bytes == 0
