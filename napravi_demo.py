from pathlib import Path
import shutil
from pillow import Image, ImageDraw

folder = Path(__file__).resolve().parent / "demo_photo_collection"

a = folder / "Disk_D_Originali"
b = folder / "Disk_E_Backup"
c = folder / "Disk_F_Manje"

for d in (a, b, c):
    d.mkdir(parents=True, exist_ok=True)

# Pravimo probnu fotografiju
im = Image.new("RGB", (1200, 800), "#a0c8eb")
draw = ImageDraw.Draw(im)

for x in range(0, 1200, 12):
    draw.line(
        (x, 0, 1199 - x // 3, 799),
        fill=(30 + x // 12, 90 + x // 13, 110 + x // 20),
        width=3
    )

draw.ellipse(
    (250, 100, 850, 690),
    fill="#e8a54d",
    outline="#542d11",
    width=18
)

draw.rectangle(
    (50, 600, 1100, 720),
    fill="#2b754e"
)

# Original u PNG formatu
im.save(a / "letovanje_original.png")

# JPEG verzija iste fotografije
im.save(b / "neko_drugo_ime.jpg", quality=92)

# Potpuno identicna kopija JPEG-a
shutil.copy2(
    b / "neko_drugo_ime.jpg",
    c / "fajl_123.jpg"
)

# Manja i kompresovana verzija
im.resize((450, 300)).save(
    c / "manja_verzija.webp",
    quality=70
)

# Potpuno druga fotografija
other = Image.new("RGB", (800, 600), "#b0bbd5")
ImageDraw.Draw(other).rectangle(
    (100, 100, 500, 500),
    fill="#b35040"
)

other.save(a / "druga_fotografija.jpg")

print("Demo fotografije su napravljene!")
print(f"Lokacija: {folder}")
print("Identicne kopije: neko_drugo_ime.jpg i fajl_123.jpg")
print("Vizuelno slicne: PNG, JPG i WEBP varijante")