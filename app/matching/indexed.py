"""Streaming exact grouping and a disk-backed BK tree with original semantics."""
from __future__ import annotations

from threading import Event

from app.matching.matcher import ASPECT_MAX, DHASH_MAX, PHASH_MAX, aspect
from app.safety.paths import cancelled
from app.storage.index import Index, decode_photo


def match_index(index: Index, session: str, cancel: Event) -> None:
    db = index.db
    for table in ('bk_nodes', 'bk_members', 'bk_frontier'):
        db.execute(f'DROP TABLE IF EXISTS temp.{table}')
    db.execute('CREATE TEMP TABLE bk_nodes(id INTEGER PRIMARY KEY,hash TEXT NOT NULL,parent INTEGER,edge INTEGER,UNIQUE(parent,edge))')
    db.execute('CREATE TEMP TABLE bk_members(node INTEGER,entry INTEGER PRIMARY KEY)')
    db.execute('CREATE INDEX temp.bk_member_node ON bk_members(node)')
    db.execute('CREATE TEMP TABLE bk_frontier(id INTEGER PRIMARY KEY)')
    previous, keeper = None, None
    # SQL sorting spills to disk; never build the collection or an exact group in RAM.
    rows = db.execute('''SELECT id,size,sha256 FROM scan_entries WHERE session_id=? AND photo IS NOT NULL
                         ORDER BY size,sha256,rank,folded,path''', (session,))
    for row in rows:
        cancelled(cancel)
        key = row['size'], row['sha256']
        if key != previous:
            previous, keeper = key, row['id']
        else:
            with index.transaction():
                db.execute("INSERT INTO match_results(session_id,keeper,duplicate,kind,pd,dd) VALUES(?,?,?,'EXACT',0,0)",
                           (session, keeper, row['id']))
    rows = db.execute('''SELECT e.id,e.photo FROM scan_entries e WHERE e.session_id=? AND e.phash<>''
        AND NOT EXISTS(SELECT 1 FROM match_results m WHERE m.session_id=? AND m.duplicate=e.id)
        ORDER BY raw DESC,pixels DESC,format_rank DESC,size DESC,rank,folded DESC,e.id''', (session, session))
    for row in rows:
        cancelled(cancel)
        photo = decode_photo(row['photo'])
        h = int(photo.phash, 16)
        best = None
        db.execute('DELETE FROM bk_frontier')
        db.execute('INSERT INTO bk_frontier SELECT id FROM bk_nodes WHERE parent IS NULL')
        while node := db.execute('SELECT n.* FROM bk_frontier f JOIN bk_nodes n ON n.id=f.id LIMIT 1').fetchone():
            cancelled(cancel)
            db.execute('DELETE FROM bk_frontier WHERE id=?', (node['id'],))
            distance = (h ^ int(node['hash'], 16)).bit_count()
            if distance <= PHASH_MAX:
                for member in db.execute('SELECT e.id,e.photo FROM bk_members b JOIN scan_entries e ON e.id=b.entry WHERE b.node=?', (node['id'],)):
                    cancelled(cancel)
                    other = decode_photo(member['photo'])
                    dd = (int(photo.dhash, 16) ^ int(other.dhash, 16)).bit_count()
                    delta = abs(aspect(photo) - aspect(other)) / max(aspect(photo), aspect(other))
                    candidate = (distance, dd, other.path, member['id'])
                    if dd <= DHASH_MAX and delta <= ASPECT_MAX and (best is None or candidate < best):
                        best = candidate
            db.execute('INSERT INTO bk_frontier SELECT id FROM bk_nodes WHERE parent=? AND edge BETWEEN ? AND ?',
                       (node['id'], distance - PHASH_MAX, distance + PHASH_MAX))
        if best:
            with index.transaction():
                db.execute("INSERT INTO match_results(session_id,keeper,duplicate,kind,pd,dd) VALUES(?,?,?,'VISUAL',?,?)",
                           (session, best[3], row['id'], best[0], best[1]))
            continue  # Followers never enter the tree: no transitive visual chains.
        node = db.execute('SELECT * FROM bk_nodes WHERE parent IS NULL').fetchone()
        if node is None:
            node_id = db.execute('INSERT INTO bk_nodes(hash) VALUES(?)', (photo.phash,)).lastrowid
        else:
            while True:
                cancelled(cancel)
                distance = (h ^ int(node['hash'], 16)).bit_count()
                if distance == 0:
                    node_id = node['id']
                    break
                child = db.execute('SELECT * FROM bk_nodes WHERE parent=? AND edge=?', (node['id'], distance)).fetchone()
                if child is None:
                    node_id = db.execute('INSERT INTO bk_nodes(hash,parent,edge) VALUES(?,?,?)',
                                         (photo.phash, node['id'], distance)).lastrowid
                    break
                node = child
        db.execute('INSERT INTO bk_members VALUES(?,?)', (node_id, row['id']))
