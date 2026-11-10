"""Validate editable Qt TS sources; build JSON fallback and embedded QM resources.

Run from the repository with Python -m tools.build_translations [--check].
Qt Linguist's lrelease and rcc are used locally, with no network or installation.
"""
from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path
import re
from string import Formatter
import subprocess
import sys
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
LANGUAGES = ('en', 'sr_Latn')


def placeholders(text: str) -> tuple[Counter, Counter]:
    return (Counter(field for _, field, _, _ in Formatter().parse(text) if field is not None),
            Counter(re.findall(r'%\d+', text)))


def read_source(path: Path, language: str) -> dict[str, str]:
    document = ET.parse(path).getroot()
    if document.tag != 'TS' or document.get('language') != language:
        raise ValueError(f'Invalid TS language: {path}')
    catalog: dict[str, str] = {}
    for context in document.findall('context'):
        if context.findtext('name') != 'PhotoAgent':
            raise ValueError(f'Unexpected translation context: {path}')
        for message in context.findall('message'):
            key = message.findtext('source', '')
            translation = message.find('translation')
            value = message.findtext('translation', '')
            if (not key or key in catalog or translation is None or list(translation)
                    or translation.get('type') or not value.strip()):
                raise ValueError(f'Missing, unfinished or duplicate translation: {path}: {key}')
            placeholders(value)  # Reject malformed Python format strings before release.
            catalog[key] = value
    if not catalog:
        raise ValueError(f'Empty translation source: {path}')
    return catalog


def source_catalogs(root: Path) -> dict[str, dict[str, str]]:
    catalogs = {language: read_source(root / f'{language}.ts', language) for language in LANGUAGES}
    en = catalogs['en']
    for language, catalog in catalogs.items():
        if set(catalog) != set(en):
            raise ValueError(f'Translation key mismatch: {language}')
        for key, text in catalog.items():
            if placeholders(text) != placeholders(en[key]):
                raise ValueError(f'Translation placeholder mismatch: {language}: {key}')
    return catalogs


def build(root: Path = ROOT / 'app/i18n', *, check: bool = False) -> dict[str, int]:
    catalogs = source_catalogs(root)
    if check:
        for language, catalog in catalogs.items():
            if json.loads((root / f'{language}.json').read_text(encoding='utf-8')) != catalog:
                raise ValueError(f'Stale JSON fallback: {language}; run tools.build_translations')
    else:
        # Call modules through this interpreter to avoid mismatched executable wrappers.
        for language, catalog in catalogs.items():
            (root / f'{language}.json').write_text(
                json.dumps(catalog, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
            subprocess.run([sys.executable, '-B', '-c',
                            'from PySide6.scripts.pyside_tool import lrelease; lrelease()',
                            str(root / f'{language}.ts'), '-qm', str(root / f'{language}.qm')], check=True)
        subprocess.run([sys.executable, '-B', '-c',
                        'from PySide6.scripts.pyside_tool import rcc; rcc()',
                        str(root / 'translations.qrc'), '-o', str(root / 'resources_rc.py')], check=True)
    return {language: len(catalog) for language, catalog in catalogs.items()}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true', help='Check TS/JSON parity without writing files or requiring Qt')
    args = parser.parse_args()
    for language, count in build(check=args.check).items():
        print(f'{language}: {count}/{count} translated; no unfinished entries')
