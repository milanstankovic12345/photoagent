"""Measure hidden Tk heartbeat gaps during synthetic cold and warm scans.

The output directory must not exist. Only benchmark-generated images are scanned.
The worker's full-content reads are delayed by 50 ms; the UI ticks every 25 ms.
"""
from __future__ import annotations

import argparse
import importlib.metadata
import json
import platform
import threading
import time
import tkinter as tk
from pathlib import Path

from app.safety import paths
from app.ui.tk_app import PhotoApp
from tools.benchmark_index import generate


def pump(root: tk.Tk, predicate, *, timeout: float = 120.0) -> None:
    deadline = time.monotonic() + timeout
    while not predicate():
        if time.monotonic() > deadline:
            raise TimeoutError('Tk worker did not finish')
        root.update()
        time.sleep(0.005)
    root.update()


def run(output: Path, repeats: int, seed: int) -> None:
    output.mkdir(parents=True, exist_ok=False)
    metadata = {
        'python': platform.python_version(), 'platform': platform.platform(),
        'cpu': platform.processor(), 'seed': seed, 'images': 20,
        'tick_ms': 25, 'worker_read_delay_ms': 50,
        'versions': {name: importlib.metadata.version(name) for name in
                     ('Pillow', 'ImageHash', 'rawpy', 'pillow-heif', 'numpy', 'scipy')},
        'collection': '80x60 seeded noise; PNG/JPEG copies; resized WebP; no RAW',
    }
    results: list[dict] = []
    record_path = output / 'results.json'
    original = paths.snapshot_stream

    def delayed_read(stream, cancel=None):
        if threading.current_thread() is not threading.main_thread():
            time.sleep(0.050)
        return original(stream, cancel)

    paths.snapshot_stream = delayed_read
    root = tk.Tk()
    root.withdraw()
    try:
        for repetition in range(repeats):
            collection = output / f'photos-20-{repetition}'
            generate(collection, 20, seed + repetition)
            window = tk.Toplevel(root)
            window.withdraw()
            app = PhotoApp(window, home=output / f'home-20-{repetition}')
            try:
                pump(root, lambda: app.journal is not None and not app.busy)
                app.folder_list.insert('end', str(collection))
                for scenario in ('cold', 'warm'):
                    gaps: list[float] = []
                    active = [True]
                    start = time.perf_counter()
                    last = [start]

                    def tick(active=active, last=last, gaps=gaps) -> None:
                        now = time.perf_counter()
                        if active[0]:
                            gaps.append((now - last[0]) * 1000)
                            last[0] = now
                            root.after(25, tick)

                    root.after(25, tick)
                    app.start_scan()
                    pump(root, lambda: not app.busy)
                    end = time.perf_counter()
                    active[0] = False
                    gaps.append((end - last[0]) * 1000)
                    result = {
                        'repetition': repetition, 'scenario': scenario,
                        'seconds': end - start, 'heartbeat_gaps_ms': gaps,
                        'max_gap_ms': max(gaps), 'under_250_ms': max(gaps) < 250,
                        'complete': app.scan_complete,
                        'photos_on_first_page': len(app.photos),
                    }
                    results.append(result)
                    record_path.write_text(json.dumps({'environment': metadata, 'runs': results}, indent=2))
                    print(json.dumps({key: value for key, value in result.items()
                                      if key != 'heartbeat_gaps_ms'}), flush=True)
                    if not result['complete'] or result['photos_on_first_page'] != 20:
                        raise RuntimeError('benchmark scan incomplete')
            finally:
                app.close()
                pump(root, lambda: not app.futures and app._service_closing)
                app.executor.shutdown(wait=True)
    finally:
        paths.snapshot_stream = original
        root.destroy()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--repeats', type=int, default=3)
    parser.add_argument('--seed', type=int, default=2202)
    args = parser.parse_args()
    if args.repeats < 1:
        parser.error('repeats must be positive')
    run(args.output, args.repeats, args.seed)
