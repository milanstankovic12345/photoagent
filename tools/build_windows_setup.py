"""Stage a private Windows runtime and compile the offline installer."""
from __future__ import annotations

import argparse
import json
import platform
import re
import shutil
import subprocess
import sys
import sysconfig
from pathlib import Path
from zipfile import ZipFile

from tools.build_release import ROOT, digest, safe_file, wheel_inventory

EMBED_SHA256 = "4acbed6dd1c744b0376e3b1cf57ce906f9dc9e95e68824584c8099a63025a3c3"


def copy_tree(source: Path, target: Path, suffixes: set[str] | None = None) -> None:
    for path in source.rglob("*"):
        if "__pycache__" in path.parts or not path.is_file():
            continue
        if suffixes is not None and path.suffix not in suffixes:
            continue
        safe_file(path, source)
        dest = target / path.relative_to(source)
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(path, dest)


def build(embed: Path, wheels: Path, iscc: Path, output: Path, version: str) -> None:
    if platform.python_version() != "3.12.10" or sysconfig.get_platform() != "win-amd64":
        raise ValueError("Build with CPython 3.12.10 Windows x64 (matching Tcl/Tk)")
    if not re.fullmatch(r"[0-9]+(?:\.[0-9]+){1,3}", version):
        raise ValueError("Use a numeric release version")
    if digest(embed) != EMBED_SHA256:
        raise ValueError("Incorrect CPython embeddable archive")
    rows = wheel_inventory(wheels, ROOT / "packaging/runtime-win-amd64-py312.txt")
    output.mkdir(parents=True, exist_ok=False)
    payload = output / "payload"
    runtime = payload / ".runtime"
    runtime.mkdir(parents=True)
    with ZipFile(embed) as archive:
        archive.extractall(runtime)  # Entire official archive pinned above.
    base = Path(sys.base_prefix)
    for name in ("_tkinter.pyd", "tcl86t.dll", "tk86t.dll", "zlib1.dll"):
        shutil.copyfile(base / "DLLs" / name, runtime / name)
    copy_tree(base / "Lib/tkinter", runtime / "Lib/tkinter", {".py"})
    copy_tree(base / "tcl", runtime / "tcl")
    (runtime / "python312._pth").write_text(
        "python312.zip\n.\nLib\nLib/site-packages\n..\n", encoding="ascii")
    req = output / "requirements-locked.txt"
    req.write_text("".join(f"{r['name']}=={r['version']} --hash=sha256:{r['sha256']}\n"
                           for r in rows), encoding="ascii")
    subprocess.run([sys.executable, "-I", "-m", "pip", "--isolated", "install",
                    "--no-index", "--no-compile", "--no-cache-dir", "--only-binary=:all:",
                    "--find-links", str(wheels), "--require-hashes", "-r", str(req),
                    "--target", str(runtime / "Lib/site-packages")], check=True)
    copy_tree(ROOT / "app", payload / "app", {".py", ".json", ".qm", ".ts", ".svg", ".qss", ".qrc"})
    for entry in ("photo_agent.py", "packaging/windows_entry.py", "packaging/check_install.py"):
        shutil.copyfile(ROOT / entry, payload / Path(entry).name)
    (payload / "tools").mkdir()
    shutil.copyfile(ROOT / "tools/release_smoke.py", payload / "tools/release_smoke.py")
    manifest = {"version": version, "python": platform.python_version(), "embed_sha256": EMBED_SHA256,
                "dependencies": rows, "files": {p.relative_to(payload).as_posix(): digest(p)
                                                for p in sorted(payload.rglob("*")) if p.is_file()}}
    (payload / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    subprocess.run([runtime / "python.exe", "-B", payload / "check_install.py"], check=True)
    subprocess.run([iscc, f"/DReleaseVersion={version}", f"/DPayload={payload}",
                    f"/O{output}", ROOT / "packaging/windows.iss"], check=True)
    setup = output / "PhotoAgent-Setup.exe"
    (output / "PhotoAgent-Setup.exe.sha256").write_text(digest(setup) + "\n", encoding="ascii")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for option in ("embed", "wheelhouse", "iscc", "output"):
        parser.add_argument("--" + option, type=Path, required=True)
    parser.add_argument("--version", required=True)
    args = parser.parse_args()
    build(args.embed.resolve(), args.wheelhouse.resolve(), args.iscc.resolve(),
          args.output.resolve(), args.version)
