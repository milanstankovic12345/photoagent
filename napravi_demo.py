"""Generate synthetic photographs only into a new, explicitly selected folder."""
from __future__ import annotations

import argparse
from pathlib import Path
import shutil

from PIL import Image, ImageDraw

from app.safety.paths import check_path


def create_demo(destination: Path) -> Path:
    folder = check_path(destination, allow_missing=True)
    folder.mkdir(parents=True, exist_ok=False)
    a, b, c = (folder / name for name in ("Disk_D_Originali", "Disk_E_Backup", "Disk_F_Manje"))
    for directory in (a, b, c):
        directory.mkdir()
    with Image.new("RGB", (1200, 800), "#a0c8eb") as image:
        draw = ImageDraw.Draw(image)
        for x in range(0, 1200, 12):
            draw.line((x, 0, 1199 - x // 3, 799),
                      fill=(30 + x // 12, 90 + x // 13, 110 + x // 20), width=3)
        draw.ellipse((250, 100, 850, 690), fill="#e8a54d", outline="#542d11", width=18)
        draw.rectangle((50, 600, 1100, 720), fill="#2b754e")
        image.save(a / "letovanje_original.png")
        image.save(b / "neko_drugo_ime.jpg", quality=92)
        shutil.copy2(b / "neko_drugo_ime.jpg", c / "fajl_123.jpg")
        with image.resize((450, 300)) as small:
            small.save(c / "manja_verzija.webp", quality=70)
    with Image.new("RGB", (800, 600), "#b0bbd5") as other:
        ImageDraw.Draw(other).rectangle((100, 100, 500, 500), fill="#b35040")
        other.save(a / "druga_fotografija.jpg")
    return folder


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("destination", type=Path)
    args = parser.parse_args()
    print(f"Demo fotografije: {create_demo(args.destination)}")


if __name__ == "__main__":
    main()
