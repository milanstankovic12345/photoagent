"""Validate Task018 capture manifests and assemble contact sheets for inspection."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from PIL import Image, ImageDraw


def review(root: Path) -> None:
    report = {'validated': 0, 'sheets': [], 'visual_review': 'Requires opening the sheets/originals.'}
    for scale in ('100', '150'):
        folder = root / scale
        manifest = json.loads((folder / 'manifest.json').read_text(encoding='utf-8'))
        assert manifest['synthetic'] and len(manifest['captures']) == 33
        assert len({r['file'] for r in manifest['captures']}) == 33
        for row in manifest['captures']:
            path = folder / row['file']
            assert hashlib.sha256(path.read_bytes()).hexdigest() == row['sha256']
            with Image.open(path) as image:
                assert list(image.size) == row['physical']
            assert not any(row['layout'][key] for key in
                           ('toolbar_outside', 'toolbar_overlaps', 'page_horizontal_max'))
            report['validated'] += 1
        for state in ('empty', 'grid', 'list', 'filtered'):
            rows = [r for r in manifest['captures'] if r['file'].startswith(state + '-')]
            assert len(rows) == 8
            with Image.new('RGB', (1040, 1440), '#dadada') as sheet:
                draw = ImageDraw.Draw(sheet)
                for i, row in enumerate(rows):
                    x, y = (i % 2) * 520, (i // 2) * 360
                    draw.text((x + 5, y + 5), row['file'], fill='black')
                    with Image.open(folder / row['file']) as image:
                        image.thumbnail((510, 330))
                        sheet.paste(image, (x + 5, y + 25))
                path = folder / f'review-{state}.png'
                sheet.save(path)
                report['sheets'].append(str(path.relative_to(root)))
    (root / 'review.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    print(f'{report["validated"]} captures validated; {len(report["sheets"])} contact sheets for visual review')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, required=True)
    review(parser.parse_args().root)
