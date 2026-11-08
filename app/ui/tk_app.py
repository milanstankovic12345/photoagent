from __future__ import annotations

import base64
from concurrent.futures import ThreadPoolExecutor
import io
import logging
from pathlib import Path
import queue
import threading
from typing import Any, Callable
import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog, ttk

from PIL import Image, ImageTk

from app.core.models import Approval, Kind, Plan
from app.i18n import tr
from app.safety.journal import Journal
from app.services.reports import make_report, pretty
from app.services.application import Application
from app.storage.index import PAGE_SIZE

log = logging.getLogger(__name__)


class PhotoApp:
    def __init__(self, root: tk.Tk | tk.Toplevel, *, home: Path | None = None) -> None:
        self.root = root
        self.home = home if home is not None else Path.home()
        self.state_path = self.home / ".photo_agent_state.json"
        self.reports = self.home / "PhotoAgentReports"
        self.service = Application(self.home)
        self.session_id = None
        self.scan_complete = False
        self.page_offset = 0
        self.page_total = 0
        self._service_closing = False
        self.root.title("PhotoAgent - lokalno pronalazenje duplikata")
        self.root.geometry("1210x800")
        self.state = {"roots": [], "moves": []}
        self.journal = None
        self.operations = None
        self.history_error = ""
        self.updates = queue.Queue()
        self.cancel = threading.Event()
        self.preview_cancel = threading.Event()
        self.executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="photoagent")
        self.futures = []
        self.pairs, self.photos, self.preview_refs = [], [], []
        self.preview_token = 0
        self.confirmation_dialog: tk.Toplevel | None = None
        self.busy = False
        self.closing = False
        self.setup_ui()
        self.root.protocol("WM_DELETE_WINDOW", self.close)
        self._submit("initialized", self._initialize)
        self.root.after(150, self.poll)

    def _initialize(self) -> tuple[Journal, dict, list[str]]:
        return self.service.initialize()

    def _submit(self, event: str, function: Callable[[], Any], *,
                context: Any = None, background: bool = False) -> None:
        if not background:
            self.busy = True
            self.scan_btn.config(state="disabled")
            self.stop_btn.config(state="normal")
            self.progress.start(12)

        def worker() -> None:
            try:
                self.updates.put((event, (True, function(), context)))
            except Exception as exc:
                log.exception("background_task_failed", extra={"task": event})
                self.updates.put((event, (False, f"{type(exc).__name__}: {exc}", context)))

        self.futures.append(self.executor.submit(worker))

    def setup_ui(self) -> None:

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

        pagination = ttk.Frame(middle)
        pagination.pack(fill="x", pady=3)
        self.previous_page = ttk.Button(pagination, text=tr("previous_page"), command=lambda: self.change_page(-1))
        self.previous_page.pack(side="left")
        self.page_label = ttk.Label(pagination, text=tr("page_count", 0, 0))
        self.page_label.pack(side="left", padx=12)
        self.next_page = ttk.Button(pagination, text=tr("next_page"), command=lambda: self.change_page(1))
        self.next_page.pack(side="left")

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
            text="Izdvoji bezbedne EXACT kandidate",
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

    def add_folder(self) -> None:
        if self.busy:
            return
        path = filedialog.askdirectory(title="Odaberi folder sa fotografijama")
        if path and path not in self.folder_list.get(0, "end"):
            self.folder_list.insert("end", path)
            self.save_roots()

    def remove_folder(self) -> None:
        if self.busy:
            return
        for index in reversed(self.folder_list.curselection()):
            self.folder_list.delete(index)
        self.save_roots()

    def save_roots(self) -> None:
        self.state["roots"] = list(self.folder_list.get(0, "end"))
        if not self.journal or not self.journal.writable:
            self.status.set(tr("history_error"))
            return
        value = {"roots": self.state["roots"][:], "moves": self.state["moves"][:]}

        self._submit("settings_saved", lambda: self.service.save_settings(value))

    def start_scan(self) -> None:
        if self.busy:
            return
        folders = list(self.folder_list.get(0, "end"))
        if not folders:
            messagebox.showinfo("Folderi", "Dodaj bar jedan folder.")
            return
        self.cancel.clear()
        self.preview_cancel.set()
        self.preview_token += 1
        self.photos, self.pairs = [], []
        self.session_id = None
        self.scan_complete = False
        self.page_offset = self.page_total = 0
        self.tree.delete(*self.tree.get_children())
        self.status.set("Skeniranje je pokrenuto...")

        self._submit("scanned", lambda: self.service.scan_with_report(folders, self.updates, self.cancel, make_report))

    def stop_scan(self) -> None:
        self.cancel.set()
        self.preview_cancel.set()
        self.status.set("Zaustavljanje na bezbednoj granici operacije...")

    def _idle(self) -> None:
        self.busy = False
        self.progress.stop()
        self.scan_btn.config(state="normal")
        self.stop_btn.config(state="disabled")

    def _populate(self) -> None:
        self.tree.delete(*self.tree.get_children())
        for index, pair in enumerate(self.pairs):
            self.tree.insert("", "end", iid=str(index), values=(
                pair.kind.value, pair.keep.path, pair.dup.path,
                f"{pair.ph_distance}/{pair.dh_distance}",
                "DA" if pair.keep.is_raw or pair.dup.is_raw else "NE"))
        self.page_label.config(text=tr("page_count", min(self.page_offset + len(self.pairs), self.page_total), self.page_total))
        self.previous_page.config(state="normal" if self.page_offset else "disabled")
        self.next_page.config(state="normal" if self.page_offset + PAGE_SIZE < self.page_total else "disabled")

    def change_page(self, direction: int) -> None:
        if self.busy or self.closing or not self.session_id:
            return
        offset = max(0, self.page_offset + direction * PAGE_SIZE)
        if offset >= self.page_total and offset:
            return
        self.preview_token += 1
        self.preview_cancel.set()
        self._submit("page", lambda: self.service.page(self.session_id, offset), context=offset)

    def _invalidate(self, paths: set[str]) -> None:
        self.preview_token += 1
        self.preview_cancel.set()
        self.pairs = [p for p in self.pairs if p.keep.path not in paths and p.dup.path not in paths]
        self.photos = [p for p in self.photos if p.path not in paths]
        self._populate()
        self.preview_refs = []
        for label in (self.keep_image, self.dup_image):
            label.config(image="", text="Izaberi fotografiju")

    def poll(self) -> None:
        try:
            while True:
                event, payload = self.updates.get_nowait()
                if event == "status":
                    key, number = payload
                    self.status.set(tr(key, number))
                    continue
                ok, data, context = payload
                if event != "preview":
                    self._idle()
                if event == "operated":
                    # Also invalidate on a partial failure/final journal failure.
                    self._invalidate({m.source for m in context.moves})
                    if self.session_id and not self.closing:
                        self._submit("page", lambda: self.service.page(self.session_id, 0), context=0)
                if not ok:
                    if event == "preview" and context == self.preview_token:
                        for label in (self.keep_image, self.dup_image):
                            label.config(image="", text=f"Pregled nije dostupan\n{data}")
                    if event != "preview":
                        self.status.set(tr("operation_error") if event == "operated" else str(data))
                        if not self.closing:
                            messagebox.showerror("Operacija nije uspela", str(data))
                    continue
                if event == "initialized":
                    self.journal, self.state, issues = data
                    self.operations = self.service.operations
                    for path in self.state["roots"]:
                        self.folder_list.insert("end", path)
                    if not self.journal.writable or issues:
                        self.status.set(tr("history_error") if not self.journal.writable else "Oporavak zahteva proveru.")
                        if not self.closing:
                            messagebox.showwarning("Istorija / oporavak", "\n".join(issues) or self.journal.error or "Druga instanca drži istoriju zaključanom.")
                elif event == "scanned":
                    result, report, report_error, page, errors, index_warning = data
                    self.session_id = result.session_id
                    self.scan_complete = result.complete
                    self.pairs, self.photos, self.page_total = page
                    self.page_offset = 0
                    self._populate()
                    prefix = tr("cancelled") if result.cancelled else "Završeno" if result.complete else tr("incomplete")
                    exact = result.exact_count
                    self.status.set(f"{prefix} | {result.photo_count} fotografija | {exact} EXACT | "
                                    f"{result.pair_count - exact} VISUAL | {result.error_count} grešaka | CSV: {report or report_error}"
                                    + (" | " + tr("index_warning", index_warning) if index_warning else ""))
                    if errors and not self.closing:
                        messagebox.showwarning("Nepotpuno skeniranje", "\n".join(errors[:8]))
                elif event == "page":
                    self.pairs, self.photos, self.page_total = data
                    self.page_offset = context
                    self._populate()
                elif event == "prepared" and not self.closing:
                    self._confirm(data)
                elif event == "operated":
                    self.status.set("Operacija je završena. Istorija je sačuvana.")
                elif event == "preview" and context == self.preview_token:
                    self._display_preview(data)
        except queue.Empty:
            pass
        except Exception as exc:
            log.exception("gui_poll_failed")
            self.status.set(f"Greška prikaza: {exc}")
        finally:
            self.futures = [f for f in self.futures if not f.done()]
            if self.closing and not self.futures:
                if not self._service_closing:
                    self._service_closing = True
                    self.futures.append(self.executor.submit(self.service.close))
                    self.root.after(150, self.poll)
                else:
                    self.executor.shutdown(wait=False)
                    self.root.destroy()
            else:
                # A report, dialog, or rendering error must never stop polling.
                self.root.after(150, self.poll)

    def show_choice(self, _event: tk.Event | None = None) -> None:
        selection = self.tree.selection()
        if not selection or self.closing:
            return
        pair = self.pairs[int(selection[0])]
        self.preview_cancel.set()
        self.preview_cancel = threading.Event()
        cancel = self.preview_cancel
        self.preview_token += 1
        token = self.preview_token
        for photo, label, desc in ((pair.keep, self.keep_image, self.keep_text),
                                   (pair.dup, self.dup_image, self.dup_text)):
            label.config(image="", text="Učitavanje pregleda...")
            desc.config(text=f"{photo.path}\n{pretty(photo)}\nHeuristička preporuka; obrade mogu imati posebnu vrednost.", wraplength=500)

        self._submit("preview", lambda: self.service.previews(pair, cancel), context=token, background=True)

    def _display_preview(self, results: list[tuple[dict | None, str]]) -> None:
        self.preview_refs = []
        for label, (data, error) in zip((self.keep_image, self.dup_image), results):
            if data is None:
                label.config(image="", text=f"Pregled nije dostupan\n{error}")
                continue
            with Image.open(io.BytesIO(base64.b64decode(data["preview"]))) as image:
                image.thumbnail((440, 210), Image.Resampling.LANCZOS)
                tk_image = ImageTk.PhotoImage(image)
            self.preview_refs.append(tk_image)
            label.config(image=tk_image, text="")

    def _can_operate(self, *, require_scan: bool = False) -> bool:
        if self.busy or not self.operations:
            return False
        if require_scan and self.session_id and not self.scan_complete:
            messagebox.showinfo(tr("incomplete"), tr("scan_review_only"))
            return False
        if not self.journal.writable:
            messagebox.showerror("Istorija", tr("history_error"))
            return False
        self.cancel.clear()
        self.preview_cancel.set()
        return True

    def move_selected(self) -> None:
        if not self._can_operate(require_scan=True):
            return
        selected = self.tree.selection()
        if not selected:
            messagebox.showinfo("Izbor", "Prvo izaberi jedan red.")
            return
        pair = self.pairs[int(selected[0])]
        self._prepare(lambda: self.service.prepare([pair], self.cancel, session=self.session_id))

    def move_exact(self) -> None:
        if self._can_operate(require_scan=True):
            if self.session_id:
                self._prepare(lambda: self.service.prepare_session(self.session_id, self.cancel))

    def restore_last(self) -> None:
        if self._can_operate():
            self._prepare(lambda: self.service.restore_plan(self.cancel))

    def _prepare(self, builder: Callable[[], Plan]) -> None:
        self._submit("prepared", builder)

    def _confirm(self, plan: Plan) -> None:
        if not plan.moves:
            messagebox.showinfo("Nema kandidata", "Nema dozvoljenih grupnih kandidata: samo dekodirani EXACT parovi u istom korenu, bez RAW i XMP.")
            return
        # Read-only, scrollable preview contains every operation before approval.
        dialog = tk.Toplevel(self.root)
        self.confirmation_dialog = dialog
        dialog.title("Pregled nepromenljivog plana")
        dialog.geometry("900x600")
        text = tk.Text(dialog, wrap="word")
        scroll = ttk.Scrollbar(dialog, command=text.yview)
        text.config(yscrollcommand=scroll.set)
        scroll.pack(side="right", fill="y")
        text.pack(fill="both", expand=True)
        text.insert("end", f"Plan {plan.id}\nBroj operacija: {len(plan.moves)}\n\n")
        for move in plan.moves:
            warning = ""
            if move.kind != Kind.EXACT:
                warning += "VIZUELNA SLIČNOST NIJE DOKAZ DUPLIKATA. Mogući drugi kadrovi ili obrade.\n"
            if move.keeper and move.keeper.root != move.root:
                warning += "Kopije su u različitim korenima; mogu biti namerni backup.\n"
            if move.xmp:
                warning += tr("xmp_warning") + "\n" + "\n".join(move.xmp) + "\n"
            if move.legacy:
                warning += tr("legacy_warning") + "\n"
            keeper = f"SACUVAJ: {move.keeper.path}\nSHA-256: {move.keeper.sha256}\n" if move.keeper else ""
            text.insert("end", f"{warning}{move.action} / {move.kind.value}\n{keeper}"
                        f"IZVOR: {move.source}\nODREDIŠTE: {move.destination}\nSHA-256: {move.expected.sha256}\n"
                        f"Identitet: {move.expected.identity}\n\n")
        text.config(state="disabled")
        approved = []

        def approve() -> None:
            raw = any(m.raw for m in plan.moves)
            legacy = any(m.legacy for m in plan.moves)
            if legacy and not messagebox.askyesno("Stara istorija", tr("legacy_warning"), parent=dialog):
                return
            if raw and simpledialog.askstring("Posebna RAW zaštita", "Za potvrdu upiši: RAW", parent=dialog) != "RAW":
                return
            approved.append(Approval(plan, raw=raw, legacy=legacy))
            dialog.destroy()

        ttk.Button(dialog, text="Potvrdi prikazani plan", command=approve).pack(side="left", padx=12, pady=8)
        ttk.Button(dialog, text="Odustani", command=dialog.destroy).pack(side="left", padx=12, pady=8)
        dialog.transient(self.root)
        dialog.grab_set()
        self.root.wait_window(dialog)
        self.confirmation_dialog = None
        if approved and not self.closing:
            self._submit("operated", lambda: self.service.execute(plan, approved[0], self.cancel), context=plan)

    def open_reports(self) -> None:
        if not self.busy:
            self._submit("reports_opened", self.service.open_reports)

    def close(self) -> None:
        self.closing = True
        self.cancel.set()
        self.preview_cancel.set()
        if self.confirmation_dialog is not None:
            self.confirmation_dialog.destroy()
            self.confirmation_dialog = None
        self.status.set("Zatvaranje nakon bezbednog završetka aktivnog posla...")


