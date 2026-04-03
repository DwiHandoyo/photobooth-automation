import os
import re
import sys
import threading
import queue

from config import load_config, save_config, cleanup_old_sessions
from gui import App
from watcher import start_watching
from drive_upload import DriveClient
from mailer import send_photo_email, verify_smtp
from printer import list_printers, print_image
import state


def resolve_path(path):
    """Resolve a path relative to the executable/script directory."""
    if os.path.isabs(path):
        return path
    base = os.path.dirname(os.path.abspath(sys.argv[0]))
    return os.path.join(base, path)


class PhotoboothApp:
    def __init__(self):
        self.config = load_config()
        self.observer = None
        self.drive_client = None
        self._session_folder = None
        self._session_email = None
        self._session_path = None
        self._photos = []
        self._file_queue = queue.Queue()

        try:
            printers = list_printers()
        except Exception:
            printers = []

        self.app = App(
            config=self.config,
            on_save=self.handle_save,
            on_start=self.handle_start,
            on_stop=self.handle_stop,
            on_send=self.handle_send,
            on_print=self.handle_print,
            on_skip=self.handle_skip,
            printer_list=printers,
        )
        self._poll_file_queue()
        self._poll_state()

    def handle_save(self, data):
        self.config.update(data)
        save_config(self.config)

    def handle_start(self):
        self.config.update(self.app.get_config())

        # Cleanup old sessions
        watch_folder = resolve_path(self.config["watch_folder"])
        cleanup_old_sessions(watch_folder, int(self.config.get("cleanup_days", 30)))

        creds_path = resolve_path(self.config["credentials_file"])
        try:
            self.drive_client = DriveClient(creds_path)
            self.drive_client.authenticate()
            self.app.log("Google Drive connected.", "success")
        except Exception as e:
            error_msg = f"Failed to connect to Google Drive: {e}"
            self.app.log(f"ERROR: {error_msg}", "error")
            self.app.show_error("Google Drive Error", error_msg)
            self.app.btn_start.configure(state="normal")
            self.app.btn_stop.configure(state="disabled")
            return

        try:
            verify_smtp(
                smtp_host=self.config["smtp_host"],
                smtp_port=self.config["smtp_port"],
                sender=self.config["sender_email"],
                password=self.config["sender_password"],
            )
            self.app.log("SMTP credentials verified.", "success")
        except Exception as e:
            error_msg = f"SMTP login failed: {e}\n\nCheck your sender email and app password."
            self.app.log(f"ERROR: {error_msg}", "error")
            self.app.show_error("SMTP Authentication Error", error_msg)
            self.app.btn_start.configure(state="normal")
            self.app.btn_stop.configure(state="disabled")
            return

        self._watch_root = watch_folder
        self.observer = start_watching(watch_folder, self.on_new_file, recursive=True)
        self.app.log(f"Watching folder: {watch_folder}", "info")

    def handle_skip(self):
        if self._session_folder:
            state.mark_handled(self._session_folder)
            self._end_session()

    def handle_stop(self):
        if self.observer:
            self.observer.stop()
            self.observer = None
            self.app.log("Stopped watching.", "warning")

    def on_new_file(self, file_path):
        self._file_queue.put(file_path)

    def _poll_file_queue(self):
        """Process new files — only care about files moved into session subfolders."""
        max_photos = int(self.config.get("max_photos_per_session", 10))
        while not self._file_queue.empty():
            file_path = self._file_queue.get_nowait()
            file_name = os.path.basename(file_path)
            parent_dir = os.path.dirname(file_path)
            parent_name = os.path.basename(parent_dir)

            # Ignore files in root photos/ (they'll be moved by user app)
            if parent_dir == getattr(self, "_watch_root", ""):
                continue

            # Pick up active session from state if we don't have one
            if self._session_folder is None:
                session, email, st = state.get_session()
                if session and st == "active":
                    self._session_folder = session
                    self._session_email = email
                    self._session_path = parent_dir
                    self._photos = []

            # Add to session if it matches
            if self._session_folder and parent_name == self._session_folder:
                if len(self._photos) < max_photos:
                    self._photos.append(file_path)
                    count = len(self._photos)
                    self.app.log(f"Photo {count}/{max_photos}: {file_name}", "info")
                    self.app.show_send_panel(
                        f"Session: {self._session_email} — {count}/{max_photos} photos"
                    )

        self.app.after(200, self._poll_file_queue)

    def _poll_state(self):
        """Check if the user app handled the current session."""
        if self._session_folder:
            session, _email, status = state.get_session()
            if session == self._session_folder and status == "handled":
                self.app.log("Session handled by user app.", "info")
                self.app.hide_send_panel()
                self._end_session()
        self.app.after(500, self._poll_state)

    def _end_session(self):
        self._session_folder = None
        self._session_email = None
        self._session_path = None
        self._photos = []

    @staticmethod
    def _extract_folder_id(value):
        match = re.search(r"folders/([a-zA-Z0-9_-]+)", value)
        return match.group(1) if match else value.strip()

    def handle_send(self, recipient_email):
        """Called when operator clicks 'Upload & Send'."""
        if not self._photos:
            return

        email = recipient_email or self._session_email
        if not email:
            return

        threading.Thread(
            target=self._upload_and_send,
            args=(email,),
            daemon=True,
        ).start()

    def _upload_and_send(self, recipient_email):
        folder_name = self._session_folder or "photobooth_upload"
        file_paths = list(self._photos)
        cfg = self.config

        # Upload folder to Drive
        parent_id = self._extract_folder_id(cfg.get("google_drive_folder_id", ""))
        try:
            url = self.drive_client.create_folder_and_upload(
                folder_name, file_paths, parent_id,
            )
            self.app.log(f"Uploaded {len(file_paths)} photos to Drive.", "success")
        except Exception as e:
            error_msg = f"Upload failed: {e}"
            self.app.log(f"ERROR: {error_msg}", "error")
            self.app.after(0, lambda: self.app.show_error("Upload Error", error_msg))
            self._re_enable_send()
            return

        # Send email
        try:
            body = cfg["email_body_template"].format(url=url)
            send_photo_email(
                smtp_host=cfg["smtp_host"], smtp_port=cfg["smtp_port"],
                sender=cfg["sender_email"], password=cfg["sender_password"],
                recipient=recipient_email, subject=cfg["email_subject"],
                body=body,
            )
            self.app.log(f"Email sent to {recipient_email}", "success")
        except Exception as e:
            error_msg = f"Email failed: {e}\nPhotos are safe in Drive: {url}"
            self.app.log(f"WARNING: {error_msg}", "warning")
            self.app.after(0, lambda: self.app.show_warning("Email Error", error_msg))
            self._re_enable_send()
            return

        self.app.log(f"Done! {len(file_paths)} photos sent.", "success")
        if self._session_folder:
            state.mark_handled(self._session_folder)
        self.app.after(0, self.app.hide_send_panel)
        self._end_session()

    def handle_print(self):
        if not self._photos:
            return
        printer_name = self.config.get("printer_name", "")
        if not printer_name or printer_name == "No printer found":
            self.app.show_error("Print Error", "No printer selected.")
            self.app.after(0, lambda: self.app.btn_print.configure(state="normal"))
            return
        file_path = self._photos[-1]
        threading.Thread(
            target=self._do_print,
            args=(file_path, printer_name),
            daemon=True,
        ).start()

    def _do_print(self, file_path, printer_name):
        file_name = os.path.basename(file_path)
        try:
            print_image(file_path, printer_name)
            self.app.log(f"Printed: {file_name}", "success")
        except Exception as e:
            self.app.log(f"ERROR: Print failed: {e}", "error")
            self.app.after(0, lambda: self.app.show_error("Print Error", str(e)))
        self.app.after(0, lambda: self.app.btn_print.configure(state="normal"))

    def _re_enable_send(self):
        self.app.after(0, lambda: self.app.btn_send.configure(state="normal"))

    def run(self):
        self.app.mainloop()
        if self.observer:
            self.observer.stop()


if __name__ == "__main__":
    PhotoboothApp().run()
