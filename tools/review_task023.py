"""Validate final capture coverage and build contact sheets without asserting visual review.

The new review/ folder must not exist. Originals and capture manifests are read-only.
Open the generated sheets/originals before recording observations in the report.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from PIL import Image, ImageDraw


def review(root: Path) -> None:
    destination = root / 'review'
    destination.mkdir(exist_ok=False)
    report = {'validated': 0, 'sheets': [], 'visual_review': 'Pending human/agent image inspection',
              'note': 'Contact sheets are scaled review aids; original PNG dimensions remain authoritative.'}
    states = ('populated-dashboard', 'populated-scan', 'populated-duplicates',
              'compare-exact', 'quarantine-active', 'populated-settings')
    for scale, dpr in (('100', 1), ('150', 1.5)):
        directory = root / (scale + '-verified')
        manifest = json.loads((directory / 'manifest.json').read_text(encoding='utf-8'))
        assert manifest['finished'] and manifest['synthetic'] and manifest['original_bytes_restored']
        assert manifest['os_launches'] == 0
        captures = manifest['captures']
        assert len({row['file'] for row in captures}) == len(captures)
        for state in states:
            expected = {f'{state}-{lang}-{theme}-{sidebar}-{width}.png'
                for lang in ('en', 'sr_Latn') for theme in ('dark', 'light')
                for sidebar in ('compact', 'expanded') for width in (1280, 853)}
            assert expected <= {row['file'] for row in captures}, state
            for row in captures:
                if row['file'] in expected:
                    width = int(row['file'].rsplit('-', 1)[1].removesuffix('.png'))
                    assert row['logical'] == [width, 720 if width == 1280 else 480], row
        for row in captures:
            path = directory / row['file']
            assert hashlib.sha256(path.read_bytes()).hexdigest() == row['sha256']
            with Image.open(path) as shot:
                assert list(shot.size) == row['physical']
            assert row['dpr'] == dpr
            assert all(abs(p - logical * dpr) <= 1 for p, logical in zip(row['physical'], row['logical']))
            assert not any(row['layout'][key] for key in ('page_horizontal_max', 'toolbar_outside', 'toolbar_overlaps'))
            report['validated'] += 1
        for offset in range(0, len(captures), 8):
            rows = captures[offset:offset + 8]
            with Image.new('RGB', (960, 1168), '#dddddd') as sheet:
                draw = ImageDraw.Draw(sheet)
                for index, row in enumerate(rows):
                    x, y = index % 2 * 480, index // 2 * 292
                    draw.text((x + 5, y + 5), row['file'], fill='black')
                    with Image.open(directory / row['file']) as shot:
                        shot.thumbnail((470, 264))
                        sheet.paste(shot.convert('RGB'), (x + 5, y + 25))
                name = f'{scale}-{offset // 8 + 1:02}.jpg'
                sheet.save(destination / name, quality=90)
                report['sheets'].append({'file': name, 'captures': [f'{scale}-verified/{row["file"]}' for row in rows],
                                         'visually_reviewed': False})

    baseline = root.parent / 'task014-20261110' / 'baseline'
    mappings = [('dashboard', 'populated-dashboard'), ('scan', 'populated-scan'),
                ('duplicates', 'populated-duplicates'), ('compare', 'compare-exact'),
                ('history', 'quarantine-active'), ('settings', 'populated-settings')]
    report['comparisons'] = []
    for old_name, new_name in mappings:
        before = baseline / f'matrix-1280-dark-{old_name}.png'
        after = root / '100-verified' / f'{new_name}-en-dark-expanded-1280.png'
        with Image.new('RGB', (1280, 405), '#dddddd') as sheet:
            draw = ImageDraw.Draw(sheet)
            for x, path, label in ((0, before, 'Task014 baseline'), (640, after, 'Task023 current')):
                draw.text((x + 5, 5), label + ' / ' + old_name, fill='black')
                with Image.open(path) as shot:
                    assert shot.size == (1280, 720)
                    shot.thumbnail((630, 355))
                    sheet.paste(shot.convert('RGB'), (x + 5, 30))
            name = 'before-after-' + old_name + '.jpg'
            sheet.save(destination / name, quality=92)
            report['comparisons'].append({'file': name, 'before': str(before.relative_to(root.parent)),
                'after': str(after.relative_to(root)), 'visually_reviewed': False,
                'note': 'Same viewport/theme; synthetic sessions and some state/data differ. Not a pixel-diff test.'})
    (destination / 'index.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    print(f"{report['validated']} capture hashes/DPR/layouts validated; inspect review/ before accepting images")


def history_supplements(root: Path) -> None:
    """Preserve the initial captures/index, recording explicit loaded replacements."""
    index_path = root / 'review' / 'index.json'
    report = json.loads(index_path.read_text(encoding='utf-8'))
    assert 'history_supplements' not in report
    rows = []
    for scale, dpr in (('100', 1), ('150', 1.5)):
        directory = root / ('history-' + scale)
        manifest = json.loads((directory / 'manifest.json').read_text(encoding='utf-8'))
        assert manifest['finished'] and manifest['original_bytes_restored'] and manifest['synthetic']
        assert manifest['scope'] == 'loaded-history-supplement' and len(manifest['captures']) == 3
        for row in manifest['captures']:
            path = directory / row['file']
            assert hashlib.sha256(path.read_bytes()).hexdigest() == row['sha256']
            with Image.open(path) as shot:
                assert list(shot.size) == row['physical']
            assert row['dpr'] == dpr and row['logical'] == [1280, 720]
            assert not any(row['layout'][key] for key in ('page_horizontal_max', 'toolbar_outside', 'toolbar_overlaps'))
            rows.append({'file': str(path.relative_to(root)),
                'replaces': f'{scale}-verified/{row["file"]}', 'sha256': row['sha256'],
                'reason': 'Initial frame was captured before history preview settled', 'visually_reviewed': False})
    destination = root / 'review' / 'history-repairs.jpg'
    assert not destination.exists()
    with Image.new('RGB', (960, 876), '#dddddd') as sheet:
        draw = ImageDraw.Draw(sheet)
        for index, row in enumerate(rows):
            x, y = index % 2 * 480, index // 2 * 292
            draw.text((x + 5, y + 5), row['file'], fill='black')
            with Image.open(root / row['file']) as shot:
                shot.thumbnail((470, 264))
                sheet.paste(shot.convert('RGB'), (x + 5, y + 25))
        sheet.save(destination, quality=92)
    report['history_supplements'] = rows
    report['validated'] += len(rows)
    report['rejected_loading_frames'] = [row['replaces'] for row in rows]
    index_path.write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    print('Six loaded history replacements validated; inspect review/history-repairs.jpg')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--history-supplements-only', action='store_true')
    arguments = parser.parse_args()
    if arguments.history_supplements_only:
        history_supplements(arguments.root)
    else:
        review(arguments.root)
