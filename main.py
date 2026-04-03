import os
import re
import sys
import threading
import queue

from config import load_config, save_config
from gui import App
from watcher import start_watching
from drive_upload import DriveClient
from mailer import send_photo_email, verify_smtp


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
        self._pending_file_path = None
        self._file_queue = queue.Queue()

        self.app = App(
            config=self.config,
            on_save=self.handle_save,
            on_start=self.handle_start,
            on_stop=self.handle_stop,
            on_send=self.handle_send,
        )
        self._poll_file_queue()

    def handle_save(self, data):
        self.config.update(data)
        save_config(self.config)

    def handle_start(self):
        self.config.update(self.app.get_config())

        creds_path = resolve_path(self.config["credentials_file"])
        try:
            self.drive_client = DriveClient(creds_path)
            self.drive_client.authenticate()
            self.app.log("✅ Google Drive connected.", "success")
        except Exception as e:
            error_msg = f"Failed to connect to Google Drive: {e}"
            self.app.log(f"❌ {error_msg}", "error")
            self.app.show_error("Google Drive Error", error_msg)
            self.app.btn_start.configure(state="normal")
            self.app.btn_stop.configure(state="disabled")
            return

        # Verify SMTP credentials
        try:
            verify_smtp(
                smtp_host=self.config["smtp_host"],
                smtp_port=self.config["smtp_port"],
                sender=self.config["sender_email"],
                password=self.config["sender_password"],
            )
            self.app.log("✅ SMTP credentials verified.", "success")
        except Exception as e:
            error_msg = f"SMTP login failed: {e}\n\nCheck your sender email and app password."
            self.app.log(f"❌ {error_msg}", "error")
            self.app.show_error("SMTP Authentication Error", error_msg)
            self.app.btn_start.configure(state="normal")
            self.app.btn_stop.configure(state="disabled")
            return

        watch_folder = resolve_path(self.config["watch_folder"])
        self.observer = start_watching(watch_folder, self.on_new_file)
        self.app.log(f"👀 Watching folder: {watch_folder}", "info")

    def handle_stop(self):
        if self.observer:
            self.observer.stop()
            self.observer = None
            self.app.log("⏸ Stopped watching.", "warning")

    def on_new_file(self, file_path):
        """Called from watcher thread. Queue the file for the GUI thread."""
        self._file_queue.put(file_path)

    def _poll_file_queue(self):
        """Check for new files from the watcher thread (runs on GUI thread)."""
        while not self._file_queue.empty():
            file_path = self._file_queue.get_nowait()
            file_name = os.path.basename(file_path)
            self._pending_file_path = file_path
            self.app.log(f"📸 New file detected: {file_name}", "info")
            self.app.show_send_panel(file_name)
        self.app.after(200, self._poll_file_queue)

    @staticmethod
    def _extract_folder_id(value):
        """Extract folder ID from a Google Drive URL or return as-is if already an ID."""
        match = re.search(r"folders/([a-zA-Z0-9_-]+)", value)
        return match.group(1) if match else value.strip()

    def handle_send(self, recipient_email):
        """Called when user clicks 'Upload & Send' with a recipient email."""
        if not self._pending_file_path:
            return

        file_path = self._pending_file_path
        file_name = os.path.basename(file_path)

        # Run upload + email in a background thread so GUI stays responsive
        threading.Thread(
            target=self._upload_and_send,
            args=(file_path, file_name, recipient_email),
            daemon=True,
        ).start()

    def _upload_and_send(self, file_path, file_name, recipient_email):
        """Upload to Drive and send email (runs in background thread)."""
        # Step 1: Upload to Google Drive
        folder_id = self._extract_folder_id(self.config.get("google_drive_folder_id", ""))
        try:
            url = self.drive_client.upload_and_share(file_path, folder_id)
            self.app.log(f"📤 Uploaded: {url}", "success")
        except Exception as e:
            error_msg = f"Upload failed: {e}"
            self.app.log(f"❌ {error_msg}", "error")
            self.app.after(0, lambda: self.app.show_error("Upload Error", error_msg))
            self._re_enable_send()
            return

        # Step 2: Send email with the link
        try:
            body = self.config["email_body_template"].format(url=url)
            send_photo_email(
                smtp_host=self.config["smtp_host"],
                smtp_port=self.config["smtp_port"],
                sender=self.config["sender_email"],
                password=self.config["sender_password"],
                recipient=recipient_email,
                subject=self.config["email_subject"],
                body=body,
            )
            self.app.log(f"✉️  Email sent to {recipient_email}", "success")
        except Exception as e:
            error_msg = f"Email send failed: {e}\nBut photo is safe in Drive: {url}"
            self.app.log(f"⚠️  {error_msg}", "warning")
            self.app.after(0, lambda: self.app.show_warning("Email Error", error_msg))
            self._re_enable_send()
            return

        self.app.log(f"✅ Done: {file_name}", "success")
        # Hide send panel on success (must run on GUI thread)
        self.app.after(0, self.app.hide_send_panel)

    def _re_enable_send(self):
        """Re-enable the send button on error so user can retry."""
        self.app.after(0, lambda: self.app.btn_send.configure(state="normal"))

    def run(self):
        self.app.mainloop()
        if self.observer:
            self.observer.stop()


if __name__ == "__main__":
    PhotoboothApp().run()
