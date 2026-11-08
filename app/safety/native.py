"""Native no-replace rename. No copy/delete or ordinary rename fallback.

Windows pins source and ancestor handles against replacement for the entire
verification/rename window. Linux walks directory descriptors with O_NOFOLLOW.
Linux has no general rename-by-file-handle syscall; cooperative local storage is
required (see SECURITY.md for the remaining source-name race).
"""
from __future__ import annotations

from contextlib import ExitStack, contextmanager
import ctypes
import os
from pathlib import Path
import sys
from typing import Any, BinaryIO, Callable, Iterator

from app.core.models import SafetyError, Snapshot
from app.safety.paths import check_path, snapshot_stream


def _windows_api() -> Any:
    from ctypes import wintypes
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.CreateFileW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD,
                                   ctypes.c_void_p, wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE]
    kernel.CreateFileW.restype = wintypes.HANDLE
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel.CloseHandle.restype = wintypes.BOOL
    kernel.SetFileInformationByHandle.argtypes = [wintypes.HANDLE, ctypes.c_int,
                                                  ctypes.c_void_p, wintypes.DWORD]
    kernel.SetFileInformationByHandle.restype = wintypes.BOOL
    return kernel


@contextmanager
def _win_open(path: Path, *, directory: bool = False, move: bool = False) -> Iterator[BinaryIO | int]:
    import msvcrt
    kernel = _windows_api()
    access = 0x80 if directory else 0x80000000 | (0x10000 if move else 0)
    # Directories allow child creation, but deny renaming the directory itself.
    sharing = 3 if directory else 1
    handle = kernel.CreateFileW(str(path), access, sharing, None, 3,
                                0x02000000 | 0x00200000, None)
    if handle == ctypes.c_void_p(-1).value:
        raise ctypes.WinError(ctypes.get_last_error())
    if directory:
        try:
            yield handle
        finally:
            kernel.CloseHandle(handle)
    else:
        try:
            fd = msvcrt.open_osfhandle(handle, os.O_RDONLY | os.O_BINARY)
        except Exception:
            kernel.CloseHandle(handle)
            raise
        with os.fdopen(fd, "rb") as stream:
            yield stream


def _win_rename(stream: BinaryIO, destination: Path) -> None:
    import msvcrt
    from ctypes import wintypes

    class RenameInfo(ctypes.Structure):
        _fields_ = [("ReplaceIfExists", wintypes.DWORD), ("RootDirectory", wintypes.HANDLE),
                    ("FileNameLength", wintypes.DWORD), ("FileName", wintypes.WCHAR * 1)]

    name = str(destination).encode("utf-16-le")
    buffer = ctypes.create_string_buffer(RenameInfo.FileName.offset + len(name) + 2)
    info = ctypes.cast(buffer, ctypes.POINTER(RenameInfo)).contents
    info.ReplaceIfExists = 0
    info.RootDirectory = None
    info.FileNameLength = len(name)
    ctypes.memmove(ctypes.addressof(buffer) + RenameInfo.FileName.offset, name, len(name))
    if not _windows_api().SetFileInformationByHandle(
        msvcrt.get_osfhandle(stream.fileno()), 3, buffer, len(buffer)
    ):
        raise ctypes.WinError(ctypes.get_last_error())


def _linux_dir(stack: ExitStack, path: Path) -> int:
    flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
    fd = os.open(path.anchor, flags)
    stack.callback(os.close, fd)
    for part in path.parts[1:]:
        fd = os.open(part, flags, dir_fd=fd)
        stack.callback(os.close, fd)
    return fd


def ensure_directory(root: Path, destination: Path) -> None:
    """Create destination parents without traversing a redirected component."""
    root, destination = check_path(root), check_path(destination, allow_missing=True)
    parts = destination.relative_to(root).parts
    with ExitStack() as stack:
        if sys.platform == "win32":
            for parent in (*reversed(root.parents), root):
                stack.enter_context(_win_open(parent, directory=True))
            current = root
            for part in parts:
                current = current / part
                try:
                    current.mkdir()
                except FileExistsError:
                    pass
                check_path(current)
                stack.enter_context(_win_open(current, directory=True))
                check_path(current)
        elif sys.platform.startswith("linux"):
            fd = _linux_dir(stack, root)
            for part in parts:
                try:
                    os.mkdir(part, dir_fd=fd)
                    os.fsync(fd)
                except FileExistsError:
                    pass
                fd = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
                stack.callback(os.close, fd)
        else:
            raise SafetyError("platform_unsupported")


def rename_verified(source: Path, destination: Path, keeper: Path | None,
                    verify: Callable[[BinaryIO, BinaryIO | None], None], expected: Snapshot) -> None:
    source, destination = check_path(source), check_path(destination, allow_missing=True)
    if source.stat().st_dev != destination.parent.stat().st_dev:
        raise SafetyError("cross_device_move")
    with ExitStack() as stack:
        if sys.platform == "win32":
            parents = {p for path in (source, destination, keeper) if path is not None for p in path.parents}
            for parent in sorted(parents, key=lambda p: (len(p.parts), str(p))):
                stack.enter_context(_win_open(parent, directory=True))
            src = stack.enter_context(_win_open(source, move=True))
            keep = stack.enter_context(_win_open(keeper)) if keeper is not None else None
            verify(src, keep)
            _win_rename(src, destination)
        elif sys.platform.startswith("linux"):
            srcdir = _linux_dir(stack, source.parent)
            dstdir = _linux_dir(stack, destination.parent)
            flags = os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK
            src = stack.enter_context(os.fdopen(os.open(source.name, flags, dir_fd=srcdir), "rb"))
            keep = None
            if keeper is not None:
                keepdir = _linux_dir(stack, keeper.parent)
                keep = stack.enter_context(os.fdopen(os.open(keeper.name, flags, dir_fd=keepdir), "rb"))
            verify(src, keep)
            st = os.stat(source.name, dir_fd=srcdir, follow_symlinks=False)
            if (st.st_dev, st.st_ino) != (expected.identity.device, expected.identity.inode):
                raise SafetyError("source_name_replaced")
            libc = ctypes.CDLL(None, use_errno=True)
            try:
                renameat2 = libc.renameat2
            except AttributeError as exc:
                raise SafetyError("rename_noreplace_unsupported") from exc
            renameat2.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_uint]
            renameat2.restype = ctypes.c_int
            if renameat2(srcdir, os.fsencode(source.name), dstdir, os.fsencode(destination.name), 1):
                error = ctypes.get_errno()
                raise OSError(error, os.strerror(error), str(destination))
            os.fsync(srcdir)
            os.fsync(dstdir)
        else:
            raise SafetyError("platform_unsupported")
        # Verify the open file, then the service verifies the resulting path.
        from app.safety.paths import same_content
        if not same_content(snapshot_stream(src), expected):
            raise SafetyError("post_move_content_changed")
