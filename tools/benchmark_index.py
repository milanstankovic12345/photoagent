"""Reproducible synthetic-only benchmark. Never accepts an existing photo collection.

Run from the repository with its venv. Output directory must be new. Use --source
to measure a preserved pre-change source tree (containing app/) with --mode baseline.
The OS filesystem cache is not flushed. RSS is sampled every 20 ms, not an OS hard cap.
"""
from __future__ import annotations

import argparse
import ctypes
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import platform
from queue import Queue
import random
import shutil
import statistics
import sys
from threading import Event, Thread
import time


class DiscardUpdates(Queue):
    def put(self, *args, **kwargs):
        pass


def rss(pid: int) -> int:
    if os.name == 'nt':
        from ctypes import wintypes
        class Counters(ctypes.Structure):
            _fields_ = [('cb', wintypes.DWORD), ('faults', wintypes.DWORD)] + [
                (name, ctypes.c_size_t) for name in ('peak', 'working', 'a', 'b', 'c', 'd', 'e', 'f')]
        kernel = ctypes.WinDLL('kernel32', use_last_error=True)
        kernel.OpenProcess.restype = wintypes.HANDLE
        kernel.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
        kernel.CloseHandle.argtypes = [wintypes.HANDLE]
        handle = kernel.OpenProcess(0x0400 | 0x0010, False, pid)
        if not handle:
            return 0
        try:
            value = Counters()
            value.cb = ctypes.sizeof(value)
            fn = ctypes.WinDLL('psapi').GetProcessMemoryInfo
            fn.argtypes = [wintypes.HANDLE, ctypes.c_void_p, wintypes.DWORD]
            return value.working if fn(handle, ctypes.byref(value), value.cb) else 0
        finally:
            kernel.CloseHandle(handle)
    try:
        return int(Path(f'/proc/{pid}/statm').read_text().split()[1]) * os.sysconf('SC_PAGE_SIZE')
    except (OSError, IndexError, ValueError):
        return 0


def generate(root: Path, count: int, seed: int) -> None:
    from PIL import Image
    root.mkdir()
    randomizer = random.Random(seed)
    for start in range(0, count, 10):
        with Image.frombytes('RGB', (80, 60), randomizer.randbytes(80 * 60 * 3)) as image:
            for offset in range(min(10, count - start)):
                suffix = '.png' if offset < 4 else '.jpg' if offset < 7 else '.webp'
                path = root / f'{start + offset:06d}{suffix}'
                if offset in (1, 2, 3):
                    shutil.copy2(root / f'{start:06d}.png', path)
                elif offset in (5, 6):
                    shutil.copy2(root / f'{start + 4:06d}.jpg', path)
                elif offset >= 7:
                    with image.resize((40 + 4 * (offset - 7), 30 + 3 * (offset - 7))) as small:
                        small.save(path, quality=60 + offset)
                else:
                    image.save(path)


def pair_identity_digest(pairs) -> str:
    """Compare matching identities independent of each run's temporary root."""
    identities = sorted((pair.kind.value, Path(pair.keep.path).name,
                         Path(pair.dup.path).name) for pair in pairs)
    return hashlib.sha256(json.dumps(identities, ensure_ascii=False).encode()).hexdigest()


