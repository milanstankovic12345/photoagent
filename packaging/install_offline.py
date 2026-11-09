"""Verify a PhotoAgent source bundle and install only its hash-locked local wheels."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path, PurePosixPath
import subprocess
import sys
import sysconfig
import venv


def verify(root: Path) -> dict:
    manifest = json.loads((root / 'release-manifest.json').read_text(encoding='utf-8'))
    if manifest['format'] != 1:
        raise ValueError('Unsupported bundle format')
    if manifest['python'] != list(sys.version_info[:2]) or manifest['platform'] != sysconfig.get_platform():
        raise ValueError('Bundle requires its recorded Python version and platform')
    for name, expected in manifest['files'].items():
        relative = PurePosixPath(name)
        if relative.is_absolute() or '..' in relative.parts or '\\' in name or ':' in name:
            raise ValueError(f'Unsafe bundle path: {name}')
        path = root.joinpath(*relative.parts)
        for part in (path, *path.parents):
            if part.is_symlink() or part.is_junction():
                raise ValueError(f'Redirected bundle path: {name}')
            if part == root:
                break
        with path.open('rb') as stream:
            actual = hashlib.file_digest(stream, 'sha256').hexdigest()
        if actual != expected:
            raise ValueError(f'Bundle checksum mismatch: {name}')
    return manifest


def install(root: Path) -> None:
    verify(root)
    target = root / '.runtime'
    target.mkdir(exist_ok=False)  # Never replace an existing environment or user state.
    venv.EnvBuilder(with_pip=True, system_site_packages=False).create(target)
    python = target / ('Scripts/python.exe' if sys.platform == 'win32' else 'bin/python')
    subprocess.run([str(python), '-X', 'utf8', '-I', '-m', 'pip', '--isolated', '--disable-pip-version-check',
                    'install', '--no-index', '--no-cache-dir', '--only-binary=:all:', '--require-hashes',
                    '--find-links', str(root / 'wheelhouse'), '-r', str(root / 'requirements-offline.txt')],
                   cwd=root, check=True)
    subprocess.run([str(python), '-X', 'utf8', '-I', '-m', 'pip', '--isolated', 'check'], cwd=root, check=True)
    subprocess.run([str(python), '-X', 'utf8', '-E', '-s', '-B', '-m', 'app.services.preflight', '--ui', 'qt'],
                   cwd=root, check=True)


if __name__ == '__main__':
    install(Path(__file__).resolve().parent)
    print('Offline runtime installed. Use start_offline.bat or bash start_offline.sh.')
