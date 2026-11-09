"""Synthetic packaged-runtime rehearsal. --output must be a NEW directory.

Run with the extracted bundle's .runtime Python. Only generated fixture files move.
Python socket audit events are denied in this process and its decoder children;
this is not an OS firewall or evidence of physical network disconnection.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
from threading import Event
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def require(condition: object, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def phase(name: str, work: Path) -> dict:
    require(Path(sys.prefix) == ROOT / '.runtime', 'Use the bundle .runtime interpreter')
    require(all('.venv' not in Path(p).parts for p in sys.path), 'Development venv leaked')
    from app.services.preflight import check
    check('qt')
    from importlib import import_module
    for module_name in ('PIL', 'imagehash', 'rawpy', 'pillow_heif', 'PySide6',
                        'numpy', 'scipy', 'pywt', 'shiboken6'):
        require(Path(import_module(module_name).__file__).is_relative_to(Path(sys.prefix)),
                f'Dependency outside installed runtime: {module_name}')
    home, photos = work / 'home', work / 'fotografije-čćž'
    if name == 'qt':
        from PySide6.QtCore import QSettings, qVersion
        from PySide6.QtTest import QTest
        from PySide6.QtWidgets import QApplication
        from app.ui.qt.window import MainWindow
        QSettings.setDefaultFormat(QSettings.IniFormat)
        for scope in (QSettings.UserScope, QSettings.SystemScope):
            QSettings.setPath(QSettings.IniFormat, scope, str(work / 'qt-settings'))
        qt = QApplication([])
        qt.setStyle('Fusion')
        window = MainWindow(home)
        window.show()

        def wait(predicate):
            deadline = time.monotonic() + 30
            while not predicate():
                require(time.monotonic() < deadline, 'Qt worker timeout')
                QTest.qWait(10)

        try:
            wait(lambda: window.settings and not window.controller.busy)
            for language in ('en', 'sr_Latn'):
                window.apply_language(language)
                from app.ui.qt.localization import current_language
                require(current_language() == language, 'Language did not switch')
                for theme in ('dark', 'light', 'system'):
                    window.set_theme(theme)
                    wait(lambda: not window.controller.busy)
                    require(window.theme.preference == theme, 'Theme did not switch')
            require(window.grab().save(str(work / 'qt.png')), 'Qt capture failed')
            return {'qt': qVersion(), 'platform_plugin': qt.platformName(),
                    'window_visible': window.isVisible()}
        finally:
            window.close()
            wait(lambda: window.finished)
    from app.services.application import Application
    from app.core.models import Approval, SafetyError
    service = Application(home)
    try:
        journal, settings, issues = service.initialize()
        require(journal.writable and not issues, f'Initialization: {issues}')
        if name == 'scan':
            from app.scanning.decoder import decode
            from app.i18n import STRINGS
            require(set(STRINGS['en']) == set(STRINGS['sr_Latn']), 'Catalog mismatch')
            cold = service.scan([str(photos)], None, Event())
            require(cold.complete and cold.photo_count == 4, 'Cold scan failed')
            import app.scanning.decoder as decoder
            original = decoder.subprocess.Popen
            decodes = []

            def counted(*args, **kwargs):
                decodes.append(1)
                return original(*args, **kwargs)

            decoder.subprocess.Popen = counted
            try:
                warm = service.scan([str(photos)], None, Event())
            finally:
                decoder.subprocess.Popen = original
            require(warm.complete and not decodes and warm.cache_hits == 4, 'Warm cache failure')
            malformed = work / 'malformed.nef'
            malformed.write_bytes(b'synthetic invalid RAW')
            try:
                decode(malformed)
            except SafetyError:
                pass
            else:
                raise RuntimeError('Malformed RAW unexpectedly decoded')
            service.update_settings({'language': 'sr_Latn', 'theme': 'light'})
            return {'photos': cold.photo_count, 'pairs': cold.pair_count,
                    'warm_decodes': len(decodes), 'warm_cache_hits': warm.cache_hits,
                    'malformed_raw': 'rejected'}
        if name == 'interrupt':
            require(settings['language'] == 'sr_Latn' and settings['theme'] == 'light', 'Settings restart')
            result = service.scan([str(photos)], None, Event())
            plan = service.prepare_session(result.session_id, Event())
            require(len(plan.moves) == 1, 'Expected one synthetic EXACT move')
            move = plan.moves[0]
            from dataclasses import replace
            try:
                service.execute(plan, Approval(replace(plan, id='unapproved-plan')), Event())
            except SafetyError:
                pass
            else:
                raise RuntimeError('Mismatched approval accepted')
            require(Path(move.source).exists() and not Path(move.destination).exists(),
                    'Denied approval moved a file')
            (work / 'move.json').write_text(json.dumps({'source': move.source,
                 'keeper': move.keeper.path, 'destination': move.destination}), encoding='utf-8')
            # Crash after native movement, before journal completion. No rollback.
            service.journal.transition = lambda *args, **kwargs: os._exit(73)
            service.execute(plan, Approval(plan), Event())
            raise RuntimeError('Crash injection was not reached')
        if name == 'restore':
            move = json.loads((work / 'move.json').read_text(encoding='utf-8'))
            source, keeper, destination = (Path(move[k]) for k in ('source', 'keeper', 'destination'))
            require(not source.exists() and destination.exists(), 'Interrupted move was lost')
            require(journal.records()[0]['state'] == 'complete', 'Restart did not reconcile intent')
            source.write_bytes(b'synthetic occupied restore destination')
            try:
                service.restore_plan(Event())
            except SafetyError:
                pass
            else:
                raise RuntimeError('Occupied restore destination accepted')
            require(source.read_bytes() == b'synthetic occupied restore destination', 'Conflict overwritten')
            source.unlink()  # This exact file was generated immediately above.
            plan = service.restore_plan(Event())
            service.execute(plan, Approval(plan), Event())
            require(source.read_bytes() == keeper.read_bytes(), 'Restored bytes differ')
            require(not destination.exists() and len(journal.records()) == 2, 'Restore history missing')
            return {'restart_recovery': 'complete', 'restore_conflict': 'preserved', 'restore': 'complete'}
        raise ValueError(name)
    finally:
        service.close()


def run(output: Path) -> None:
    output = output.absolute()
    output.mkdir(parents=True, exist_ok=False)
    (output / 'home').mkdir()
    guard = output / 'guard'
    guard.mkdir()
    (guard / 'sitecustomize.py').write_text(
        "import sys\ndef deny(event, args):\n"
        "    if event in ('socket.connect', 'socket.connect_ex', 'socket.getaddrinfo', 'socket.bind', 'socket.sendto'):\n"
        "        raise RuntimeError('release smoke network denied: ' + event)\n"
        "sys.addaudithook(deny)\n", encoding='utf-8')
    env = os.environ.copy()
    for key in ('HOME', 'USERPROFILE', 'TMP', 'TEMP', 'TMPDIR'):
        env[key] = str(output / 'home')
    env['PYTHONPATH'] = os.pathsep.join((str(guard), str(ROOT)))
    env['PYTHONNOUSERSITE'] = '1'
    env.pop('PYTHONHOME', None)
    env['PYTHONDONTWRITEBYTECODE'] = '1'
    # Generate a tiny, deterministic collection; never accept an external library.
    from PIL import Image, ImageDraw
    photos = output / 'fotografije-čćž'
    photos.mkdir()
    with Image.new('RGB', (128, 96), '#b4c8e0') as image:
        draw = ImageDraw.Draw(image)
        draw.rectangle((7, 9, 72, 65), fill='red')
        draw.ellipse((62, 37, 119, 92), fill='green')
        image.save(photos / 'a.png')
        (photos / 'b.png').write_bytes((photos / 'a.png').read_bytes())
        image.save(photos / 'c.jpg')
        image.save(photos / 'd.webp')
    before = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in photos.iterdir()}
    results = {'python': platform.python_version(), 'platform': platform.platform(),
               'runtime': str(sys.prefix), 'phases': {}, 'status': 'running',
               'network': 'Python socket audit denial; no OS-level disconnection claim'}
    report = output / 'results.json'
    report.write_text(json.dumps(results, indent=2), encoding='utf-8')
    for name in ('scan', 'interrupt', 'restore', 'qt'):
        completed = subprocess.run([sys.executable, '-X', 'utf8', '-B', str(Path(__file__).resolve()),
            '--phase', name, '--output', str(output)], cwd=output, env=env,
            capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=180)
        (output / f'{name}.log').write_text(completed.stdout + completed.stderr, encoding='utf-8')
        require(completed.returncode == (73 if name == 'interrupt' else 0),
                f'{name} failed ({completed.returncode}); see {output / (name + ".log")}')
        results['phases'][name] = {'returncode': completed.returncode}
        report.write_text(json.dumps(results, indent=2), encoding='utf-8')
    require(before == {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                       for p in photos.iterdir() if p.is_file()},
            'Synthetic original collection changed')
    results['original_hashes'] = before
    results['status'] = 'passed'
    report.write_text(json.dumps(results, indent=2), encoding='utf-8')
    print(f'Synthetic packaged rehearsal passed: {report}')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--phase', choices=('scan', 'interrupt', 'restore', 'qt'))
    args = parser.parse_args()
    if args.phase:
        print(json.dumps(phase(args.phase, args.output), ensure_ascii=False))
    else:
        run(args.output)