def run(args) -> None:
    source = args.source.resolve() if args.source else Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(source))
    from app.scanning import scanner, decoder
    from app.safety import paths
    os.environ['PYTHONDONTWRITEBYTECODE'] = '1'
    os.environ['OPENBLAS_NUM_THREADS'] = '1'
    os.environ['OMP_NUM_THREADS'] = '1'
    args.output.mkdir(parents=True, exist_ok=False)
    results = []
    counters = {'hash_reads': 0, 'hash_bytes': 0, 'decodes': 0}
    children = set()
    original_stream, original_popen = paths.snapshot_stream, decoder.subprocess.Popen

    def counted(stream, cancel=None):
        value = original_stream(stream, cancel)
        counters['hash_reads'] += 1
        counters['hash_bytes'] += value.size
        return value

    def popen(*a, **kw):
        process = original_popen(*a, **kw)
        counters['decodes'] += 1
        children.add(process.pid)
        return process

    paths.snapshot_stream = counted
    decoder.subprocess.Popen = popen
    stop = Event()
    peak = [0]

    def sample():
        while not stop.wait(.02):
            total = rss(os.getpid())
            for pid in tuple(children):
                memory = rss(pid)
                if not memory:
                    children.discard(pid)
                total += memory
            peak[0] = max(peak[0], total)

    monitor = Thread(target=sample, daemon=True)
    monitor.start()
    metadata = {'python': sys.version, 'platform': platform.platform(), 'cpu': platform.processor(),
                'seed': args.seed, 'source': str(source), 'mode': args.mode,
                'source_sha256': hashlib.sha256(b''.join(
                    str(p.relative_to(source)).encode() + p.read_bytes()
                    for p in sorted((source / 'app').rglob('*.py')))).hexdigest(),
                'collection': '80x60 seeded noise; PNG/JPEG copies; resized WebP; no RAW',
                'rss': 'sampled parent + live decoder RSS, 20ms; OS cache not flushed',
                'versions': {name: importlib.metadata.version(name) for name in ('Pillow', 'ImageHash', 'rawpy', 'pillow-heif', 'numpy', 'scipy')}}
    try:
        for size in args.sizes:
            for repetition in range(args.repeats):
                collection = args.output / f'photos-{size}-{repetition}'
                generate(collection, size, args.seed)
                service = None
                if args.mode == 'index':
                    from app.services.application import Application
                    service = Application(args.output / f'home-{size}-{repetition}')
                    service.initialize()
                try:
                    for scenario in (('baseline',) if service is None else ('cold', 'warm', 'changed')):
                        if scenario == 'changed':
                            from PIL import Image
                            with Image.new('RGB', (80, 60), '#217a99') as image:
                                image.save(collection / '000000.png')
                                image.save(collection / 'new.png')
                            (collection / '000001.png').rename(collection / 'renamed.png')
                            # Only benchmark-owned generated files, never a supplied collection.
                            (collection / '000002.png').unlink()
                        counters.update(dict.fromkeys(counters, 0))
                        peak[0] = rss(os.getpid())
                        start = time.perf_counter()
                        if service is None:
                            value = scanner.scan([str(collection)], DiscardUpdates(), Event())
                            measurements = {'photos': len(value.photos), 'pairs': len(value.pairs), 'complete': value.complete}
                        else:
                            value = service.scan([str(collection)], DiscardUpdates(), Event())
                            measurements = {'photos': value.photo_count, 'pairs': value.pair_count,
                                            'complete': value.complete, 'cache_hits': value.cache_hits,
                                            'scan_seconds': value.scan_seconds, 'match_seconds': value.match_seconds,
                                            'database_bytes': service.index.path.stat().st_size}
                        elapsed = time.perf_counter() - start
                        pair_source = value.pairs if service is None else service.index.iter_pairs(value.session_id)
                        measurements['pair_identity_sha256'] = pair_identity_digest(pair_source)
                        row = dict(size=size, repetition=repetition, scenario=scenario, seconds=elapsed,
                                   peak_rss=peak[0], **counters, **measurements)
                        results.append(row)
                        (args.output / 'results.json').write_text(json.dumps({'environment': metadata, 'runs': results}, indent=2))
                        print(json.dumps(row), flush=True)
                        if not measurements['complete']:
                            raise RuntimeError('benchmark scan incomplete')
                finally:
                    if service:
                        service.close()
        medians = []
        for size in args.sizes:
            for scenario in sorted({r['scenario'] for r in results}):
                rows = [r for r in results if r['size'] == size and r['scenario'] == scenario]
                medians.append({'size': size, 'scenario': scenario,
                                'seconds': statistics.median(r['seconds'] for r in rows),
                                'peak_rss': statistics.median(r['peak_rss'] for r in rows)})
        (args.output / 'results.json').write_text(json.dumps({'environment': metadata, 'runs': results, 'medians': medians}, indent=2))
    finally:
        stop.set()
        monitor.join()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--source', type=Path)
    parser.add_argument('--mode', choices=('baseline', 'index'), default='index')
    parser.add_argument('--sizes', type=int, nargs='+', default=[1000, 10000])
    parser.add_argument('--repeats', type=int, default=3)
    parser.add_argument('--seed', type=int, default=2202)
    options = parser.parse_args()
    if options.repeats < 1 or any(size < 10 for size in options.sizes):
        parser.error('repeats must be positive and sizes must be at least 10')
    run(options)
