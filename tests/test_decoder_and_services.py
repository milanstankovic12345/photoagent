from dataclasses import replace
import importlib
from pathlib import Path
from queue import Queue
import sys
from threading import Event

from PIL import Image
import pytest

from app.core.models import Approval, Cancelled, SafetyError
from app.scanning.decoder import decode, open_picture
from app.scanning.scanner import scan
from app.services.reports import make_report


def test_preview_returns_bounded_bitmap(collection):
    picture, width, height, raw = open_picture(collection / "a.png")
    try:
        assert (width, height, raw) == (128, 96, False)
        assert max(picture.size) <= 880
    finally:
        picture.close()


def test_decoder_timeout_and_cancellation(collection):
    with pytest.raises(SafetyError, match="decoder_timeout"):
        decode(collection / "a.png", timeout=0.001)
    cancel = Event()
    cancel.set()
    with pytest.raises(Cancelled):
        decode(collection / "a.png", cancel)


def test_decoder_pixel_limit_without_allocating_huge_bitmap(tmp_path):
    import struct
    import zlib
    # A PNG header declares 100,010,000 pixels; no image data is allocated.
    header = struct.pack(">IIBBBBB", 10001, 10000, 8, 2, 0, 0, 0)
    chunk = b"IHDR" + header
    path = tmp_path / "huge.png"
    path.write_bytes(b"\x89PNG\r\n\x1a\n" + struct.pack(">I", len(header)) + chunk
                     + struct.pack(">I", zlib.crc32(chunk)) + b"\x00\x00\x00\x00IEND\xaeB`\x82")
    with pytest.raises(SafetyError, match="pixel_limit|DecompressionBomb"):
        decode(path)


def test_animated_image_rejected(tmp_path):
    path = tmp_path / "animated.webp"
    with Image.new("RGB", (16, 16), "red") as a, Image.new("RGB", (16, 16), "blue") as b:
        a.save(path, save_all=True, append_images=[b], duration=100, loop=0)
    with pytest.raises(SafetyError, match="multiframe_review_required"):
        decode(path)


def test_decoder_process_crash_is_reported(collection, monkeypatch):
    import app.scanning.decoder as decoder
    popen = decoder.subprocess.Popen

    def crash(args, **kwargs):
        return popen([sys.executable, "-B", "-c", "import os; os._exit(91)"], **kwargs)

    monkeypatch.setattr(decoder.subprocess, "Popen", crash)
    with pytest.raises(SafetyError, match="decoder_failed"):
        decode(collection / "a.png")


def test_invalid_decoder_response_is_explicit(collection, monkeypatch):
    import app.scanning.decoder as decoder
    popen = decoder.subprocess.Popen

    def invalid(args, **kwargs):
        return popen([sys.executable, "-B", "-c", "print('not JSON')"], **kwargs)

    monkeypatch.setattr(decoder.subprocess, "Popen", invalid)
    with pytest.raises(SafetyError, match="decoder_invalid_response"):
        decode(collection / "a.png")


def test_report_unique_exclusive_and_failure(scanned, tmp_path, monkeypatch):
    directory = tmp_path / "reports"
    one = make_report(scanned.pairs, ("synthetic failure",), directory)
    two = make_report(scanned.pairs, (), directory)
    assert one != two
    assert "EXACT" in one.read_text(encoding="utf-8-sig")
    assert len(list(directory.glob("greske_*.txt"))) == 1
    import app.services.reports as reports
    frozen = type("Fixed", (), {"hex": "fixed"})()
    monkeypatch.setattr(reports.uuid, "uuid4", lambda: frozen)
    instant = reports.datetime.now()
    monkeypatch.setattr(reports, "datetime", type("Clock", (), {"now": staticmethod(lambda: instant)}))
    three = make_report(scanned.pairs, (), directory)
    original = three.read_bytes()
    with pytest.raises(FileExistsError):
        make_report(scanned.pairs, (), directory)
    assert three.read_bytes() == original


def test_demo_import_is_inert_and_existing_destination_refused(tmp_path):
    import napravi_demo
    before = set(tmp_path.iterdir())
    importlib.reload(napravi_demo)
    assert set(tmp_path.iterdir()) == before
    destination = tmp_path / "demo"
    napravi_demo.create_demo(destination)
    original = (destination / "Disk_D_Originali" / "letovanje_original.png").read_bytes()
    with pytest.raises(FileExistsError):
        napravi_demo.create_demo(destination)
    assert (destination / "Disk_D_Originali" / "letovanje_original.png").read_bytes() == original


def test_exif_icc_bytes_survive_move_restore(tmp_path, operations):
    root = tmp_path / "metadata"
    root.mkdir()
    with Image.new("RGB", (32, 24), "green") as image:
        exif = Image.Exif()
        exif[0x010E] = "synthetic edit history"
        exif[0x0112] = 6
        image.save(root / "a.jpg", exif=exif, icc_profile=b"synthetic ICC payload")
    original = (root / "a.jpg").read_bytes()
    (root / "b.jpg").write_bytes(original)
    result = scan([str(root)], Queue(), Event())
    assert result.complete, result.errors
    from app.safety.operations import make_plan
    plan = make_plan(list(result.pairs))
    operations.execute(plan, Approval(plan))
    assert Path(plan.moves[0].destination).read_bytes() == original
    restore = operations.restore_plan()
    operations.execute(restore, Approval(restore))
    with Image.open(root / "b.jpg") as image:
        assert image.getexif()[0x010E] == "synthetic edit history"
        assert image.info["icc_profile"] == b"synthetic ICC payload"
    assert (root / "b.jpg").read_bytes() == original


def test_preflight_and_translation_fallback():
    from app.services.preflight import check
    check()
    from app.i18n import tr
    assert tr("scan_progress", 4, language="en") == "Inspected 4 photographs..."
    assert "4" in tr("scan_progress", 4, language="missing")
    assert tr("untranslated_key", language="en") == "untranslated_key"


@pytest.mark.raw_asset
@pytest.mark.skip(reason="No licensed valid RAW fixture is available; corrupt RAW is covered")
def test_valid_raw_asset():
    pass
