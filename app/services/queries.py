"""Global SQLite queries; operation eligibility still comes from the journal."""
from __future__ import annotations

from app.core.models import Kind, Match
from app.core.queries import (DashboardSummary, GroupRow, HistoryEntry, MatchQuery,
                              MatchRow, PageResult)
from app.storage.index import decode_photo
from app.storage.index import Index
from app.safety.journal import Journal


def _where(session: str, query: MatchQuery) -> tuple[str, list]:
    sql = "m.session_id=? AND s.state IN ('complete','incomplete')"
    values = [session]
    if query.kind:
        sql += ' AND m.kind=?'
        values.append(query.kind)
    if query.text:
        # instr treats %, _ and backslash as literal search characters.
        sql += ' AND (instr(d.folded,?)>0 OR instr(k.folded,?)>0)'
        values.extend([query.text.casefold()] * 2)
    if query.keeper_id is not None:
        sql += ' AND m.keeper=?'
        values.append(query.keeper_id)
    return sql, values


JOIN = '''FROM match_results m JOIN scan_entries k ON k.id=m.keeper
          JOIN scan_entries d ON d.id=m.duplicate JOIN scan_sessions s ON s.id=m.session_id WHERE '''


def _sort(index: Index, alias: str, key: str) -> str:
    columns = {'name': f'photo_basename({alias}.path)', 'path': f'{alias}.folded',
               'size': f'{alias}.size', 'dimensions': f'{alias}.pixels', 'kind': 'm.kind',
               'format': f"json_extract({alias}.photo,'$.ext')", 'time': 'm.id'}
    if key == 'name':
        index.db.create_function('photo_basename', 1, lambda p: p.replace('\\', '/').rsplit('/', 1)[-1].casefold(), deterministic=True)
    return columns[key]


def matches(index: Index, session: str, query: MatchQuery) -> PageResult[MatchRow]:
    where, values = _where(session, query)
    total = index.db.execute('SELECT count(*) ' + JOIN + where, values).fetchone()[0]
    order = _sort(index, 'd', query.sort) + (' DESC' if query.descending else ' ASC') + ',m.id'
    rows = index.db.execute('SELECT m.id,m.keeper,m.kind,m.pd,m.dd,k.photo AS kept,d.photo AS dup '
                            + JOIN + where + ' ORDER BY ' + order + ' LIMIT ? OFFSET ?',
                            [*values, query.limit, query.offset])
    return PageResult(tuple(MatchRow(r['id'], r['keeper'], Match(Kind(r['kind']),
        decode_photo(r['kept']), decode_photo(r['dup']), r['pd'], r['dd'])) for r in rows), total, query.offset)


def groups(index: Index, session: str, query: MatchQuery) -> PageResult[GroupRow]:
    where, values = _where(session, query)
    base = JOIN + where + ' GROUP BY m.kind,m.keeper'
    total = index.db.execute('SELECT count(*) FROM (SELECT m.keeper ' + base + ')', values).fetchone()[0]
    order = _sort(index, 'k', query.sort) + (' DESC' if query.descending else ' ASC') + ',m.kind,m.keeper'
    rows = index.db.execute('''SELECT m.keeper,m.kind,k.path,k.photo,
        (SELECT count(*)+1 FROM match_results a WHERE a.session_id=m.session_id
         AND a.kind=m.kind AND a.keeper=m.keeper) AS n,
        (SELECT e.photo FROM match_results a JOIN scan_entries e ON e.id=a.duplicate
         WHERE a.session_id=m.session_id AND a.kind=m.kind AND a.keeper=m.keeper
         ORDER BY a.id LIMIT 1) AS sample,
        (SELECT coalesce(sum(size),0) FROM (
            SELECT max(e.size) AS size FROM match_results a
            JOIN scan_entries e ON e.id=a.duplicate
            WHERE a.session_id=m.session_id AND a.kind='EXACT' AND a.keeper=m.keeper
            AND e.device IS NOT NULL AND e.inode IS NOT NULL
            AND NOT EXISTS (SELECT 1 FROM match_results b JOIN scan_entries kept ON kept.id=b.keeper
                WHERE b.session_id=a.session_id AND kept.device=e.device AND kept.inode=e.inode)
            GROUP BY e.device,e.inode)) AS space ''' + base
        + ' ORDER BY ' + order + ' LIMIT ? OFFSET ?', [*values, query.limit, query.offset])
    return PageResult(tuple(GroupRow(r['keeper'], r['kind'], r['path'], r['n'],
        tuple(decode_photo(p) for p in (r['photo'], r['sample']) if p),
        r['space'] if r['kind'] == 'EXACT' else None) for r in rows), total, query.offset)


