"""Validate Task010 capture manifests and assemble review sheets of screenshots."""
import argparse
import hashlib
import json
from pathlib import Path

from PIL import Image, ImageDraw


def run(directory: Path) -> None:
    surfaces = ('dashboard', 'scan', 'duplicates', 'history', 'settings',
                'compare-selected', 'preview-details', 'confirmation',
                'consent-warnings', 'storage-error-details')
    for scale in ('100', '125', '150'):
        root = directory / scale
        manifest = json.loads((root / 'manifest.json').read_text(encoding='utf-8'))
        assert len(manifest['captures']) == 20
        for entry in manifest['captures']:
            target = root / entry['file']
            assert hashlib.sha256(target.read_bytes()).hexdigest() == entry['sha256']
            assert abs(entry['dpr'] - int(scale) / 100) < .01
            with Image.open(target) as captured:
                assert list(captured.size) == entry['pixel_size']
        for name, group in (('pages', surfaces[:5]), ('details', surfaces[5:])):
            sheet = Image.new('RGB', (1280, 1950), 'white')
            draw = ImageDraw.Draw(sheet)
            for row, surface in enumerate(group):
                for column, theme in enumerate(('dark', 'light')):
                    draw.text((column * 640 + 8, row * 390 + 5),
                              f'{scale}%  {theme}  {surface}', fill='black')
                    with Image.open(root / f'{theme}-{surface}.png') as captured:
                        captured.thumbnail((640, 360))
                        sheet.paste(captured, (column * 640, row * 390 + 25))
            sheet.save(root / f'review-{name}.png')
            sheet.close()
        print(f'{scale}%: 20 manifests verified, 2 review sheets created', flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('directory', type=Path)
    run(parser.parse_args().directory)
