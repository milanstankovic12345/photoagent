"""Native image libraries run only in a disposable, time-bounded child process."""
from __future__ import annotations

import base64
import io
import json
import os
from pathlib import Path
import subprocess
import sys
from threading import Event
import time
from typing import TYPE_CHECKING
import warnings

from app.core.models import SafetyError
from app.safety.paths import cancelled, check_path

if TYPE_CHECKING:
    from PIL import Image

RAWS = frozenset(".nef .nrw .cr2 .cr3 .crw .arw .srf .sr2 .dng .raf .orf .rw2 .pef .srw .3fr .erf .k25 .iiq .mos .mef .rwl".split())
IMAGES = frozenset(".jpg .jpeg .png .tif .tiff .bmp .webp .heic .heif .avif".split())
MAX_PIXELS = 100_000_000
TIMEOUT = 60.0


def _decode(path: str, *, preview: bool = True, preview_size: int = 880) -> dict:
    from app.scanning.fingerprints import perceptual
    from PIL import Image, ImageOps
    from pillow_heif import register_heif_opener

    register_heif_opener()
    Image.MAX_IMAGE_PIXELS = MAX_PIXELS
    warnings.simplefilter("error", Image.DecompressionBombWarning)

    def dimensions(w: int, h: int) -> None:
        if w <= 0 or h <= 0 or w * h > MAX_PIXELS:
            raise SafetyError("pixel_limit")

    if Path(path).suffix.lower() in RAWS:
        image_format = "RAW"
        import rawpy
        with rawpy.imread(path) as raw:
            w, h = int(raw.sizes.width), int(raw.sizes.height)
            dimensions(w, h)
            try:
                thumb = raw.extract_thumb()
                if thumb.format == rawpy.ThumbFormat.JPEG:
                    with Image.open(io.BytesIO(thumb.data)) as original:
                        dimensions(*original.size)
                        im = ImageOps.exif_transpose(original).copy()
                else:
                    dimensions(thumb.data.shape[1], thumb.data.shape[0])
                    im = Image.fromarray(thumb.data)
            except (rawpy.LibRawNoThumbnailError, rawpy.LibRawUnsupportedThumbnailError):
                im = Image.fromarray(raw.postprocess(half_size=True, output_bps=8))
    else:
        with Image.open(path) as original:
            image_format = original.format or "UNKNOWN"
            dimensions(*original.size)
            if getattr(original, "n_frames", 1) != 1:
                raise SafetyError("multiframe_review_required")
            im = ImageOps.exif_transpose(original).copy()
            w, h = im.size

    with im:
        with im.copy() as fingerprint:
            fingerprint.thumbnail((880, 880), Image.Resampling.LANCZOS)
            with fingerprint.convert('RGB') as rgb:
                phash, dhash = perceptual(rgb)
        im.thumbnail((preview_size, preview_size), Image.Resampling.LANCZOS)
        with im.convert("RGB") as rgb:
            result = {"width": w, "height": h, "phash": phash, "dhash": dhash,
                      "image_format": image_format}
            if preview:
                buffer = io.BytesIO()
                rgb.save(buffer, format="PNG")
                result["preview"] = base64.b64encode(buffer.getvalue()).decode("ascii")
    return result


def decode(path: str | Path, cancel: Event | None = None, *, timeout: float = TIMEOUT,
           preview: bool = True, preview_size: int = 880) -> dict:
    if type(preview_size) is not int or not 1 <= preview_size <= 2048:
        raise ValueError('invalid_preview_size')
    p = check_path(path)
    cancelled(cancel)
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    process = subprocess.Popen(
        [sys.executable, "-B", "-m", "app.scanning.decoder",
         "--worker" if preview else "--index-worker", str(p)] + ([str(preview_size)] if preview_size != 880 else []),
        stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        cwd=Path(__file__).resolve().parents[2], env=env,
        creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
    )
    deadline = time.monotonic() + timeout
    try:
        while True:
            cancelled(cancel)
            if time.monotonic() >= deadline:
                raise SafetyError("decoder_timeout")
            try:
                output, error = process.communicate(timeout=min(0.1, max(0.001, deadline - time.monotonic())))
                break
            except subprocess.TimeoutExpired:
                continue
        if process.returncode:
            raise SafetyError(f"decoder_failed: {error.decode('utf-8', errors='replace')[-1000:]}")
        try:
            result = json.loads(output)
            if not isinstance(result, dict):
                raise ValueError("not an object")
        except (ValueError, TypeError) as exc:
            raise SafetyError("decoder_invalid_response") from exc
        if "error" in result:
            raise SafetyError(result["error"])
        required = ("width", "height", "phash", "dhash") + (("preview",) if preview else ())
        if not all(key in result for key in required):
            raise SafetyError("decoder_invalid_response")
        return result
    finally:
        if process.poll() is None:
            process.kill()
        process.communicate()


def open_picture(path: str | Path, cancel: Event | None = None) -> tuple[Image.Image, int, int, bool]:
    from PIL import Image
    result = decode(path, cancel)
    with Image.open(io.BytesIO(base64.b64decode(result["preview"]))) as image:
        return image.copy(), result["width"], result["height"], Path(path).suffix.lower() in RAWS


if __name__ == "__main__":
    try:
        response = _decode(sys.argv[2], preview=sys.argv[1] != "--index-worker",
                           preview_size=int(sys.argv[3]) if len(sys.argv) > 3 else 880)
    except Exception as exc:
        response = {"error": f"{type(exc).__name__}: {exc}"}
    sys.stdout.buffer.write(json.dumps(response).encode("utf-8"))