def dashboard(index: Index, session: str | None, warning: str) -> DashboardSummary:
    db = index.db
    indexed = db.execute("SELECT count(*) FROM (SELECT device,inode FROM photo_files WHERE state NOT IN ('missing','moved') GROUP BY device,inode)").fetchone()[0]
    row = db.execute('SELECT * FROM scan_sessions WHERE id=?', (session,)).fetchone() if session else db.execute(
        'SELECT * FROM scan_sessions ORDER BY started DESC,id DESC LIMIT 1').fetchone()
    if row is None:
        return DashboardSummary(indexed, warnings=(warning,) if warning else ())
    session = row['id']
    counts = dict(db.execute('SELECT kind,count(*) FROM match_results WHERE session_id=? GROUP BY kind', (session,)))
    space = db.execute('''WITH retained AS (
        SELECT DISTINCT e.device,e.inode FROM match_results m JOIN scan_entries e ON e.id=m.keeper
        WHERE m.session_id=?)
        SELECT coalesce(sum(size),0) FROM (SELECT d.device,d.inode,max(d.size) AS size
        FROM match_results m JOIN scan_entries d ON d.id=m.duplicate
        LEFT JOIN retained k ON k.device=d.device AND k.inode=d.inode
        WHERE m.session_id=? AND m.kind='EXACT' AND d.device IS NOT NULL AND d.inode IS NOT NULL
        AND k.device IS NULL GROUP BY d.device,d.inode)''', (session, session)).fetchone()[0]
    errors = db.execute("SELECT count(*) FROM scan_entries WHERE session_id=? AND error<>''", (session,)).fetchone()[0]
    roots = tuple(tuple(r) for r in db.execute('SELECT path,state FROM scan_session_roots WHERE session_id=? ORDER BY position', (session,)))
    warnings = [warning] if warning else []
    if row['state'] != 'complete':
        warnings.append('scan_review_only')
    if db.execute("SELECT 1 FROM scan_entries e JOIN photo_files f ON f.id=e.file_id WHERE e.session_id=? AND (f.state<>'present' OR f.sha256<>e.sha256) LIMIT 1", (session,)).fetchone():
        warnings.append('stale_results')
    photos = db.execute('SELECT count(photo) FROM scan_entries WHERE session_id=?', (session,)).fetchone()[0]
    exact_groups = groups(index, session, MatchQuery(kind='EXACT', limit=1)).total
    candidates = matches(index, session, MatchQuery(limit=3)).items
    return DashboardSummary(indexed, session, row['state'], row['started'], counts.get('EXACT', 0),
                            counts.get('VISUAL', 0), space, errors, roots, tuple(warnings),
                            photos, exact_groups, row['finished'] or 0, candidates)


def history(journal: Journal, query: MatchQuery) -> PageResult[HistoryEntry]:
    records = journal.records()
    restored = {r['move']['restores'] for r in records if r.get('move', {}).get('action') == 'restore'
                and r['state'] in ('intent', 'blocked', 'complete')}
    entries = []
    for r in records:
        move = r.get('move', {})
        legacy = r.get('entry', {})
        source, destination = move.get('source', legacy.get('origin', '')), move.get('destination', legacy.get('dest', ''))
        if query.text.casefold() not in (source + '\n' + destination).casefold():
            continue
        event = r['transitions'][-1]
        eligible = r['id'] not in restored and (r['state'] == 'legacy' or
                   r['state'] == 'complete' and move.get('action') == 'quarantine')
        detail = '\n'.join(t['detail'] for t in r['transitions'] if t.get('detail'))
        # Recovery's "reconciled" timestamp describes discovery after a crash,
        # not the actual move. Legacy import time is likewise not a move date.
        complete = next((t for t in r['transitions'] if t['state'] == 'complete'), None)
        moved_at = (complete['at'] if move.get('action') == 'quarantine' and complete
                    and complete.get('detail') != 'reconciled' else None)
        entries.append(HistoryEntry(r['id'], event['at'], source, destination, r['state'], detail, eligible,
                                    moved_at, move.get('expected', {}).get('size'),
                                    move.get('action', 'quarantine'), r['id'] in restored))
    entries.sort(key=lambda e: (e.at, e.id), reverse=query.descending)
    return PageResult(tuple(entries[query.offset:query.offset + query.limit]), len(entries), query.offset)
