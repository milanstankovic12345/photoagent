"""Build a local source + wheelhouse ZIP; never download or install anything.

The output is a release candidate, not a certification of platform or licensing gates.
"""
from __future__ import annotations

import argparse
from email.parser import BytesParser
import hashlib
import json
from pathlib import Path, PurePosixPath
import platform
import re
import sys
import sysconfig
from zipfile import ZIP_DEFLATED, ZipFile

ROOT = Path(__file__).resolve().parents[1]


def digest(path: Path) -> str:
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def normalized(name: str) -> str:
    return re.sub(r'[-_.]+', '-', name).lower()


def safe_file(path: Path, root: Path) -> None:
    path.relative_to(root)
    for part in (path, *path.parents):
        if part.is_symlink() or part.is_junction():
            raise ValueError(f'Redirected packaging input: {path}')
        if part == root:
            break
    if not path.is_file():
        raise ValueError(f'Not a regular file: {path}')


def wheel_inventory(wheelhouse: Path, lock: Path) -> list[dict]:
    expected = {}
    for line in lock.read_text(encoding='utf-8').splitlines():
        if not line.strip() or line.startswith('#'):
            continue
        match = re.fullmatch(r'([A-Za-z0-9_.-]+)==([A-Za-z0-9_.+!-]+)', line)
        if not match or normalized(match[1]) in expected:
            raise ValueError(f'Invalid or repeated lock entry: {line}')
        expected[normalized(match[1])] = match[2]
    rows = []
    for path in sorted(wheelhouse.glob('*.whl')):
        safe_file(path, wheelhouse)
        with ZipFile(path) as archive:
            metadata = [n for n in archive.namelist() if n.endswith('.dist-info/METADATA')]
            if len(metadata) != 1:
                raise ValueError(f'Invalid wheel metadata: {path.name}')
            info = BytesParser().parsebytes(archive.read(metadata[0]))
        name, version = info['Name'], info['Version']
        if expected.pop(normalized(name), None) != version:
            raise ValueError(f'Unexpected wheel/version: {path.name}')
        rows.append({'name': name, 'version': version, 'wheel': path.name,
                     'sha256': digest(path), 'requires': info.get_all('Requires-Dist', []),
                     'license_expression': info.get('License-Expression'),
                     'license_metadata': info.get('License'),
                     'license_files': info.get_all('License-File', [])})
    if expected or not rows:
        raise ValueError(f'Missing wheels: {sorted(expected)}')
    return rows


def build(wheelhouse: Path, lock: Path, output: Path, *, source: Path = ROOT) -> dict:
    source, wheelhouse = source.absolute(), wheelhouse.absolute()
    safe_file(lock.absolute(), source)
    rows = wheel_inventory(wheelhouse, lock)
    files: dict[str, bytes] = {}
    for path in sorted((source / 'app').rglob('*')):
        if path.is_file() and '__pycache__' not in path.parts and path.suffix in {
                '.py', '.json', '.svg', '.qrc', '.qss', '.ts', '.qm'}:
            safe_file(path, source)
            files[path.relative_to(source).as_posix()] = path.read_bytes()
    for relative in ('photo_agent.py', 'README.md', 'README_SR.md', 'requirements.txt',
                     'tools/release_smoke.py', 'tools/build_translations.py',
                     'docs/LOCALIZATION.md', 'docs/ARCHITECTURE.md',
                     'docs/SECURITY.md', 'docs/TESTING.md', 'docs/QT_DISTRIBUTION.md',
                     'docs/RELEASE.md', 'docs/CHANGELOG.md'):
        path = source / relative
        safe_file(path, source)
        files[relative] = path.read_bytes()
    for name in ('install_offline.py', 'start_offline.bat', 'start_offline.sh'):
        path = source / 'packaging' / name
        safe_file(path, source)
        files[name] = path.read_bytes()
    files['runtime-reference.txt'] = lock.read_bytes()
    requirements = [f"{r['name']}=={r['version']} --hash=sha256:{r['sha256']}" for r in rows]
    files['requirements-offline.txt'] = ('\n'.join(requirements) + '\n').encode()
    for row in rows:
        with ZipFile(wheelhouse / row['wheel']) as wheel:
            for member in wheel.namelist():
                parts = PurePosixPath(member)
                if parts.is_absolute() or '..' in parts.parts or '\\' in member or ':' in member:
                    raise ValueError(f'Unsafe wheel member: {member}')
                if not member.endswith('/') and (
                        any(part.lower() in ('license', 'licenses') for part in parts.parts)
                        or any(token in parts.name.lower() for token in
                               ('license', 'copying', 'notice', 'copyright'))):
                    files[f"notices/{row['name']}/{member}"] = wheel.read(member)
    manifest = {
        'format': 1, 'status': 'local-candidate-not-release-ready',
        'python': list(sys.version_info[:2]), 'platform': sysconfig.get_platform(),
        'build_python': platform.python_version(), 'build_os': platform.platform(),
        'dependencies': rows,
        'files': {name: hashlib.sha256(data).hexdigest() for name, data in files.items()},
        'open_gates': ['native Windows 10/11 and Linux matrix', 'valid RAW fixture',
                       'clean OS offline acceptance', 'physical DPI/accessibility',
                       '1k/10k performance budgets', 'distribution license and source obligations'],
    }
    manifest['files'].update({f"wheelhouse/{r['wheel']}": r['sha256'] for r in rows})
    # Exclusive creation preserves any previous artifact. A failed build is not a pass.
    output.parent.mkdir(parents=True, exist_ok=True)
    with ZipFile(output, 'x', compression=ZIP_DEFLATED) as archive:
        for name, data in sorted(files.items()):
            archive.writestr(name, data)
        for row in rows:
            archive.write(wheelhouse / row['wheel'], f"wheelhouse/{row['wheel']}")
        archive.writestr('release-manifest.json', json.dumps(manifest, indent=2, ensure_ascii=False))
    return manifest


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--wheelhouse', type=Path, required=True)
    parser.add_argument('--lock', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    build(args.wheelhouse, args.lock, args.output)
    print(f'Local candidate: {args.output}; SHA-256 {digest(args.output)}')
