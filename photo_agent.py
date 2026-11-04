
"""PhotoAgent - lokalno pronalazenje dupliranih fotografija."""

from __future__ import annotations

import csv
import hashlib
import io
import json
import os
import queue
import sys
import threading
import uuid

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog, ttk

import imagehash
from PIL import Image, ImageOps, ImageTk
import rawpy

try:
    from pillow_heif import register_heif_opener
    register_heif_opener()
except ImportError:
    pass


# ============================================================
# PODESAVANJA
# ============================================================

RAWS = {
    ".nef", ".nrw", ".cr2", ".cr3", ".crw",
    ".arw", ".srf", ".sr2", ".dng", ".raf",
    ".orf", ".rw2", ".pef", ".srw", ".3fr",
    ".erf", ".k25", ".iiq", ".mos", ".mef", ".rwl"
}

IMAGES = {
    ".jpg", ".jpeg", ".png", ".tif", ".tiff",
    ".bmp", ".webp", ".heic", ".heif", ".avif"
}

SKIP_DIRS = {
    ".photo_agent_quarantine",
    "$recycle.bin",
    "system volume information",
    ".git",
    "__pycache__",
    "windows",
    "program files",
    "program files (x86)"
}

STATE = Path.home() / ".photo_agent_state.json"
REPORTS = Path.home() / "PhotoAgentReports"

PHASH_MAX = 4
DHASH_MAX = 6
ASPECT_MAX = 0.025

CHUNK = 1024 * 1024


# ============================================================
# MODEL FOTOGRAFIJE
# ============================================================

@dataclass
class Photo:
    path: str
    root: str
    size: int
    mtime_ns: int
    width: int
    height: int
    phash: str
    dhash: str
    is_raw: bool
    ext: str
    sha256: str = ""


# ============================================================
# CUVANJE PODESAVANJA
# ============================================================

def load_state():
    try:
        value = json.loads(
            STATE.read_text(encoding="utf-8")
        )
        if isinstance(value, dict):
            return {
                "roots": value.get("roots", []),
                "moves": value.get("moves", [])
            }
    except (OSError, ValueError):
        pass

    return {
        "roots": [],
        "moves": []
    }


