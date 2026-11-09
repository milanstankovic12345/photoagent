"""Verify capture integrity and build labeled contact sheets for visual review.

Only --mark-reviewed, AFTER opening the sheets, records a visual review. Producing
a contact sheet is not itself a review. Source captures are never overwritten.
"""
import argparse
import hashlib
import json
from pathlib import Path

from PIL import Image, ImageDraw


def run(directory: Path, mark_reviewed: bool = False) -> None:
    index = []
    for scale in ('100', '125', '150'):
        root = directory / scale
        path = root / 'manifest.json'
        manifest = json.loads(path.read_text(encoding='utf-8'))
        assert manifest['finished'] and manifest['synthetic']
        matrix = [entry for entry in manifest['captures'] if entry['matrix']]
        expected = {(w, theme, surface) for w in (1280, 1366, 1650, 1920)
                    for theme in ('dark', 'light')
                    for surface in ('dashboard', 'scan', 'duplicates', 'history', 'settings', 'compare')}
        actual = {(entry['target_physical'][0], entry['theme'], entry['state'].split('-')[-1]) for entry in matrix}
        assert actual == expected and len(matrix) == 48
        for entry in manifest['captures']:
            target = root / entry['file']
            assert hashlib.sha256(target.read_bytes()).hexdigest() == entry['sha256']
            assert abs(entry['dpr'] - int(scale) / 100) < .01
            assert all(abs(pixels - logical * entry['dpr']) <= 1 for pixels, logical
                       in zip(entry['pixel_size'], entry['logical_size']))
            assert entry['window_logical'] == [round(n / entry['dpr']) for n in entry['target_physical']]
            with Image.open(target) as captured:
                assert list(captured.size) == entry['pixel_size']
            layout = entry['layout']
            assert layout['page_horizontal_max'] == 0 and not layout['toolbar_outside'] and not layout['toolbar_overlaps']
        batches = [(f'matrix-{width}', [e for e in matrix if e['target_physical'][0] == width])
                   for width in (1280, 1366, 1650, 1920)]
        scenarios = [entry for entry in manifest['captures'] if not entry['matrix']]
        batches.extend((f'states-{i // 10 + 1}', scenarios[i:i + 10]) for i in range(0, len(scenarios), 10))
        for name, entries in batches:
            sheet_name = f'review-{name}.jpg'
            sheet_path = root / sheet_name
            if mark_reviewed:
                assert sheet_path.exists(), 'Open the generated contact sheets before recording review'
                for entry in entries:
                    entry['visually_reviewed'] = True
            else:
                assert not sheet_path.exists(), 'Use a new run directory; do not overwrite evidence'
                rows = (len(entries) + 1) // 2
                with Image.new('RGB', (1280, rows * 390), 'white') as sheet:
                    draw = ImageDraw.Draw(sheet)
                    for i, entry in enumerate(entries):
                        x, y = (i % 2) * 640, (i // 2) * 390
                        draw.text((x + 8, y + 5), f'{scale}% {entry["state"]}', fill='black')
                        with Image.open(root / entry['file']) as captured:
                            captured.thumbnail((640, 360))
                            sheet.paste(captured, (x, y + 25))
                    sheet.save(sheet_path, quality=90)
            index.append({'sheet': f'{scale}/{sheet_name}', 'captures': [entry['file'] for entry in entries],
                          'visually_reviewed': mark_reviewed})
        if mark_reviewed:
            path.write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf-8')
        print(f'{scale}%: {len(manifest["captures"])} capture hashes, DPR and layouts verified', flush=True)
    review_path = directory / 'review.json'
    if not mark_reviewed:
        assert not review_path.exists()
    review_path.write_text(json.dumps(index, indent=2) + '\n', encoding='utf-8')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directory', type=Path)
    parser.add_argument('--mark-reviewed', action='store_true')
    args = parser.parse_args()
    run(args.directory, args.mark_reviewed)
