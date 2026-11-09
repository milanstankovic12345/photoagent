"""Extract a local candidate to NEW output, install offline, rehearse its runtime.

The existing base Python is still required: this is not a clean-OS acceptance test.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import stat
import subprocess
import sys
from zipfile import ZipFile


def verify(archive: Path, output: Path, *, offscreen: bool = False) -> None:
    output = output.absolute()
    output.mkdir(parents=True, exist_ok=False)
    bundle = output / 'bundle'
    with ZipFile(archive) as zipped:
        names = set()
        for info in zipped.infolist():
            path = PurePosixPath(info.filename)
            name = info.filename.casefold()
            if (path.is_absolute() or '..' in path.parts or '\\' in info.orig_filename
                    or '\x00' in info.orig_filename
                    or ':' in info.filename or name in names
                    or stat.S_ISLNK(info.external_attr >> 16)):
                raise ValueError(f'Unsafe or repeated ZIP entry: {info.filename}')
            names.add(name)
        zipped.extractall(bundle)
    env = os.environ.copy()
    for key in ('PYTHONPATH', 'PYTHONHOME', 'QT_PLUGIN_PATH', 'QT_QPA_PLATFORM_PLUGIN_PATH',
                'QT_SCALE_FACTOR', 'QT_QPA_PLATFORM'):
        env.pop(key, None)
    if offscreen:
        env['QT_QPA_PLATFORM'] = 'offscreen'
    with archive.open('rb') as stream:
        checksum = hashlib.file_digest(stream, 'sha256').hexdigest()
    report = {'archive': archive.name, 'sha256': checksum, 'status': 'running',
              'base_python': sys._base_executable, 'offscreen': offscreen}
    evidence = output / 'verification.json'
    evidence.write_text(json.dumps(report, indent=2), encoding='utf-8')
    runtime = bundle / '.runtime' / ('Scripts/python.exe' if os.name == 'nt' else 'bin/python')
    commands = (
        ('install', [sys._base_executable, '-X', 'utf8', '-E', '-s', '-B', str(bundle / 'install_offline.py')]),
        ('smoke', [str(runtime), '-X', 'utf8', '-E', '-s', '-B',
                   str(bundle / 'tools/release_smoke.py'), '--output', str(output / 'smoke-čćž')]),
    )
    for name, command in commands:
        with (output / f'{name}.log').open('wb') as log:
            result = subprocess.run(command, cwd=output, env=env, stdout=log, stderr=subprocess.STDOUT)
        if result.returncode:
            report.update(status='failed', failed_phase=name, returncode=result.returncode)
            evidence.write_text(json.dumps(report, indent=2), encoding='utf-8')
            raise RuntimeError(f'{name} failed; see {output / (name + ".log")}')
    launcher = ([os.environ.get('COMSPEC', 'cmd.exe'), '/d', '/c', 'start_offline.bat', '--help']
                if os.name == 'nt' else ['bash', 'start_offline.sh', '--help'])
    with (output / 'launcher.log').open('wb') as log:
        subprocess.run(launcher, cwd=bundle, env=env, stdout=log, stderr=subprocess.STDOUT, check=True)
    report['status'] = 'passed'
    evidence.write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(f'Installed candidate verification passed: {evidence}')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--archive', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--offscreen', action='store_true')
    args = parser.parse_args()
    verify(args.archive, args.output, offscreen=args.offscreen)
