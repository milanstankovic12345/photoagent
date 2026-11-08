"""The original recommendation heuristic, separate from match detection."""
from app.core.models import Photo


def quality(p: Photo) -> tuple[int, int, int, int]:
    """Not a measurement of focus, noise, provenance, or editing value."""
    return (int(p.is_raw), p.width * p.height,
            {".png": 4, ".tiff": 3, ".tif": 3, ".bmp": 2}.get(p.ext, 0), p.size)
