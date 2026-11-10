"""Verify current Task014 PNGs and assemble review sheets, without altering them.

Run once to create audit.json/sheets. Only run --mark-reviewed AFTER opening every
sheet. That flag records human/agent inspection; hash checks alone are not review.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).parent


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(mark_reviewed: bool) -> None:
    if mark_reviewed:
        audit_path = ROOT / 'audit.json'
        audit = json.loads(audit_path.read_text(encoding='utf-8'))
        for sheet in audit['review_sheets']:
            assert digest(ROOT / sheet['file']) == sheet['sha256']
            sheet['visually_reviewed'] = True
        for entry in audit['captures']:
            assert digest(ROOT / entry['file']) == entry['sha256']
            entry['visually_reviewed'] = True
            entry['review_method'] = 'contact sheet; representative originals additionally opened at full size'
        assert not any('running;' in command['result'] for command in audit['commands'])
        audit['finished'] = True
        audit['reviewed_at_utc'] = datetime.now(timezone.utc).isoformat()
        audit_path.write_text(json.dumps(audit, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        print(f'Recorded visual review of {len(audit["captures"])} captures.')
        return

    assert not (ROOT / 'audit.json').exists(), 'Use a new evidence directory'
    audit = {'task': 'Task014', 'finished': False, 'date_local': '2026-11-10', 'timezone': 'Europe/Belgrade',
        'source_commit': '95d5698eccd9335d115c77728b8f76feb1411cf5',
        'initial_git_status': 'clean', 'production_code_changed': False,
        'created_at_utc': datetime.now(timezone.utc).isoformat(),
        'references': [], 'runs': [], 'captures': [], 'review_sheets': [],
        'commands': [
            {'command': '.venv/Scripts/python.exe -B <product-design>/skills/user-context/scripts/user_context_preflight.py',
             'result': 'exit 0; saved context missing; no external state written'},
            {'command': '.venv/Scripts/python.exe -B docs/design/verification/task014-20261110/capture.py (sandbox)',
             'result': 'exit 1 before Python start; Microsoft Store interpreter process creation failed; not a completed capture run'},
            {'command': '.venv/Scripts/python.exe -B docs/design/verification/task014-20261110/capture.py (approved runner)',
             'result': 'exit 0; 116 captures; sandbox cleaned after all workers stopped'},
            {'command': '.venv/Scripts/python.exe -B docs/design/verification/task014-20261110/supplement.py (approved runner, initial attempt)',
             'result': 'exit 0; 12 captures; original bytes preserved; sandbox cleaned; superseded after visual inspection found details below the viewport'},
            {'command': '.venv/Scripts/python.exe -B docs/design/verification/task014-20261110/supplement.py --output docs/design/verification/task014-20261110/supplement-r2 (approved runner)',
             'result': 'exit 0; 14 captures; corrected capture scroll timing, actual scan errors; original bytes preserved; sandbox cleaned'},
            {'command': '.venv/Scripts/python.exe -B -m pytest tests/test_task008.py tests/test_task009.py tests/test_task010.py tests/test_task012.py tests/test_qt_design_system.py -q',
             'result': 'exit 0; 61 passed in 815.35s (0:13:35); 0 skipped; 0 failed'},
        ],
        'superseded_evidence': [{'directory': 'supplement', 'manifest': 'supplement/manifest.json',
            'reason': 'Process succeeded, but visual review found member/photo/settings details below the captured viewport. Replaced by new captures in supplement-r2; original files retained.'},
            {'file': 'audit-initial.json', 'reason': 'Initial index before correcting supplemental capture framing; unreviewed, excluded from final acceptance.'},
            {'files': 'review-01.jpg through review-16.jpg', 'reason': 'Initial review sheets retained; final set uses review-final-*.'}],
        'limits': [
            'Visual evidence is current Qt offscreen Fusion rendering, not native desktop interaction or full functional acceptance.',
            'Only DPR 1 in this audit; 1280x720,1366x768,1650x900,1920x1080 for the six main surfaces in EN/Dark/Light.',
            'Extended baseline scenarios at 1650x900; supplement at 1280x720 includes representative Serbian views.',
            'No native Linux, physical Windows DPI/monitor transitions, NVDA/Narrator or physical drive tests.',
            'No successful RAW decode, physical power-loss or real OS photo viewer launch.',
            'System scheme changes injected; loading/unavailable and combined RAW/legacy warnings are presentation fixtures.',
            'Settings diagnostic presentation was injected, not an actual failed settings write.',
            'Existing driver manifest retains its historical Task011 name, 48-matrix description and skip wording; this audit is not a new Task011/012/013 acceptance claim.',
            'Transient dashboard thumbnail loading in matrix captures is not evidence of a decode failure.',
        ]}
    repository = ROOT.parents[3]
    for name in ('target_reference.png', 'current_ui.png', 'reference_sidebar_icons.png'):
        path = repository / 'docs/design' / name
        audit['references'].append({'file': 'docs/design/' + name,
            'exists': path.exists(), 'sha256': digest(path), 'visually_reviewed': True,
            'role': 'provided historical/concept reference; not current-run evidence'})
    for folder, expected in (('baseline', 116), ('supplement-r2', 14)):
        source = ROOT / folder / 'manifest.json'
        manifest = json.loads(source.read_text(encoding='utf-8'))
        assert manifest['finished'] and manifest['synthetic']
        assert len(manifest['captures']) == expected
        audit['runs'].append({'manifest': folder + '/manifest.json', 'sha256': digest(source),
            'capture_count': expected, 'checks': manifest['checks'],
            'python': manifest.get('python'), 'qt': manifest.get('qt_version'),
            'platform': manifest.get('platform'), 'qt_platform': manifest.get('qt_platform')})
        for entry in manifest['captures']:
            path = ROOT / folder / entry['file']
            assert digest(path) == entry['sha256']
            with Image.open(path) as captured:
                assert list(captured.size) == entry['pixel_size']
                assert captured.getextrema() != ((0, 0),) * len(captured.getbands())
            assert entry['dpr'] == 1
            layout = entry['layout']
            assert not layout['page_horizontal_max'] and not layout['toolbar_outside'] and not layout['toolbar_overlaps']
            audit['captures'].append({**entry, 'file': folder + '/' + entry['file'], 'visually_reviewed': False})
    for start in range(0, len(audit['captures']), 8):
        entries = audit['captures'][start:start + 8]
        name = f'review-final-{start // 8 + 1:02}.jpg'
        assert not (ROOT / name).exists(), 'Do not overwrite review sheets'
        sheet = Image.new('RGB', (1280, ((len(entries) + 1) // 2) * 390), '#f2f5fa')
        draw = ImageDraw.Draw(sheet)
        for i, entry in enumerate(entries):
            x, y = (i % 2) * 640, (i // 2) * 390
            draw.text((x + 6, y + 5), entry['file'], fill='black')
            with Image.open(ROOT / entry['file']) as source:
                source.thumbnail((636, 358))
                sheet.paste(source, (x, y + 25))
            entry['review_sheet'] = name
        sheet.save(ROOT / name, quality=92)
        audit['review_sheets'].append({'file': name, 'sha256': digest(ROOT / name),
            'captures': [e['file'] for e in entries], 'visually_reviewed': False})
    (ROOT / 'audit.json').write_text(json.dumps(audit, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(f'Verified {len(audit["captures"])} hashes/dimensions/DPR/layouts; created {len(audit["review_sheets"])} sheets. Visual review pending.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--mark-reviewed', action='store_true')
    run(parser.parse_args().mark_reviewed)
