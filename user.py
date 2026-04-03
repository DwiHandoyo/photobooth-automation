"""Photobooth User App — simplified session-based interface.

Flow: Enter email → Start Session → Photos accumulate → Send all → Next user.
"""
import os
import re
import shutil
import sys
import threading
import queue

import customtkinter as ctk
from tkinter import messagebox, scrolledtext
from datetime import datetime
from PIL import Image as PILImage, ImageTk

from config import load_config, cleanup_old_sessions
from watcher import start_watching
from drive_upload import DriveClient
from mailer import send_photo_email
from printer import print_image, print_grid_2x2
import state


ctk.set_appearance_mode("light")
ctk.set_default_color_theme("blue")

BLUE = "#3B82F6"
BLUE_HOVER = "#2563EB"
BLUE_LIGHT = "#EFF6FF"
DARK = "#1E293B"
GRAY = "#94A3B8"
WHITE = "#FFFFFF"
BG = "#F7F8FA"
BORDER = "#E2E8F0"


def resolve_path(path):
    if os.path.isabs(path):
        return path
    base = os.path.dirname(os.path.abspath(sys.argv[0]))
    return os.path.join(base, path)


def make_session_folder(email):
    """Create a sanitized session folder name from email + timestamp."""
    name, domain = email.split("@")
    sanitized = re.sub(r"[^\w.-]", "_", f"{name}-{domain}")
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"{sanitized}_{timestamp}"


class UserApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Photobooth")
        self.geometry("620x700")
        self.resizable(False, False)
        self.configure(fg_color=BG)

        self.cfg = load_config()
        self.drive_client = None
        self.observer = None
        self._session_folder = None
        self._session_email = None
        self._session_path = None
        self._photos = []
        self._print_count = 0
        self._file_queue = queue.Queue()
        self._log_queue = queue.Queue()

        # Cleanup old sessions on start
        self._watch_root = resolve_path(self.cfg["watch_folder"])
        cleanup_old_sessions(self._watch_root, int(self.cfg.get("cleanup_days", 30)))

        self._build_header()
        self._build_email_frame()
        self._build_session_frame()
        self._build_log_frame()
        self._build_status_bar()

        self._poll_log_queue()
        self._poll_file_queue()
        self._poll_state()

        # Start watching root photos/ folder immediately
        self.observer = start_watching(self._watch_root, self._on_new_file)

        # Connect to Drive in background
        threading.Thread(target=self._connect_drive, daemon=True).start()

    # ══════════════════════════════════════
    # UI Building
    # ══════════════════════════════════════

    def _build_header(self):
        header = ctk.CTkFrame(self, fg_color=BLUE, corner_radius=0, height=64)
        header.pack(fill="x")
        header.pack_propagate(False)

        ctk.CTkLabel(
            header, text="Photobooth",
            font=ctk.CTkFont(family="Segoe UI", size=20, weight="bold"),
            text_color=WHITE,
        ).pack(pady=(10, 0))

        ctk.CTkLabel(
            header, text="Take photos and we'll send them to your email!",
            font=ctk.CTkFont(family="Segoe UI", size=11),
            text_color="#BFDBFE",
        ).pack(pady=(0, 8))

    def _build_email_frame(self):
        """State A: email entry screen."""
        self.email_frame = ctk.CTkFrame(
            self, fg_color=WHITE, corner_radius=12,
            border_width=1, border_color=BORDER,
        )
        self.email_frame.pack(fill="x", padx=16, pady=(16, 8))

        inner = ctk.CTkFrame(self.email_frame, fg_color=WHITE)
        inner.pack(fill="x", padx=20, pady=16)

        ctk.CTkLabel(
            inner, text="Enter your email to start",
            font=ctk.CTkFont(family="Segoe UI", size=14, weight="bold"),
            text_color=DARK,
        ).pack(anchor="w", pady=(0, 8))

        row = ctk.CTkFrame(inner, fg_color=WHITE)
        row.pack(fill="x")

        self.entry_email = ctk.CTkEntry(
            row, width=320,
            fg_color=BG, text_color=DARK,
            border_color=BORDER, border_width=1,
            corner_radius=8,
            font=ctk.CTkFont(family="Segoe UI", size=13),
            placeholder_text="email@example.com",
            placeholder_text_color=GRAY,
        )
        self.entry_email.pack(side="left", padx=(0, 8), expand=True, fill="x")

        self.btn_start_session = ctk.CTkButton(
            row, text="Start Session", width=140, height=38,
            fg_color=BLUE, hover_color=BLUE_HOVER,
            text_color=WHITE, corner_radius=10,
            font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
            command=self._start_session_clicked,
        )
        self.btn_start_session.pack(side="left")

    def _build_session_frame(self):
        """State B: photo session screen (hidden initially)."""
        self.session_frame = ctk.CTkFrame(
            self, fg_color=BLUE_LIGHT, corner_radius=12,
            border_width=1, border_color=BLUE,
        )
        # Not packed yet

        inner = ctk.CTkFrame(self.session_frame, fg_color=BLUE_LIGHT)
        inner.pack(fill="x", padx=16, pady=12)

        # Session info row
        info_row = ctk.CTkFrame(inner, fg_color=BLUE_LIGHT)
        info_row.pack(fill="x")

        self.lbl_session_email = ctk.CTkLabel(
            info_row, text="",
            font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"),
            text_color=BLUE,
        )
        self.lbl_session_email.pack(side="left")

        self.lbl_photo_count = ctk.CTkLabel(
            info_row, text="0 photos",
            font=ctk.CTkFont(family="Segoe UI", size=12),
            text_color=DARK,
        )
        self.lbl_photo_count.pack(side="right")

        # Photo grid with thumbnails + checkboxes
        self.photo_scroll = ctk.CTkScrollableFrame(
            inner, height=230, fg_color=WHITE,
            border_color=BORDER, border_width=1, corner_radius=8,
        )
        self.photo_scroll.pack(fill="x", pady=(8, 8))
        self._photo_checkboxes = []  # list of (frame, BooleanVar, file_path)
        self._thumb_refs = []  # keep references to prevent garbage collection

        # Buttons row
        btn_row = ctk.CTkFrame(inner, fg_color=BLUE_LIGHT)
        btn_row.pack(fill="x")

        self.btn_send = ctk.CTkButton(
            btn_row, text="Send to Email", width=150, height=38,
            fg_color=BLUE, hover_color=BLUE_HOVER,
            text_color=WHITE, corner_radius=10,
            font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
            command=self._send_clicked,
            state="disabled",
        )
        self.btn_send.pack(side="left", padx=(0, 8))

        self.btn_print = ctk.CTkButton(
            btn_row, text="Print Selected", width=130, height=38,
            fg_color=WHITE, hover_color=BLUE_LIGHT,
            text_color=BLUE, corner_radius=10,
            border_color=BLUE, border_width=1,
            font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
            command=self._print_clicked,
            state="disabled",
        )
        self.btn_print.pack(side="left", padx=(0, 8))

        self.lbl_print_count = ctk.CTkLabel(
            btn_row, text="",
            font=ctk.CTkFont(family="Segoe UI", size=10),
            text_color=GRAY,
        )
        self.lbl_print_count.pack(side="left")

        self.btn_cancel = ctk.CTkButton(
            btn_row, text="Cancel", width=80, height=38,
            fg_color=WHITE, hover_color=BLUE_LIGHT,
            text_color=GRAY, corner_radius=10,
            border_color=BORDER, border_width=1,
            font=ctk.CTkFont(family="Segoe UI", size=12),
            command=self._cancel_session_clicked,
        )
        self.btn_cancel.pack(side="right")

    def _build_log_frame(self):
        self.log_card = ctk.CTkFrame(self, fg_color=WHITE, corner_radius=12,
                                     border_width=1, border_color=BORDER)
        self.log_card.pack(fill="both", expand=True, padx=16, pady=(8, 8))

        self.log_text = scrolledtext.ScrolledText(
            self.log_card, state="disabled", wrap="word", height=4,
            font=("Consolas", 10), bg=BG, fg=DARK,
            relief="flat", bd=0,
            selectbackground=BLUE, selectforeground=WHITE,
            highlightthickness=0,
        )
        self.log_text.pack(fill="both", expand=True, padx=10, pady=10)

        self.log_text.tag_configure("error", foreground="#DC2626", font=("Consolas", 10, "bold"))
        self.log_text.tag_configure("success", foreground="#16A34A")
        self.log_text.tag_configure("warning", foreground="#D97706")
        self.log_text.tag_configure("info", foreground=BLUE)

    def _build_status_bar(self):
        bar = ctk.CTkFrame(self, fg_color=WHITE, corner_radius=0, height=26)
        bar.pack(fill="x", side="bottom")
        bar.pack_propagate(False)

        self.lbl_status = ctk.CTkLabel(
            bar, text="  Enter your email to begin",
            font=ctk.CTkFont(family="Segoe UI", size=10),
            text_color=GRAY,
        )
        self.lbl_status.pack(side="left", padx=14)

    # ══════════════════════════════════════
    # Drive connection
    # ══════════════════════════════════════

    def _connect_drive(self):
        creds_path = resolve_path(self.cfg["credentials_file"])
        try:
            self.drive_client = DriveClient(creds_path)
            self.drive_client.authenticate()
            self.log("Connected to Google Drive.", "success")
        except Exception as e:
            self.log(f"ERROR: Google Drive failed: {e}", "error")
            self.after(0, lambda: self._update_status(
                "Drive not connected — print still works", "#D97706"))

    # ══════════════════════════════════════
    # Session management
    # ══════════════════════════════════════

    def _start_session_clicked(self):
        email = self.entry_email.get().strip()
        if not email or "@" not in email or "." not in email:
            self._show_inline_warning("Please enter a valid email address.")
            return

        # Create session folder
        folder_name = make_session_folder(email)
        session_path = os.path.join(self._watch_root, folder_name)
        os.makedirs(session_path, exist_ok=True)

        self._session_folder = folder_name
        self._session_email = email
        self._session_path = session_path
        self._photos = []
        self._print_count = 0

        # Update state for operator sync
        state.set_session(folder_name, email, "active")

        # Switch UI: hide email frame, show session frame
        self.email_frame.pack_forget()
        self.lbl_session_email.configure(text=f"Session: {email}")
        self._update_photo_list()
        self.session_frame.pack(fill="x", padx=16, pady=(10, 0), before=self.log_card)

        self.log(f"Session started for {email}", "success")
        self._update_status(f"Session active — take photos!", BLUE)

    def _cancel_session_clicked(self):
        if self._session_folder:
            state.mark_handled(self._session_folder)
        self._end_session()
        self.log("Session cancelled.", "warning")

    def _end_session(self):
        """Reset state, switch back to email screen. Watcher stays on root."""
        self._session_folder = None
        self._session_email = None
        self._session_path = None
        self._photos = []
        self._print_count = 0

        self.session_frame.pack_forget()
        self.email_frame.pack(fill="x", padx=16, pady=(16, 8), before=self.log_card)
        self.entry_email.delete(0, "end")

        self._update_status("Enter your email to begin", GRAY)

    # ══════════════════════════════════════
    # File queue & photo list
    # ══════════════════════════════════════

    def _on_new_file(self, file_path):
        self._file_queue.put(file_path)

    def _poll_file_queue(self):
        max_photos = int(self.cfg.get("max_photos_per_session", 10))
        while not self._file_queue.empty():
            file_path = self._file_queue.get_nowait()
            file_name = os.path.basename(file_path)

            # Only process files in the root photos/ folder (not subfolders)
            if os.path.dirname(file_path) != self._watch_root:
                continue

            # No active session — ignore the photo
            if not self._session_path:
                self.log(f"No session active, ignoring: {file_name}", "warning")
                continue

            if len(self._photos) >= max_photos:
                self.log(f"Max photos ({max_photos}) reached, ignoring.", "warning")
                continue

            # Move file from root to session subfolder
            dest = os.path.join(self._session_path, file_name)
            try:
                shutil.move(file_path, dest)
            except OSError as e:
                self.log(f"Failed to move {file_name}: {e}", "error")
                continue

            self._photos.append(dest)
            self.log(f"Photo added: {file_name}", "info")
            self.after(0, self._update_photo_list)
            self.bell()
        self.after(200, self._poll_file_queue)

    def _make_thumbnail(self, file_path, size=100):
        """Create a thumbnail CTkImage from a file path."""
        try:
            img = PILImage.open(file_path)
            img.thumbnail((size, size), PILImage.LANCZOS)
            return ctk.CTkImage(light_image=img, size=(img.width, img.height))
        except Exception:
            return None

    def _update_photo_list(self):
        """Rebuild thumbnail grid with checkboxes and update button states."""
        max_photos = int(self.cfg.get("max_photos_per_session", 10))
        count = len(self._photos)

        self.lbl_photo_count.configure(text=f"{count}/{max_photos} photos")

        # Clear old thumbnails
        for widget in self.photo_scroll.winfo_children():
            widget.destroy()
        self._photo_checkboxes = []
        self._thumb_refs = []

        COLS = 4
        for i, path in enumerate(self._photos):
            row_idx = i // COLS
            col_idx = i % COLS

            # Card per photo
            card = ctk.CTkFrame(self.photo_scroll, fg_color=BG, corner_radius=8)
            card.grid(row=row_idx, column=col_idx, padx=4, pady=4, sticky="n")

            # Thumbnail
            thumb = self._make_thumbnail(path)
            if thumb:
                self._thumb_refs.append(thumb)
                ctk.CTkLabel(card, image=thumb, text="").pack(padx=4, pady=(4, 2))

            # Checkbox
            var = ctk.BooleanVar(value=False)
            cb = ctk.CTkCheckBox(
                card,
                text=os.path.basename(path)[:12],
                variable=var,
                font=ctk.CTkFont(family="Segoe UI", size=9),
                text_color=DARK, fg_color=BLUE, hover_color=BLUE_HOVER,
                border_color=BORDER, corner_radius=4, width=20,
                command=self._on_checkbox_changed,
            )
            cb.pack(padx=4, pady=(0, 4))
            self._photo_checkboxes.append((cb, var, path))

        # Enable/disable buttons
        self.btn_send.configure(state="normal" if count > 0 else "disabled")
        self.btn_print.configure(state="disabled")
        self._on_checkbox_changed()

    def _on_checkbox_changed(self):
        """Enable Print only when exactly 4 photos are selected."""
        selected = sum(1 for _, var, _ in self._photo_checkboxes if var.get())
        remaining = 4 - selected

        if self._print_count > 0:
            self.btn_print.configure(state="disabled")
            self.lbl_print_count.configure(text="(already printed)", text_color=GRAY)
        elif selected == 4:
            self.btn_print.configure(state="normal")
            self.lbl_print_count.configure(text="(4 selected — ready!)", text_color=BLUE)
        elif selected > 4:
            self.btn_print.configure(state="disabled")
            self.lbl_print_count.configure(text=f"(too many — select exactly 4)", text_color="#D97706")
        else:
            self.btn_print.configure(state="disabled")
            self.lbl_print_count.configure(text=f"(select {remaining} more)", text_color=GRAY)

    # ══════════════════════════════════════
    # Send
    # ══════════════════════════════════════

    def _send_clicked(self):
        self.btn_send.configure(state="disabled")
        self.btn_cancel.configure(state="disabled")
        self._update_status("Uploading & sending...", BLUE)
        threading.Thread(
            target=self._do_send, daemon=True,
        ).start()

    def _do_send(self):
        email = self._session_email
        folder_name = self._session_folder
        file_paths = list(self._photos)
        cfg = self.cfg

        # Upload folder to Drive
        parent_id = self._extract_folder_id(cfg.get("google_drive_folder_id", ""))
        try:
            url = self.drive_client.create_folder_and_upload(
                folder_name, file_paths, parent_id,
            )
            self.log(f"Uploaded {len(file_paths)} photos to Drive.", "success")
        except Exception as e:
            self.log(f"ERROR: Upload failed: {e}", "error")
            self.after(0, lambda: messagebox.showerror("Upload Error", str(e)))
            self.after(0, lambda: self.btn_send.configure(state="normal"))
            self.after(0, lambda: self.btn_cancel.configure(state="normal"))
            return

        # Send email
        try:
            body = cfg["email_body_template"].format(url=url)
            send_photo_email(
                smtp_host=cfg["smtp_host"], smtp_port=cfg["smtp_port"],
                sender=cfg["sender_email"], password=cfg["sender_password"],
                recipient=email, subject=cfg["email_subject"],
                body=body,
            )
            self.log(f"Email sent to {email}!", "success")
        except Exception as e:
            self.log(f"ERROR: Email failed: {e}", "error")
            self.after(0, lambda: messagebox.showerror("Email Error", str(e)))
            self.after(0, lambda: self.btn_send.configure(state="normal"))
            self.after(0, lambda: self.btn_cancel.configure(state="normal"))
            return

        self.log(f"Done! {len(file_paths)} photos sent to {email}.", "success")
        state.mark_handled(folder_name)
        self.after(0, self._end_session)

    # ══════════════════════════════════════
    # Print
    # ══════════════════════════════════════

    def _print_clicked(self):
        printer_name = self.cfg.get("printer_name", "")
        if not printer_name or printer_name == "No printer found":
            messagebox.showerror("Print Error", "No printer configured.")
            return

        selected = [path for _, var, path in self._photo_checkboxes if var.get()]
        if len(selected) != 4:
            return

        self.btn_print.configure(state="disabled")
        self._update_status("Printing 2x2 grid...", BLUE)
        threading.Thread(
            target=self._do_print, args=(selected, printer_name), daemon=True,
        ).start()

    def _do_print(self, file_paths, printer_name):
        names = [os.path.basename(p) for p in file_paths]
        try:
            print_grid_2x2(file_paths, printer_name)
            self.log(f"Printed 2x2 grid: {', '.join(names)}", "success")
        except Exception as e:
            self.log(f"ERROR: Print failed: {e}", "error")
            self.after(0, lambda: messagebox.showerror("Print Error", str(e)))
        self._print_count += 1
        self.after(0, self._update_photo_list)

    # ══════════════════════════════════════
    # State sync with operator
    # ══════════════════════════════════════

    def _poll_state(self):
        if self._session_folder:
            session, email, status = state.get_session()
            if session == self._session_folder and status == "handled":
                self.log("Session handled by operator.", "info")
                self._end_session()
        self.after(500, self._poll_state)

    # ══════════════════════════════════════
    # Helpers
    # ══════════════════════════════════════

    @staticmethod
    def _extract_folder_id(value):
        match = re.search(r"folders/([a-zA-Z0-9_-]+)", value)
        return match.group(1) if match else value.strip()

    def _update_status(self, text, color=None):
        if color is None:
            color = GRAY
        self.lbl_status.configure(text=f"  {text}", text_color=color)

    def _show_inline_warning(self, message):
        self.log(message, "warning")
        self._update_status(message, "#D97706")
        self.entry_email.configure(border_color="#DC2626")
        self.after(1500, lambda: self.entry_email.configure(border_color=BORDER))

    def log(self, message, tag="info"):
        timestamp = datetime.now().strftime("%H:%M:%S")
        self._log_queue.put((f"[{timestamp}]  {message}", tag))

    def _poll_log_queue(self):
        while not self._log_queue.empty():
            msg, tag = self._log_queue.get_nowait()
            self.log_text.config(state="normal")
            self.log_text.insert("end", msg + "\n", tag)
            self.log_text.see("end")
            self.log_text.config(state="disabled")
        self.after(100, self._poll_log_queue)

    def run(self):
        self.mainloop()
        if self.observer:
            self.observer.stop()


if __name__ == "__main__":
    UserApp().run()
