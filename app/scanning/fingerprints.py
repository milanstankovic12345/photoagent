"""Perceptual fingerprints of an already decoded, oriented image."""
from PIL import Image


def perceptual(image: Image.Image) -> tuple[str, str]:
    import imagehash
    with image.copy() as small:
        small.thumbnail((320, 320), Image.Resampling.LANCZOS)
        return str(imagehash.phash(small)), str(imagehash.dhash(small))
