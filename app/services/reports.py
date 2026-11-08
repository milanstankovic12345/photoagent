from __future__ import annotations

import csv
from datetime import datetime
from pathlib import Path
import uuid
from collections.abc import Iterable

from app.core.models import Match, Photo
from app.safety.paths import check_path


def pretty(p: Photo) -> str:
    return f"{p.width} x {p.height} | {p.size / 1048576:.1f} MB | {p.ext.upper()}"


def make_report(pairs: Iterable[Match], errors: Iterable[str], directory: Path) -> Path:
    check_path(directory, allow_missing=True).mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S") + "_" + uuid.uuid4().hex
    dest = directory / f"foto_izvestaj_{stamp}.csv"
    with dest.open("x", newline="", encoding="utf-8-sig") as stream:
        writer = csv.writer(stream, delimiter=";")
        writer.writerow(["TIP", "SACUVAJ", "SACUVAJ_INFO", "KOPIJA_ZA_PROVERU", "KOPIJA_INFO",
                         "PHASH_RAZLIKA", "DHASH_RAZLIKA", "RAW_UPOZORENJE"])
        for pair in pairs:
            writer.writerow([pair.kind.value, pair.keep.path, pretty(pair.keep), pair.dup.path,
                             pretty(pair.dup), pair.ph_distance, pair.dh_distance,
                             "DA" if pair.keep.is_raw or pair.dup.is_raw else "NE"])
    errors = iter(errors)
    first_error = next(errors, None)
    if first_error is not None:
        with (directory / f"greske_{stamp}.txt").open("x", encoding="utf-8") as stream:
            stream.write(first_error)
            for error in errors:
                stream.write('\n' + error)
    return dest
