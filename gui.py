import customtkinter as ctk
from tkinter import filedialog, messagebox, scrolledtext
from datetime import datetime
import queue


ctk.set_appearance_mode("light")
ctk.set_default_color_theme("blue")

# ── 3-color palette ──
BLUE = "#3B82F6"
BLUE_HOVER = "#2563EB"
BLUE_LIGHT = "#EFF6FF"
DARK = "#1E293B"
GRAY = "#94A3B8"
WHITE = "#FFFFFF"
BG = "#F7F8FA"
BORDER = "#E2E8F0"


class App(ctk.CTk):
    def __init__(self, config, on_save, on_start, on_stop, on_send, on_print,
                 on_skip=None, printer_list=None):
        """Create the Photobooth Automation GUI.

        Args:
            config: Dict of current settings.
            on_save: Callback(config_dict) when Save is clicked.
            on_start: Callback() when Start is clicked.
            on_stop: Callback() when Stop is clicked.
            on_send: Callback(email) when Send is clicked with recipient email.
            on_print: Callback() when Print is clicked.
            printer_list: List of available printer names.
        """
        super().__init__()
        self.title("Photobooth Automation")
        self.geometry("700x750")
        self.resizable(False, False)
        self.configure(fg_color=BG)

        self._on_save = on_save
        self._on_start = on_start
        self._on_stop = on_stop
        self._on_send = on_send
        self._on_print = on_print
        self._on_skip = on_skip
        self._printer_list = printer_list or []
        self._log_queue = queue.Queue()
        self._pending_file = None

        self._build_header()
        self._build_settings_frame(config)
        self._build_send_frame()
        self._build_log_frame()
        self._build_status_bar()
        self._poll_log_queue()

    # ── Header ──

    def _build_header(self):
        header = ctk.CTkFrame(self, fg_color=BLUE, corner_radius=0, height=72)
        header.pack(fill="x")
        header.pack_propagate(False)

        ctk.CTkLabel(
            header, text="Photobooth Automation",
            font=ctk.CTkFont(family="Segoe UI", size=18, weight="bold"),
            text_color=WHITE,
        ).pack(pady=(14, 0))

        ctk.CTkLabel(
            header, text="Upload to Drive  &  Send via Email",
            font=ctk.CTkFont(family="Segoe UI", size=11),
            text_color="#BFDBFE",
        ).pack(pady=(0, 10))

    # ── Settings ──

    def _build_settings_frame(self, config):
        card = ctk.CTkFrame(self, fg_color=WHITE, corner_radius=12, border_width=1, border_color=BORDER)
        card.pack(fill="x", padx=16, pady=(14, 8))

        ctk.CTkLabel(
            card, text="Settings",
            font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"),
            text_color=DARK,
        ).pack(anchor="w", padx=18, pady=(14, 6))

        form = ctk.CTkFrame(card, fg_color=WHITE)
        form.pack(fill="x", padx=18, pady=(0, 6))

        self.entries = {}
        fields = [
            ("watch_folder", "Watch Folder", False, True),
            ("google_drive_folder_id", "Drive Folder URL", False, False),
            ("credentials_file", "Credentials File", False, True),
            ("smtp_host", "SMTP Host", False, False),
            ("smtp_port", "SMTP Port", False, False),
            ("sender_email", "Sender Email", False, False),
            ("sender_password", "Sender Password", True, False),
        ]

        for row, (key, label, is_password, has_browse) in enumerate(fields):
            row_frame = ctk.CTkFrame(form, fg_color=WHITE)
            row_frame.pack(fill="x", pady=2)

            ctk.CTkLabel(
                row_frame, text=f"{label}:", width=130, anchor="w",
                font=ctk.CTkFont(family="Segoe UI", size=12),
                text_color=DARK,
            ).pack(side="left")

            entry = ctk.CTkEntry(
                row_frame, width=320,
                show="*" if is_password else "",
                fg_color=BG, text_color=DARK,
                border_color=BORDER, border_width=1,
                corner_radius=8,
                font=ctk.CTkFont(family="Segoe UI", size=12),
                placeholder_text_color=GRAY,
            )
            entry.insert(0, str(config.get(key, "")))
            entry.pack(side="left", padx=(0, 6), expand=True, fill="x")
            self.entries[key] = entry

            if has_browse:
                is_folder = key == "watch_folder"
                ctk.CTkButton(
                    row_frame, text="Browse", width=70,
                    fg_color=WHITE, text_color=BLUE,
                    border_color=BORDER, border_width=1,
                    hover_color=BLUE_LIGHT,
                    corner_radius=8,
                    font=ctk.CTkFont(family="Segoe UI", size=11),
                    command=lambda e=entry, f=is_folder: self._browse(e, f),
                ).pack(side="left")

        # Session settings
        for key, label in [
            ("max_photos_per_session", "Max Photos/Session"),
            ("max_prints_per_session", "Max Prints/Session"),
        ]:
            s_row = ctk.CTkFrame(form, fg_color=WHITE)
            s_row.pack(fill="x", pady=2)

            ctk.CTkLabel(
                s_row, text=f"{label}:", width=130, anchor="w",
                font=ctk.CTkFont(family="Segoe UI", size=12),
                text_color=DARK,
            ).pack(side="left")

            entry = ctk.CTkEntry(
                s_row, width=80,
                fg_color=BG, text_color=DARK,
                border_color=BORDER, border_width=1,
                corner_radius=8,
                font=ctk.CTkFont(family="Segoe UI", size=12),
            )
            entry.insert(0, str(config.get(key, "")))
            entry.pack(side="left", padx=(0, 6))
            self.entries[key] = entry

        # Cleanup dropdown
        cleanup_row = ctk.CTkFrame(form, fg_color=WHITE)
        cleanup_row.pack(fill="x", pady=2)

        ctk.CTkLabel(
            cleanup_row, text="Auto Cleanup:", width=130, anchor="w",
            font=ctk.CTkFont(family="Segoe UI", size=12),
            text_color=DARK,
        ).pack(side="left")

        self.cleanup_var = ctk.StringVar(value=str(config.get("cleanup_days", 30)))
        ctk.CTkOptionMenu(
            cleanup_row, values=["30", "60", "90"],
            variable=self.cleanup_var,
            fg_color=BG, text_color=DARK,
            button_color=BLUE, button_hover_color=BLUE_HOVER,
            dropdown_fg_color=WHITE, dropdown_text_color=DARK,
            dropdown_hover_color=BLUE_LIGHT,
            corner_radius=8, width=80,
            font=ctk.CTkFont(family="Segoe UI", size=12),
        ).pack(side="left", padx=(0, 6))

        ctk.CTkLabel(
            cleanup_row, text="days",
            font=ctk.CTkFont(family="Segoe UI", size=11),
            text_color=GRAY,
        ).pack(side="left")

        # Printer dropdown
        printer_row = ctk.CTkFrame(form, fg_color=WHITE)
        printer_row.pack(fill="x", pady=2)

        ctk.CTkLabel(
            printer_row, text="Printer:", width=130, anchor="w",
            font=ctk.CTkFont(family="Segoe UI", size=12),
            text_color=DARK,
        ).pack(side="left")

        printer_values = self._printer_list if self._printer_list else ["No printer found"]
        saved_printer = config.get("printer_name", "")
        self.printer_var = ctk.StringVar(
            value=saved_printer if saved_printer in printer_values else (
                printer_values[0] if printer_values else ""
            )
        )
        self.printer_dropdown = ctk.CTkOptionMenu(
            printer_row, values=printer_values,
            variable=self.printer_var,
            fg_color=BG, text_color=DARK,
            button_color=BLUE, button_hover_color=BLUE_HOVER,
            dropdown_fg_color=WHITE, dropdown_text_color=DARK,
            dropdown_hover_color=BLUE_LIGHT,
            corner_radius=8, width=320,
            font=ctk.CTkFont(family="Segoe UI", size=12),
        )
        self.printer_dropdown.pack(side="left", padx=(0, 6), expand=True, fill="x")

        # Save & Start / Stop buttons
        btn_row = ctk.CTkFrame(card, fg_color=WHITE)
        btn_row.pack(pady=(10, 14))

        self.btn_start = ctk.CTkButton(
            btn_row, text="Save & Start", width=180, height=40,
            fg_color=BLUE, hover_color=BLUE_HOVER,
            text_color=WHITE, corner_radius=10,
            font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"),
            command=self._save_and_start_clicked,
        )
        self.btn_start.pack(side="left", padx=(0, 10))

        self.btn_stop = ctk.CTkButton(
            btn_row, text="Stop", width=100, height=40,
            fg_color=WHITE, hover_color=BLUE_LIGHT,
            text_color=BLUE, corner_radius=10,
            border_color=BORDER, border_width=1,
            font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"),
            command=self._stop_clicked,
        )
        self.btn_stop.configure(state="disabled")
        self.btn_stop.pack(side="left", padx=(0, 10))

        self.status_dot = ctk.CTkLabel(
            btn_row, text="Idle",
            font=ctk.CTkFont(family="Segoe UI", size=11),
            text_color=GRAY,
        )
        self.status_dot.pack(side="left")

    # ── Send Panel ──

    def _build_send_frame(self):
        """Panel shown when a new photo is detected."""
        self.send_frame = ctk.CTkFrame(
            self, fg_color=BLUE_LIGHT, corner_radius=12,
            border_width=1, border_color=BLUE,
        )

        inner = ctk.CTkFrame(self.send_frame, fg_color=BLUE_LIGHT)
        inner.pack(fill="x", padx=16, pady=12)

        ctk.CTkLabel(
            inner, text="New Photo Detected!",
            font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"),
            text_color=BLUE,
        ).pack(anchor="w")

        self.lbl_filename = ctk.CTkLabel(
            inner, text="",
            font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
            text_color=DARK,
        )
        self.lbl_filename.pack(anchor="w", pady=(2, 8))

        row = ctk.CTkFrame(inner, fg_color=BLUE_LIGHT)
        row.pack(fill="x")

        ctk.CTkLabel(
            row, text="Recipient Email:",
            font=ctk.CTkFont(family="Segoe UI", size=12),
            text_color=DARK,
        ).pack(side="left")

        self.entry_recipient = ctk.CTkEntry(
            row, width=240,
            fg_color=WHITE, text_color=DARK,
            border_color=BORDER, border_width=1,
            corner_radius=8,
            font=ctk.CTkFont(family="Segoe UI", size=12),
            placeholder_text="email@example.com",
            placeholder_text_color=GRAY,
        )
        self.entry_recipient.pack(side="left", padx=(8, 8))

        self.btn_send = ctk.CTkButton(
            row, text="Upload & Send", width=130, height=32,
            fg_color=BLUE, hover_color=BLUE_HOVER,
            text_color=WHITE, corner_radius=8,
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
            command=self._send_clicked,
        )
        self.btn_send.pack(side="left", padx=(0, 6))

        self.btn_skip = ctk.CTkButton(
            row, text="Skip", width=70, height=32,
            fg_color=WHITE, hover_color=BLUE_LIGHT,
            text_color=GRAY, corner_radius=8,
            border_color=BORDER, border_width=1,
            font=ctk.CTkFont(family="Segoe UI", size=11),
            command=self._skip_clicked,
        )
        self.btn_skip.pack(side="left")

        # Print row
        print_row = ctk.CTkFrame(inner, fg_color=BLUE_LIGHT)
        print_row.pack(fill="x", pady=(8, 0))

        self.btn_print = ctk.CTkButton(
            print_row, text="Print Photo", width=160, height=32,
            fg_color=WHITE, hover_color=BLUE_LIGHT,
            text_color=BLUE, corner_radius=8,
            border_color=BLUE, border_width=1,
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
            command=self._print_clicked,
        )
        self.btn_print.pack(side="left")

    # ── Log ──

    def _build_log_frame(self):
        card = ctk.CTkFrame(self, fg_color=WHITE, corner_radius=12, border_width=1, border_color=BORDER)
        card.pack(fill="both", expand=True, padx=16, pady=(6, 8))

        ctk.CTkLabel(
            card, text="Activity Log",
            font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"),
            text_color=DARK,
        ).pack(anchor="w", padx=14, pady=(12, 4))

        # Using tkinter ScrolledText inside CTk frame for colored log tags
        import tkinter as tk
        log_container = ctk.CTkFrame(card, fg_color=WHITE, corner_radius=8)
        log_container.pack(fill="both", expand=True, padx=14, pady=(0, 12))

        self.log_text = scrolledtext.ScrolledText(
            log_container, state="disabled", wrap="word", height=8,
            font=("Consolas", 10),
            bg=BG, fg=DARK,
            relief="flat", bd=0,
            selectbackground=BLUE, selectforeground=WHITE,
            highlightthickness=0,
        )
        self.log_text.pack(fill="both", expand=True, padx=4, pady=4)

        self.log_text.tag_configure("error", foreground="#DC2626", font=("Consolas", 10, "bold"))
        self.log_text.tag_configure("success", foreground="#16A34A")
        self.log_text.tag_configure("warning", foreground="#D97706")
        self.log_text.tag_configure("info", foreground=BLUE)

    # ── Status Bar ──

    def _build_status_bar(self):
        bar = ctk.CTkFrame(self, fg_color=WHITE, corner_radius=0, height=28)
        bar.pack(fill="x", side="bottom")
        bar.pack_propagate(False)

        self.lbl_status = ctk.CTkLabel(
            bar, text="  Ready",
            font=ctk.CTkFont(family="Segoe UI", size=10),
            text_color=GRAY,
        )
        self.lbl_status.pack(side="left", padx=14)

        ctk.CTkLabel(
            bar, text="v1.0",
            font=ctk.CTkFont(family="Segoe UI", size=10),
            text_color=BORDER,
        ).pack(side="right", padx=14)

    # ── Helpers ──

    def _update_status(self, text, color=None):
        if color is None:
            color = GRAY
        self.lbl_status.configure(text=f"  {text}", text_color=color)

    def show_send_panel(self, file_name):
        """Show the send panel for a new photo."""
        self._pending_file = file_name
        self.lbl_filename.configure(text=file_name)
        self.entry_recipient.delete(0, "end")
        self.btn_send.configure(state="normal")
        self.send_frame.pack(
            fill="x", padx=16, pady=(6, 0), before=self.log_text.master.master.master
        )
        self._update_status(f"New photo: {file_name}", BLUE)
        self.bell()
        self.focus_force()
        self.entry_recipient.focus()

    def hide_send_panel(self):
        """Hide the send panel after sending or skipping."""
        self.send_frame.pack_forget()
        self._pending_file = None
        self._update_status("Watching for photos...", BLUE)

    def _send_clicked(self):
        email = self.entry_recipient.get().strip()
        if not email:
            self._show_inline_warning("Please enter a recipient email address.")
            return
        if "@" not in email or "." not in email:
            self._show_inline_warning("Please enter a valid email address.")
            return
        self.btn_send.configure(state="disabled")
        self._update_status(f"Sending to {email}...", BLUE)
        self._on_send(email)

    def _skip_clicked(self):
        self.log(f"Skipped: {self._pending_file}", "warning")
        if self._on_skip:
            self._on_skip()
        self.hide_send_panel()

    def _browse(self, entry, is_folder):
        if is_folder:
            path = filedialog.askdirectory()
        else:
            path = filedialog.askopenfilename(
                filetypes=[("JSON files", "*.json"), ("All files", "*.*")]
            )
        if path:
            entry.delete(0, "end")
            entry.insert(0, path)

    def _print_clicked(self):
        self.btn_print.configure(state="disabled")
        self._update_status("Printing...", BLUE)
        self._on_print()

    def _save_and_start_clicked(self):
        data = {key: entry.get() for key, entry in self.entries.items()}
        data["printer_name"] = self.printer_var.get()
        data["cleanup_days"] = int(self.cleanup_var.get())
        self._on_save(data)
        self.log("Settings saved.", "success")
        self.btn_start.configure(state="disabled")
        self.btn_stop.configure(state="normal")
        self.status_dot.configure(text="Watching...", text_color=BLUE)
        self._update_status("Watching for new photos...", BLUE)
        self._on_start()

    def _stop_clicked(self):
        self.btn_stop.configure(state="disabled")
        self.btn_start.configure(state="normal")
        self.status_dot.configure(text="Idle", text_color=GRAY)
        self._update_status("Stopped", GRAY)
        self._on_stop()

    def log(self, message, tag="info"):
        """Thread-safe logging with color tags."""
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

    def show_error(self, title, message):
        """Show error as both a dialog and a highlighted log entry."""
        self.log(f"ERROR: {message}", "error")
        self._update_status(f"Error: {title}", "#DC2626")
        messagebox.showerror(title, message)

    def show_warning(self, title, message):
        """Show warning as both a dialog and a highlighted log entry."""
        self.log(f"WARNING: {message}", "warning")
        self._update_status(f"Warning: {title}", "#D97706")
        messagebox.showwarning(title, message)

    def _show_inline_warning(self, message):
        """Show a non-blocking inline warning in the log instead of a popup."""
        self.log(message, "warning")
        self._update_status(message, "#D97706")
        self.entry_recipient.configure(border_color="#DC2626")
        self.after(1500, lambda: self.entry_recipient.configure(border_color=BORDER))

    def get_config(self):
        """Return current values from the form as a dict."""
        data = {key: entry.get() for key, entry in self.entries.items()}
        data["printer_name"] = self.printer_var.get()
        data["cleanup_days"] = int(self.cleanup_var.get())
        return data
