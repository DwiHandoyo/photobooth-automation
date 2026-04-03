"""Photobooth User App — simplified interface for end users.

Only shows: photo notification, email input, Upload & Send, Print, Skip.
All configuration is done by the operator via main.py.
"""
import os
import re
import sys
import threading
import queue

import customtkinter as ctk
from tkinter import messagebox, scrolledtext
from datetime import datetime

from config import load_config
from watcher import start_watching
from drive_upload import DriveClient
from mailer import send_photo_email
from printer import list_printers, print_image
import state


ctk.set_appearance_mode("light")
ctk.set_default_color_theme("blue")

# ── Palette (same as operator app) ──
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


class UserApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Photobooth")
        self.geometry("580x480")
        self.resizable(False, False)
        self.configure(fg_color=BG)

        self.config = load_config()
        self.drive_client = None
        self.observer = None
        self._pending_file_path = None
        self._file_queue = queue.Queue()
        self._log_queue = queue.Queue()

        self._build_header()
        self._build_waiting_label()
        self._build_send_frame()
        self._build_log_frame()
        self._build_status_bar()

        self._poll_log_queue()
        self._poll_file_queue()
        self._poll_state()
        self.after(200, self._auto_start)

    # ── UI ──

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
            header, text="Take a photo and we'll send it to your email!",
            font=ctk.CTkFont(family="Segoe UI", size=11),
            text_color="#BFDBFE",
        ).pack(pady=(0, 8))

    def _build_waiting_label(self):
        self.waiting_label = ctk.CTkLabel(
            self, text="Waiting for photo...",
            font=ctk.CTkFont(family="Segoe UI", size=14),
            text_color=GRAY,
        )
        self.waiting_label.pack(pady=(30, 10))

    def _build_send_frame(self):
        self.send_frame = ctk.CTkFrame(
            self, fg_color=BLUE_LIGHT, corner_radius=12,
            border_width=1, border_color=BLUE,
        )
        # Not packed yet — shown when photo detected

        inner = ctk.CTkFrame(self.send_frame, fg_color=BLUE_LIGHT)
        inner.pack(fill="x", padx=20, pady=16)

        ctk.CTkLabel(
            inner, text="New Photo!",
            font=ctk.CTkFont(family="Segoe UI", size=16, weight="bold"),
            text_color=BLUE,
        ).pack(anchor="w")

        self.lbl_filename = ctk.CTkLabel(
            inner, text="",
            font=ctk.CTkFont(family="Segoe UI", size=12),
            text_color=DARK,
        )
        self.lbl_filename.pack(anchor="w", pady=(2, 12))

        # Email row
        email_frame = ctk.CTkFrame(inner, fg_color=BLUE_LIGHT)
        email_frame.pack(fill="x", pady=(0, 8))

        ctk.CTkLabel(
            email_frame, text="Your Email:",
            font=ctk.CTkFont(family="Segoe UI", size=12),
            text_color=DARK,
        ).pack(side="left")

        self.entry_email = ctk.CTkEntry(
            email_frame, width=300,
            fg_color=WHITE, text_color=DARK,
            border_color=BORDER, border_width=1,
            corner_radius=8,
            font=ctk.CTkFont(family="Segoe UI", size=12),
            placeholder_text="email@example.com",
            placeholder_text_color=GRAY,
        )
        self.entry_email.pack(side="left", padx=(8, 0), expand=True, fill="x")

        # Buttons row
        btn_frame = ctk.CTkFrame(inner, fg_color=BLUE_LIGHT)
        btn_frame.pack(fill="x", pady=(4, 0))

        self.btn_send = ctk.CTkButton(
            btn_frame, text="Send to Email", width=150, height=38,
            fg_color=BLUE, hover_color=BLUE_HOVER,
            text_color=WHITE, corner_radius=10,
            font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
            command=self._send_clicked,
        )
        self.btn_send.pack(side="left", padx=(0, 8))

        self.btn_print = ctk.CTkButton(
            btn_frame, text="Print Photo", width=130, height=38,
            fg_color=WHITE, hover_color=BLUE_LIGHT,
            text_color=BLUE, corner_radius=10,
            border_color=BLUE, border_width=1,
            font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
            command=self._print_clicked,
        )
        self.btn_print.pack(side="left", padx=(0, 8))

        self.btn_skip = ctk.CTkButton(
            btn_frame, text="Skip", width=80, height=38,
            fg_color=WHITE, hover_color=BLUE_LIGHT,
            text_color=GRAY, corner_radius=10,
            border_color=BORDER, border_width=1,
            font=ctk.CTkFont(family="Segoe UI", size=12),
            command=self._skip_clicked,
        )
        self.btn_skip.pack(side="left")

    def _build_log_frame(self):
        """Minimal log — only shows important messages."""
        self.log_card = ctk.CTkFrame(self, fg_color=WHITE, corner_radius=12,
                                     border_width=1, border_color=BORDER)
        self.log_card.pack(fill="both", expand=True, padx=16, pady=(8, 8))

        self.log_text = scrolledtext.ScrolledText(
            self.log_card, state="disabled", wrap="word", height=4,
            font=("Consolas", 10),
            bg=BG, fg=DARK,
            relief="flat", bd=0,
            selectbackground=BLUE, selectforeground=WHITE,
            highlightthickness=0,
        )
        self.log_text.pack(fill="both", expand=True, padx=10, pady=10)

        self.log_text.tag_configure("error", foreground="#DC2626",
                                    font=("Consolas", 10, "bold"))
        self.log_text.tag_configure("success", foreground="#16A34A")
        self.log_text.tag_configure("warning", foreground="#D97706")
        self.log_text.tag_configure("info", foreground=BLUE)

    def _build_status_bar(self):
        bar = ctk.CTkFrame(self, fg_color=WHITE, corner_radius=0, height=26)
        bar.pack(fill="x", side="bottom")
        bar.pack_propagate(False)

        self.lbl_status = ctk.CTkLabel(
            bar, text="  Starting...",
            font=ctk.CTkFont(family="Segoe UI", size=10),
            text_color=GRAY,
        )
        self.lbl_status.pack(side="left", padx=14)

    # ── Auto start ──

    def _auto_start(self):
        """Connect to Drive and start watcher automatically using saved config."""
        # Start watcher first — photo detection should always work
        watch_folder = resolve_path(self.config["watch_folder"])
        self.observer = start_watching(watch_folder, self._on_new_file)
        self.log(f"Watching: {watch_folder}", "info")

        # Connect to Drive in background so UI doesn't freeze
        threading.Thread(target=self._connect_drive, daemon=True).start()

    def _connect_drive(self):
        """Connect to Google Drive (runs in background thread)."""
        creds_path = resolve_path(self.config["credentials_file"])
        try:
            self.drive_client = DriveClient(creds_path)
            self.drive_client.authenticate()
            self.log("Connected to Google Drive.", "success")
            self.after(0, lambda: self._update_status("Ready! Waiting for photo...", BLUE))
        except Exception as e:
            self.log(f"ERROR: Google Drive failed: {e}", "error")
            self.after(0, lambda: self._update_status(
                "Drive not connected — print still works", "#D97706"))

    # ── File queue ──

    def _on_new_file(self, file_path):
        self._file_queue.put(file_path)

    def _poll_file_queue(self):
        while not self._file_queue.empty():
            file_path = self._file_queue.get_nowait()
            self._pending_file_path = file_path
            file_name = os.path.basename(file_path)
            state.clear()
            self.log(f"New photo: {file_name}", "info")
            self._show_send_panel(file_name)
        self.after(200, self._poll_file_queue)

    def _poll_state(self):
        """Check if the operator app already handled the current photo."""
        if self._pending_file_path:
            handled = state.get_handled()
            pending = os.path.basename(self._pending_file_path)
            if handled == pending:
                self.log("Handled by operator.", "info")
                self._pending_file_path = None
                self._hide_send_panel()
        self.after(500, self._poll_state)

    # ── Show / hide panel ──

    def _show_send_panel(self, file_name):
        self.waiting_label.pack_forget()
        self.lbl_filename.configure(text=file_name)
        self.entry_email.delete(0, "end")
        self.btn_send.configure(state="normal")
        self.btn_print.configure(state="normal")
        self.send_frame.pack(fill="x", padx=16, pady=(10, 0),
                             before=self.log_card)
        self._update_status(f"Photo ready: {file_name}", BLUE)
        self.bell()
        self.focus_force()
        self.entry_email.focus()

    def _hide_send_panel(self):
        self.send_frame.pack_forget()
        self._pending_file_path = None
        self.waiting_label.pack(pady=(30, 10),
                                before=self.log_card)
        self._update_status("Waiting for photo...", BLUE)

    # ── Actions ──

    def _send_clicked(self):
        email = self.entry_email.get().strip()
        if not email:
            self._show_inline_warning("Please enter your email address.")
            return
        if "@" not in email or "." not in email:
            self._show_inline_warning("Please enter a valid email address.")
            return
        self.btn_send.configure(state="disabled")
        self._update_status(f"Sending to {email}...", BLUE)
        threading.Thread(
            target=self._do_send, args=(email,), daemon=True,
        ).start()

    def _do_send(self, recipient_email):
        file_path = self._pending_file_path
        file_name = os.path.basename(file_path)
        cfg = self.config

        # Upload
        folder_id = self._extract_folder_id(cfg.get("google_drive_folder_id", ""))
        try:
            url = self.drive_client.upload_and_share(file_path, folder_id)
            self.log(f"Uploaded to Drive.", "success")
        except Exception as e:
            self.log(f"ERROR: Upload failed: {e}", "error")
            self.after(0, lambda: messagebox.showerror("Upload Error", str(e)))
            self.after(0, lambda: self.btn_send.configure(state="normal"))
            return

        # Email
        try:
            body = cfg["email_body_template"].format(url=url)
            send_photo_email(
                smtp_host=cfg["smtp_host"], smtp_port=cfg["smtp_port"],
                sender=cfg["sender_email"], password=cfg["sender_password"],
                recipient=recipient_email, subject=cfg["email_subject"],
                body=body,
            )
            self.log(f"Email sent to {recipient_email}!", "success")
        except Exception as e:
            self.log(f"ERROR: Email failed: {e}", "error")
            self.after(0, lambda: messagebox.showerror("Email Error", str(e)))
            self.after(0, lambda: self.btn_send.configure(state="normal"))
            return

        self.log(f"Done: {file_name}", "success")
        state.mark_handled(file_name)
        self._pending_file_path = None
        self.after(0, self._hide_send_panel)

    def _print_clicked(self):
        printer_name = self.config.get("printer_name", "")
        if not printer_name or printer_name == "No printer found":
            messagebox.showerror("Print Error", "No printer configured.")
            return
        self.btn_print.configure(state="disabled")
        self._update_status("Printing...", BLUE)
        threading.Thread(
            target=self._do_print, args=(printer_name,), daemon=True,
        ).start()

    def _do_print(self, printer_name):
        file_path = self._pending_file_path
        file_name = os.path.basename(file_path)
        try:
            print_image(file_path, printer_name)
            self.log(f"Printed: {file_name}", "success")
        except Exception as e:
            self.log(f"ERROR: Print failed: {e}", "error")
            self.after(0, lambda: messagebox.showerror("Print Error", str(e)))
        self.after(0, lambda: self.btn_print.configure(state="normal"))

    def _skip_clicked(self):
        if self._pending_file_path:
            state.mark_handled(os.path.basename(self._pending_file_path))
            self._pending_file_path = None
        self.log(f"Skipped.", "warning")
        self._hide_send_panel()

    # ── Helpers ──

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
        full_msg = f"[{timestamp}]  {message}"
        self._log_queue.put((full_msg, tag))

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