def save_state(value):
    tmp = STATE.with_name(STATE.name + ".tmp")

    tmp.write_text(
        json.dumps(value, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )

    tmp.replace(STATE)


# ============================================================
# SHA-256 - POTPUNO IDENTICNI FAJLOVI
# ============================================================

def file_sha(path):
    digest = hashlib.sha256()

    with open(path, "rb") as f:
        while True:
            piece = f.read(CHUNK)

            if not piece:
                break

            digest.update(piece)

    return digest.hexdigest()


# ============================================================
# OTVARANJE STANDARDNIH I RAW FOTOGRAFIJA
# ============================================================

def open_picture(path):
    """
    Vraca:
    (slika_za_pregled, sirina, visina, jeste_raw)
    """

    path = Path(path)

    is_raw = path.suffix.lower() in RAWS

    if is_raw:
        with rawpy.imread(str(path)) as raw:

            w = raw.sizes.width
            h = raw.sizes.height

            try:
                thumb = raw.extract_thumb()

                if thumb.format == rawpy.ThumbFormat.JPEG:
                    with Image.open(io.BytesIO(thumb.data)) as original:
                        im = original.copy()
                else:
                    im = Image.fromarray(thumb.data)

            except (
                rawpy.LibRawNoThumbnailError,
                rawpy.LibRawUnsupportedThumbnailError
            ):
                im = Image.fromarray(
                    raw.postprocess(
                        half_size=True,
                        output_bps=8
                    )
                )

        im = ImageOps.exif_transpose(im)

        return im, int(w), int(h), True

    with Image.open(path) as img:

        if getattr(img, "n_frames", 1) > 1:
            raise ValueError(
                "Animirana ili multiframe slika: rucna provera"
            )

        im = ImageOps.exif_transpose(img)

        w, h = im.size

        im = im.copy()

    return im, w, h, False


# ============================================================
# ANALIZA JEDNE FOTOGRAFIJE
# ============================================================

def inspect(path, root):
    st = path.stat()

    im, w, h, is_raw = open_picture(path)

    try:
        im.thumbnail(
            (320, 320),
            Image.Resampling.LANCZOS
        )

        rgb = im.convert("RGB")

        phash = str(imagehash.phash(rgb))
        dhash = str(imagehash.dhash(rgb))

        rgb.close()

        return Photo(
            path=str(path),
            root=str(root),
            size=st.st_size,
            mtime_ns=st.st_mtime_ns,
            width=w,
            height=h,
            phash=phash,
            dhash=dhash,
            is_raw=is_raw,
            ext=path.suffix.lower()
        )

    finally:
        im.close()


# ============================================================
# PROCENA KVALITETA
# ============================================================

def quality(p):
    """
    Heuristicka preporuka.
    Ne meri stvarnu ostrinu niti kvalitet RAW obrade.
    """

    lossless = {
        ".png": 4,
        ".tiff": 3,
        ".tif": 3,
        ".bmp": 2
    }

    return (
        int(p.is_raw),
        p.width * p.height,
        lossless.get(p.ext, 0),
        p.size,
        p.path.casefold()
    )


def aspect(p):
    return max(p.width, p.height) / max(
        1, min(p.width, p.height)
    )


def hamming_int(x, y):
    return (x ^ y).bit_count()


# ============================================================
# BK TREE - BRZA PRETRAGA SLICNIH HESEVA
# ============================================================

class BKTree:

    def __init__(self):
        self.node = None

    def add(self, h, photo):

        if self.node is None:
            self.node = [h, [photo], {}]
            return

        node = self.node

        while True:

            dist = hamming_int(h, node[0])

            if dist == 0:
                node[1].append(photo)
                return

            if dist not in node[2]:
                node[2][dist] = [h, [photo], {}]
                return

            node = node[2][dist]

    def near(self, h, radius):

        if self.node is None:
            return []

        results = []
        stack = [self.node]

        while stack:

            node = stack.pop()

            dist = hamming_int(h, node[0])

            if dist <= radius:
                results.extend(
                    (dist, p) for p in node[1]
                )

            stack.extend(
                child
                for edge, child in node[2].items()
                if dist - radius <= edge <= dist + radius
            )

        return results


# ============================================================
# VALIDACIJA FOLDERA
# ============================================================

def roots_for_scan(folders):

    resolved = []

    for folder in folders:

        root = Path(folder).expanduser().resolve()

        if (
            root.is_dir()
            and not root.is_symlink()
            and root not in resolved
        ):
            resolved.append(root)

    return [
        r for r in resolved
        if not any(
            other != r and other in r.parents
            for other in resolved
        )
    ]


# ============================================================
# SKENIRANJE FOTOGRAFIJA
# ============================================================

def scan(folders, updates, cancel):

    roots = roots_for_scan(folders)

    found = []
    errors = []
    seen = set()

    def walk_error(err):
        errors.append(
            f"Nije moguce pristupiti folderu: {err}"
        )

    # 1. Pronalazenje i analiza fotografija

    for root in roots:

        if root.name.lower() == ".photo_agent_quarantine":
            errors.append(
                f"Preskacem karantin: {root}"
            )
            continue

        for dirpath, dirnames, filenames in os.walk(
            root,
            followlinks=False,
            onerror=walk_error
        ):

            if cancel.is_set():
                return None

            dirnames[:] = [
                d for d in dirnames
                if d.lower() not in SKIP_DIRS
                and not (Path(dirpath) / d).is_symlink()
            ]

            for filename in filenames:

                if cancel.is_set():
                    return None

                path = Path(dirpath) / filename

                if path.suffix.lower() not in IMAGES | RAWS:
                    continue

                if path.is_symlink():
                    continue

                key = os.path.normcase(str(path.absolute()))

                if key in seen:
                    continue

                seen.add(key)

                try:
                    found.append(
                        inspect(path, root)
                    )

                except Exception as exc:

                    errors.append(
                        f"{path}: "
                        f"{type(exc).__name__}: {exc}"
                    )

                    # Cak i RAW bez pregleda moze imati
                    # potpuno identicnu kopiju.

                    try:
                        st = path.stat()

                        found.append(
                            Photo(
                                path=str(path),
                                root=str(root),
                                size=st.st_size,
                                mtime_ns=st.st_mtime_ns,
                                width=0,
                                height=0,
                                phash="",
                                dhash="",
                                is_raw=path.suffix.lower() in RAWS,
                                ext=path.suffix.lower()
                            )
                        )

                    except OSError as stat_exc:
                        errors.append(
                            f"{path}: {stat_exc}"
                        )

                if len(seen) % 25 == 0:
                    updates.put(
                        (
                            "status",
                            f"Analizirano {len(seen)} fotografija..."
                        )
                    )

    # 2. Grupisanje prema velicini

    updates.put(
        (
            "status",
            "Racunanje SHA-256 za fajlove iste velicine..."
        )
    )

    by_size = {}

    for photo in found:
        by_size.setdefault(
            photo.size, []
        ).append(photo)

    by_sha = {}

    for size, group in by_size.items():

        if cancel.is_set():
            return None

        if len(group) < 2:
            continue

        for photo in group:

            try:
                photo.sha256 = file_sha(photo.path)

                by_sha.setdefault(
                    (size, photo.sha256), []
                ).append(photo)

            except OSError as exc:
                errors.append(
                    f"SHA-256 {photo.path}: {exc}"
                )

    # 3. Identicni fajlovi

    pairs = []
    exact_duplicates = set()

    root_rank = {
        str(r): i
        for i, r in enumerate(roots)
    }

    def visual_quality(p):
        return (
            *quality(p)[:-1],
            -root_rank.get(p.root, 999),
            p.path.casefold()
        )

    for group in by_sha.values():

        if len(group) < 2:
            continue

        group.sort(
            key=lambda p: (
                root_rank.get(p.root, 999),
                p.path.casefold()
            )
        )

        keeper = group[0]

        for dup in group[1:]:

            exact_duplicates.add(dup.path)

            pairs.append(
                {
                    "kind": "IDENTICAN",
                    "keep": keeper,
                    "dup": dup,
                    "ph_distance": 0,
                    "dh_distance": 0
                }
            )

    # 4. Vizuelno slicne fotografije

    updates.put(
        (
            "status",
            "Pretraga vizuelno slicnih fotografija..."
        )
    )

    tree = BKTree()

    photos_for_comparison = sorted(
        (
            p for p in found
            if p.path not in exact_duplicates
            and p.phash
        ),
        key=visual_quality,
        reverse=True
    )

    for photo in photos_for_comparison:

        if cancel.is_set():
            return None

        h = int(photo.phash, 16)

        candidates = []

        for pdist, master in tree.near(h, PHASH_MAX):

            ddist = hamming_int(
                int(photo.dhash, 16),
                int(master.dhash, 16)
            )

            adiff = (
                abs(aspect(photo) - aspect(master))
                / max(aspect(photo), aspect(master))
            )

            if (
                ddist <= DHASH_MAX
                and adiff <= ASPECT_MAX
            ):
                candidates.append(
                    (pdist, ddist, master)
                )

        if candidates:

            pdist, ddist, master = min(
                candidates,
                key=lambda t: (t[0], t[1])
            )

            pairs.append(
                {
                    "kind": "SLICAN",
                    "keep": master,
                    "dup": photo,
                    "ph_distance": pdist,
                    "dh_distance": ddist
                }
            )

        else:
            tree.add(h, photo)

    pairs.sort(
        key=lambda pair: (
            pair["kind"] != "IDENTICAN",
            pair["dup"].path.casefold()
        )
    )

    return found, pairs, errors


# ============================================================
# PROVERA PRE PREMESTANJA
# ============================================================

def verify_and_move(pair):

    src = pair["dup"]
    master = pair["keep"]

    src_path = Path(src.path)
    master_path = Path(master.path)

    if src_path.is_symlink() or master_path.is_symlink():
        raise ValueError(
            "Simbolicki linkovi nisu dozvoljeni"
        )

    if (
        not src_path.is_file()
        or not master_path.is_file()
    ):
        raise FileNotFoundError(
            "Izvor ili preporuceni original ne postoji"
        )

    # Proveravamo da fajlovi nisu menjani.

    for photo, path in (
        (src, src_path),
        (master, master_path)
    ):

        st = path.stat()

        if (
            st.st_size != photo.size
            or st.st_mtime_ns != photo.mtime_ns
        ):
            raise ValueError(
                f"Fajl je promenjen nakon skeniranja: {path}"
            )

    # Za identicne proveravamo SHA-256 ponovo.

    if pair["kind"] == "IDENTICAN":

        if file_sha(src_path) != file_sha(master_path):
            raise ValueError(
                "SHA-256 nije isti. Ponovi skeniranje."
            )

    # Za slicne proveravamo perceptual hash.

    else:

        a = inspect(src_path, src.root)
        b = inspect(master_path, master.root)

        pdist = hamming_int(
            int(a.phash, 16),
            int(b.phash, 16)
        )

        ddist = hamming_int(
            int(a.dhash, 16),
            int(b.dhash, 16)
        )

        adiff = (
            abs(aspect(a) - aspect(b))
            / max(aspect(a), aspect(b))
        )

        if (
            pdist > PHASH_MAX
            or ddist > DHASH_MAX
            or adiff > ASPECT_MAX
        ):
            raise ValueError(
                "Fotografije vise ne odgovaraju. "
                "Ponovi skeniranje."
            )

    # Bezbednosna provera odabranog foldera.

    root = Path(src.root)

    if not src_path.resolve().is_relative_to(
        root.resolve()
    ):
        raise ValueError(
            "Fajl nije unutar dozvoljenog foldera"
        )

    # Karantin ostaje na istom izvornom disku.

    target_dir = (
        root
        / ".photo_agent_quarantine"
        / datetime.now().strftime("%Y-%m-%d")
    )

    target_dir.mkdir(
        parents=True,
        exist_ok=True
    )

    target = target_dir / (
        f"{uuid.uuid4().hex}_{src_path.name}"
    )

    src_path.rename(target)

    return {
        "origin": str(src_path),
        "dest": str(target),
        "keep": master.path,
        "kind": pair["kind"],
        "date": datetime.now().isoformat(
            timespec="seconds"
        )
    }


# ============================================================
# IZVESTAJI
# ============================================================

def pretty(p):

    return (
        f"{p.width} x {p.height} | "
        f"{p.size / 1048576:.1f} MB | "
        f"{p.ext.upper()}"
    )


def make_report(pairs, errors):

    REPORTS.mkdir(
        parents=True,
        exist_ok=True
    )

    stamp = datetime.now().strftime(
        "%Y%m%d_%H%M%S"
    )

    dest = REPORTS / (
        f"foto_izvestaj_{stamp}.csv"
    )

    with dest.open(
        "w",
        newline="",
        encoding="utf-8-sig"
    ) as f:

        writer = csv.writer(
            f,
            delimiter=";"
        )

        writer.writerow(
            [
                "TIP",
                "SACUVAJ",
                "SACUVAJ_INFO",
                "KOPIJA_ZA_PROVERU",
                "KOPIJA_INFO",
                "PHASH_RAZLIKA",
                "DHASH_RAZLIKA",
                "RAW_UPOZORENJE"
            ]
        )

        for pair in pairs:

            master = pair["keep"]
            dup = pair["dup"]

            writer.writerow(
                [
                    pair["kind"],
                    master.path,
                    pretty(master),
                    dup.path,
                    pretty(dup),
                    pair["ph_distance"],
                    pair["dh_distance"],
                    (
                        "DA"
                        if master.is_raw or dup.is_raw
                        else "NE"
                    )
                ]
            )

    if errors:

        errors_path = REPORTS / (
            f"greske_{stamp}.txt"
        )

        errors_path.write_text(
            "\n".join(errors),
            encoding="utf-8"
        )

    return dest


# ============================================================
# GRAFICKI INTERFEJS
# ============================================================

class PhotoApp:

    def __init__(self, root):

        self.root = root

        self.root.title(
            "PhotoAgent - lokalno pronalazenje duplikata"
        )

        self.root.geometry("1210x800")

        self.state = load_state()

        self.updates = queue.Queue()
        self.cancel = threading.Event()

        self.pairs = []
        self.photos = []

        self.busy = False
        self.preview_refs = []

        self.setup_ui()

        for path in self.state["roots"]:
            self.folder_list.insert(
                "end",
                path
            )

        self.root.after(
            150,
            self.poll
        )

    # --------------------------------------------------------
    # KREIRANJE INTERFEJSA
    # --------------------------------------------------------

    def setup_ui(self):

        top = ttk.Frame(
            self.root,
            padding=12
        )

        top.pack(fill="x")

        ttk.Label(
            top,
            text="1. Folderi za skeniranje",
            font=("Segoe UI", 12, "bold")
        ).pack(anchor="w")

        line = ttk.Frame(top)

        line.pack(
            fill="x",
            pady=5
        )

        self.folder_list = tk.Listbox(
            line,
            selectmode="extended",
            height=4
        )

        self.folder_list.pack(
            side="left",
            fill="x",
            expand=True
        )

        sb = ttk.Scrollbar(
            line,
            orient="vertical",
            command=self.folder_list.yview
        )

        sb.pack(
            side="left",
            fill="y"
        )

        self.folder_list.config(
            yscrollcommand=sb.set
        )

        btns = ttk.Frame(line)

        btns.pack(
            side="left",
            padx=8
        )

        ttk.Button(
            btns,
            text="+ Dodaj folder",
            command=self.add_folder
        ).pack(fill="x", pady=3)

        ttk.Button(
            btns,
            text="Ukloni iz liste",
            command=self.remove_folder
        ).pack(fill="x", pady=3)

        commands = ttk.Frame(top)

        commands.pack(
            fill="x",
            pady=7
        )

        self.scan_btn = ttk.Button(
            commands,
            text="2. Pokreni skeniranje",
            command=self.start_scan
        )

        self.scan_btn.pack(
            side="left",
            padx=(0, 8)
        )

        self.stop_btn = ttk.Button(
            commands,
            text="Zaustavi",
            command=self.stop_scan,
            state="disabled"
        )

        self.stop_btn.pack(
            side="left",
            padx=4
        )

        ttk.Button(
            commands,
            text="Otvori CSV izvestaje",
            command=self.open_reports
        ).pack(
            side="left",
            padx=6
        )

        self.progress = ttk.Progressbar(
            commands,
            mode="indeterminate",
            length=180
        )

        self.progress.pack(
            side="right"
        )

        self.status = tk.StringVar(
            value="Dodaj foldere i pokreni skeniranje."
        )

        ttk.Label(
            top,
            textvariable=self.status,
            wraplength=1100
        ).pack(anchor="w")

        middle = ttk.Frame(
            self.root,
            padding=(12, 4)
        )

        middle.pack(
            fill="both",
            expand=True
        )

        ttk.Label(
            middle,
            text="3. Rezultati: IDENTICNI i SLICNI",
            font=("Segoe UI", 12, "bold")
        ).pack(
            anchor="w",
            pady=(4, 7)
        )

        table_area = ttk.Frame(middle)

        table_area.pack(
            fill="both",
            expand=True
        )

        cols = (
            "type",
            "keep",
            "duplicate",
            "difference",
            "quality"
        )

        self.tree = ttk.Treeview(
            table_area,
            columns=cols,
            show="headings",
            height=10
        )

        for column, label, width in [
            ("type", "Tip", 105),
            ("keep", "Sacuvaj", 340),
            ("duplicate", "Kopija za proveru", 340),
            ("difference", "pHash / dHash", 110),
            ("quality", "RAW?", 55)
        ]:

            self.tree.heading(
                column,
                text=label
            )

            self.tree.column(
                column,
                width=width,
                minwidth=60,
                stretch=column in ("keep", "duplicate")
            )

        scroll = ttk.Scrollbar(
            table_area,
            orient="vertical",
            command=self.tree.yview
        )

        self.tree.config(
            yscrollcommand=scroll.set
        )

        self.tree.pack(
            side="left",
            fill="both",
            expand=True
        )

        scroll.pack(
            side="left",
            fill="y"
        )

        self.tree.bind(
            "<<TreeviewSelect>>",
            self.show_choice
        )

        # Dva panela za pregled fotografija

        previews = ttk.Frame(middle)

        previews.pack(
            fill="both",
            pady=8
        )

        left = ttk.LabelFrame(
            previews,
            text="PREPORUKA: SACUVAJ",
            padding=7
        )

        right = ttk.LabelFrame(
            previews,
            text="KANDIDAT: PREMESTI U KARANTIN",
            padding=7
        )

        left.pack(
            side="left",
            fill="both",
            expand=True,
            padx=(0, 6)
        )

        right.pack(
            side="left",
            fill="both",
            expand=True,
            padx=(6, 0)
        )

        self.keep_image = ttk.Label(left)
        self.dup_image = ttk.Label(right)

        self.keep_image.pack()
        self.dup_image.pack()

        self.keep_text = ttk.Label(
            left,
            text="Izaberi rezultat iz tabele.",
            wraplength=530
        )

        self.dup_text = ttk.Label(
            right,
            text="Uporedi fotografije.",
            wraplength=530
        )

        self.keep_text.pack(
            anchor="w",
            pady=4
        )

        self.dup_text.pack(
            anchor="w",
            pady=4
        )

        # Akcije

        actions = ttk.Frame(
            self.root,
            padding=12
        )

        actions.pack(fill="x")

        ttk.Button(
            actions,
            text="Premesti IZABRANU kopiju",
            command=self.move_selected
        ).pack(
            side="left",
            padx=(0, 8)
        )

        ttk.Button(
            actions,
            text="Premesti sve 100% identicne (bez RAW)",
            command=self.move_exact
        ).pack(
            side="left",
            padx=8
        )

        ttk.Button(
            actions,
            text="Vrati poslednju kopiju",
            command=self.restore_last
        ).pack(
            side="left",
            padx=8
        )

        ttk.Label(
            self.root,
            text=(
                "Fajlovi se ne brisu trajno. "
                "SLICNE slike zahtevaju pojedinacnu potvrdu."
            ),
            padding=(12, 0, 12, 10)
        ).pack(anchor="w")

    # --------------------------------------------------------
    # IZBOR FOLDERA
    # --------------------------------------------------------

    def add_folder(self):

        path = filedialog.askdirectory(
            title="Odaberi folder sa fotografijama"
        )

        if (
            path
            and path not in self.folder_list.get(0, "end")
        ):
            self.folder_list.insert(
                "end",
                path
            )

            self.save_roots()

    def remove_folder(self):

        for i in reversed(
            self.folder_list.curselection()
        ):
            self.folder_list.delete(i)

        self.save_roots()

    def save_roots(self):

        self.state["roots"] = list(
            self.folder_list.get(0, "end")
        )

        save_state(self.state)

    # --------------------------------------------------------
    # POKRETANJE SKENIRANJA
    # --------------------------------------------------------

    def start_scan(self):

        if self.busy:
            return

        folders = list(
            self.folder_list.get(0, "end")
        )

        if not roots_for_scan(folders):

            messagebox.showwarning(
                "Nema foldera",
                "Dodaj bar jedan postojeci folder."
            )

            return

        self.save_roots()

        self.cancel.clear()
        self.busy = True

        self.scan_btn.config(
            state="disabled"
        )

        self.stop_btn.config(
            state="normal"
        )

        self.progress.start(12)

        self.status.set(
            "Skeniranje je pokrenuto..."
        )

        self.tree.delete(
            *self.tree.get_children()
        )

        self.pairs = []

        def worker():

            try:
                result = scan(
                    folders,
                    self.updates,
                    self.cancel
                )

                self.updates.put(
                    ("done", result)
                )

            except Exception as exc:

                self.updates.put(
                    (
                        "error",
                        f"{type(exc).__name__}: {exc}"
                    )
                )

        threading.Thread(
            target=worker,
            daemon=True
        ).start()

    def stop_scan(self):

        self.cancel.set()

        self.status.set(
            "Zaustavljanje nakon trenutnog fajla..."
        )

    # --------------------------------------------------------
    # OBRADA REZULTATA IZ POZADINSKE NITI
    # --------------------------------------------------------

    def poll(self):

        try:

            while True:

                msg, data = self.updates.get_nowait()

                if msg == "status":

                    self.status.set(data)

                elif msg in ("done", "error"):

                    self.busy = False

                    self.progress.stop()

                    self.scan_btn.config(
                        state="normal"
                    )

                    self.stop_btn.config(
                        state="disabled"
                    )

                    if msg == "error":

                        messagebox.showerror(
                            "Greska pri skeniranju",
                            data
                        )

                    elif data is None:

                        self.status.set(
                            "Skeniranje je zaustavljeno."
                        )

                    else:

                        self.photos, self.pairs, errors = data

                        for i, pair in enumerate(self.pairs):

                            self.tree.insert(
                                "",
                                "end",
                                iid=str(i),
                                values=(
                                    pair["kind"],
                                    pair["keep"].path,
                                    pair["dup"].path,
                                    (
                                        f"{pair['ph_distance']}/"
                                        f"{pair['dh_distance']}"
                                    ),
                                    (
                                        "DA"
                                        if (
                                            pair["keep"].is_raw
                                            or pair["dup"].is_raw
                                        )
                                        else "NE"
                                    )
                                )
                            )

                        report = make_report(
                            self.pairs,
                            errors
                        )

                        exact = sum(
                            p["kind"] == "IDENTICAN"
                            for p in self.pairs
                        )

                        similar = len(self.pairs) - exact

                        self.status.set(
                            f"{len(self.photos)} fotografija | "
                            f"{exact} identicnih kopija | "
                            f"{similar} vizuelno slicnih | "
                            f"{len(errors)} gresaka | "
                            f"CSV: {report}"
                        )

        except queue.Empty:
            pass

        self.root.after(
            150,
            self.poll
        )

    # --------------------------------------------------------
    # PREGLED FOTOGRAFIJA
    # --------------------------------------------------------

    def show_choice(self, _event=None):

        selection = self.tree.selection()

        if not selection:
            return

        pair = self.pairs[
            int(selection[0])
        ]

        self.preview_refs = []

        for photo, label, desc in (
            (
                pair["keep"],
                self.keep_image,
                self.keep_text
            ),
            (
                pair["dup"],
                self.dup_image,
                self.dup_text
            )
        ):

            try:

                img, _, _, _ = open_picture(
                    photo.path
                )

                img.thumbnail(
                    (440, 210),
                    Image.Resampling.LANCZOS
                )

                tk_img = ImageTk.PhotoImage(
                    img.convert("RGB")
                )

                self.preview_refs.append(tk_img)

                label.config(
                    image=tk_img,
                    text=""
                )

                img.close()

            except Exception:

                label.config(
                    image="",
                    text="Pregled nije dostupan"
                )

            desc.config(
                text=(
                    f"{photo.path}\n"
                    f"{pretty(photo)}"
                ),
                wraplength=500
            )

    # --------------------------------------------------------
    # PREMESTANJE JEDNE KOPIJE
    # --------------------------------------------------------

    def move_pair(self, pair):

        move = None

        try:

            move = verify_and_move(pair)

            self.state["moves"].append(move)

            save_state(self.state)

            return None

        except Exception as exc:

            if move is not None:

                if (
                    self.state["moves"]
                    and self.state["moves"][-1] == move
                ):
                    self.state["moves"].pop()

                try:

                    Path(move["dest"]).rename(
                        move["origin"]
                    )

                except OSError as rollback_error:

                    return (
                        f"{exc}\n"
                        "VAZNO: Automatsko vracanje nije uspelo.\n"
                        f"Fajl je u: {move['dest']}\n"
                        f"{rollback_error}"
                    )

            return str(exc)

    def move_selected(self):

        if self.busy:
            return

        selection = self.tree.selection()

        if not selection:

            messagebox.showinfo(
                "Izbor",
                "Prvo izaberi jedan red."
            )

            return

        iid = selection[0]

        pair = self.pairs[int(iid)]

        if pair["kind"] == "SLICAN":

            question = (
                "Ove fotografije su samo VIZUELNO SLICNE!\n"
                "Mozda su razliciti kadrovi ili obrade.\n"
                "Obavezno proveri fotografije.\n\n"
            )

        else:

            question = (
                "Ovi fajlovi imaju isti SHA-256 sadrzaj.\n\n"
            )

        question += (
            f"SACUVAJ:\n{pair['keep'].path}\n\n"
            f"PREMESTI:\n{pair['dup'].path}\n\n"
            "Da li potvrdjujes?"
        )

        if not messagebox.askyesno(
            "Potvrdi izdvajanje",
            question
        ):
            return

        # Posebna zastita za RAW

        if pair["dup"].is_raw:

            code = simpledialog.askstring(
                "Posebna RAW zastita",
                (
                    "Izabrana kopija je RAW fotografija.\n"
                    "Pripadajuci XMP fajlovi se ne premestaju.\n"
                    "Za potvrdu upisi: RAW"
                )
            )

            if code != "RAW":
                return

        error = self.move_pair(pair)

        if error:

            messagebox.showerror(
                "Premestanje nije uspelo",
                error
            )

        else:

            self.tree.delete(iid)

            self.status.set(
                "Kopija je premestena u karantin."
            )

    # --------------------------------------------------------
    # GRUPNO IZDVAJANJE IDENTICNIH KOPIJA
    # --------------------------------------------------------

    def move_exact(self):

        if self.busy:
            return

        items = [
            (
                iid,
                self.pairs[int(iid)]
            )
            for iid in self.tree.get_children()

            if (
                self.pairs[int(iid)]["kind"] == "IDENTICAN"

                and not self.pairs[int(iid)]["dup"].is_raw

                and bool(
                    self.pairs[int(iid)]["dup"].phash
                )

                and bool(
                    self.pairs[int(iid)]["keep"].phash
                )
            )
        ]

        if not items:

            messagebox.showinfo(
                "Nema kandidata",
                "Nema identicnih ne-RAW kopija."
            )

            return

        confirmed = messagebox.askyesno(
            "Potvrda grupnog izdvajanja",
            (
                f"Premestiti {len(items)} identicnih "
                "kopija u karantin?\n\n"
                "Proveri da nisu namerne rezervne kopije.\n"
                "Prvi izabrani folder ima prioritet.\n\n"
                "Akcija se moze ponistiti."
            )
        )

        if not confirmed:
            return

        successful = 0
        failed = []

        for iid, pair in items:

            error = self.move_pair(pair)

            if error:

                failed.append(
                    f"{pair['dup'].path}: {error}"
                )

            else:

                successful += 1
                self.tree.delete(iid)

        self.status.set(
            f"Premesteno: {successful} | "
            f"Greske: {len(failed)}"
        )

        if failed:

            messagebox.showwarning(
                "Delimican uspeh",
                "\n".join(failed[:6])
            )

    # --------------------------------------------------------
    # VRACANJE POSLEDNJE KOPIJE
    # --------------------------------------------------------

    def restore_last(self):

        if self.busy:
            return

        for i in range(
            len(self.state["moves"]) - 1,
            -1,
            -1
        ):

            entry = self.state["moves"][i]

            src = Path(entry["origin"])
            dest = Path(entry["dest"])

            if not dest.is_file() or dest.is_symlink():
                continue

            if src.exists():

                messagebox.showerror(
                    "Konflikt",
                    (
                        "Originalna putanja je zauzeta.\n"
                        f"Necu prepisati fajl:\n{src}"
                    )
                )

                return

            if not messagebox.askyesno(
                "Vrati kopiju",
                f"Vratiti fotografiju u:\n{src}?"
            ):
                return

            try:

                src.parent.mkdir(
                    parents=True,
                    exist_ok=True
                )

                dest.rename(src)

                self.state["moves"].pop(i)

                save_state(self.state)

                self.status.set(
                    f"Vraceno: {src}"
                )

            except OSError as exc:

                messagebox.showerror(
                    "Vracanje nije uspelo",
                    str(exc)
                )

            return

        messagebox.showinfo(
            "Nema kopija",
            "Nema evidentiranih kopija za vracanje."
        )

    # --------------------------------------------------------
    # OTVARANJE IZVESTAJA
    # --------------------------------------------------------

    def open_reports(self):

        REPORTS.mkdir(
            parents=True,
            exist_ok=True
        )

        if sys.platform == "win32":

            os.startfile(str(REPORTS))

        elif sys.platform == "darwin":

            import subprocess

            subprocess.Popen(
                ["open", str(REPORTS)]
            )

        else:

            import subprocess

            try:

                subprocess.Popen(
                    ["xdg-open", str(REPORTS)]
                )

            except OSError:

                messagebox.showinfo(
                    "Putanja do izvestaja",
                    str(REPORTS)
                )


# ============================================================
# POKRETANJE PROGRAMA
# ============================================================

if __name__ == "__main__":

    app_root = tk.Tk()

    PhotoApp(app_root)

    app_root.mainloop()
