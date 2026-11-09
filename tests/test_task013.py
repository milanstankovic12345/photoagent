"""Packaging uses synthetic wheels and an isolated source tree, never user photos."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from zipfile import ZipFile

import pytest

from packaging import __version__ as _packaging_version  # dependency already in pytest
from tools.build_release import build, wheel_inventory
from tools.verify_release import verify as verify_archive
import importlib.util

INSTALLER = Path(__file__).resolve().parents[1] / 'packaging' / 'install_offline.py'
spec = importlib.util.spec_from_file_location('photoagent_offline_installer', INSTALLER)
installer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(installer)


@pytest.fixture
def bundle_inputs(tmp_path):
    source = tmp_path / 'source'
    source.mkdir()
    names = ['app/__init__.py', 'app/i18n/en.json', 'app/i18n/sr_Latn.json',
             'photo_agent.py', 'README.md', 'requirements.txt', 'tools/release_smoke.py',
             'docs/ARCHITECTURE.md', 'docs/SECURITY.md', 'docs/TESTING.md',
             'docs/QT_DISTRIBUTION.md', 'docs/RELEASE.md', 'docs/CHANGELOG.md',
             'packaging/install_offline.py', 'packaging/start_offline.bat', 'packaging/start_offline.sh']
    for name in names:
        path = source / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text('{}' if path.suffix == '.json' else '# synthetic', encoding='utf-8')
    for name in ('app/__pycache__/private.py', 'app/private.sqlite3', '.photo_agent_state.json',
                 'library/original.jpg', '.venv/secret.txt'):
        path = source / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b'never package')
    lock = source / 'runtime.txt'
    lock.write_text('Example==1.0\n', encoding='utf-8')
    wheels = tmp_path / 'wheels'
    wheels.mkdir()
    with ZipFile(wheels / 'example-1.0-py3-none-any.whl', 'x') as wheel:
        wheel.writestr('example-1.0.dist-info/METADATA', 'Name: Example\nVersion: 1.0\nLicense: MIT\n')
        wheel.writestr('example-1.0.dist-info/licenses/LICENSE', 'synthetic license')
        wheel.writestr('example-1.0.dist-info/licenses/THIRD_PARTY.txt', 'synthetic third party')
    return source, lock, wheels


def test_bundle_allowlist_hashes_notices_and_no_overwrite(bundle_inputs, tmp_path):
    source, lock, wheels = bundle_inputs
    output = tmp_path / 'candidate.zip'
    manifest = build(wheels, lock, output, source=source)
    before = output.read_bytes()
    with ZipFile(output) as archive:
        names = archive.namelist()
        assert 'app/i18n/en.json' in names and 'app/i18n/sr_Latn.json' in names
        assert not any('private' in n or 'secret' in n or 'original.jpg' in n for n in names)
        assert 'notices/Example/example-1.0.dist-info/licenses/LICENSE' in names
        assert 'notices/Example/example-1.0.dist-info/licenses/THIRD_PARTY.txt' in names
        for name, expected in manifest['files'].items():
            assert hashlib.sha256(archive.read(name)).hexdigest() == expected
        assert '--hash=sha256:' in archive.read('requirements-offline.txt').decode()
        assert 'not-release-ready' in manifest['status']
    with pytest.raises(FileExistsError):
        build(wheels, lock, output, source=source)
    assert output.read_bytes() == before


@pytest.mark.parametrize('entry', ['Example==2.0', 'Example==1.0\nMissing==1.0',
                                  'Example>=1', 'Example==1.0\nexample==1.0'])
def test_incomplete_or_invalid_lock_fails(bundle_inputs, entry):
    _, lock, wheels = bundle_inputs
    lock.write_text(entry, encoding='utf-8')
    with pytest.raises(ValueError):
        wheel_inventory(wheels, lock)


def test_offline_verification_refuses_tampering_and_existing_runtime(bundle_inputs, tmp_path):
    source, lock, wheels = bundle_inputs
    output = tmp_path / 'candidate.zip'
    build(wheels, lock, output, source=source)
    extracted = tmp_path / 'extracted'
    with ZipFile(output) as archive:
        archive.extractall(extracted)  # Only our synthetic builder-produced archive.
    installer.verify(extracted)
    (extracted / '.runtime').mkdir()
    sentinel = extracted / '.runtime' / 'preserve.txt'
    sentinel.write_bytes(b'existing runtime')
    with pytest.raises(FileExistsError):
        installer.install(extracted)
    assert sentinel.read_bytes() == b'existing runtime'
    (extracted / 'app/__init__.py').write_bytes(b'tampered')
    with pytest.raises(ValueError, match='checksum'):
        installer.verify(extracted)


@pytest.mark.parametrize('name', ['../outside.txt', '/absolute', 'C:/escape', 'app\\escape'])
def test_manifest_path_escape_rejected(tmp_path, name):
    import sys
    import sysconfig
    (tmp_path / 'release-manifest.json').write_text(json.dumps({
        'format': 1, 'python': list(sys.version_info[:2]), 'platform': sysconfig.get_platform(),
        'files': {name: '0' * 64}}), encoding='utf-8')
    with pytest.raises(ValueError, match='Unsafe'):
        installer.verify(tmp_path)


def test_redirected_source_rejected(bundle_inputs, tmp_path):
    source, lock, wheels = bundle_inputs
    target = tmp_path / 'external.py'
    target.write_bytes(b'outside source')
    link = source / 'app/link.py'
    try:
        link.symlink_to(target)
    except OSError as exc:
        pytest.skip(f'Symlink privilege unavailable: {exc}')
    with pytest.raises(ValueError, match='Redirected'):
        build(wheels, lock, tmp_path / 'candidate.zip', source=source)


@pytest.mark.parametrize('name', ['../escape', '/absolute', 'C:/escape', 'app\\escape'])
def test_archive_escape_refused_before_installation(tmp_path, name, monkeypatch):
    import subprocess
    monkeypatch.setattr(subprocess, 'run', lambda *a, **kw: pytest.fail('Installer must not start'))
    archive = tmp_path / 'bad.zip'
    with ZipFile(archive, 'x') as zipped:
        zipped.writestr(name, b'escape')
    if '\\' in name:
        # ZipInfo normalizes Windows separators when writing; restore an actual
        # malicious member name in both ZIP headers without changing byte lengths.
        archive.write_bytes(archive.read_bytes().replace(name.replace('\\', '/').encode(), name.encode()))
    with pytest.raises(ValueError, match='Unsafe'):
        verify_archive(archive, tmp_path / 'output')
