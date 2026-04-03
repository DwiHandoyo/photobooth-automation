import os
import certifi
os.environ["SSL_CERT_FILE"] = certifi.where()

from google.auth.transport.requests import Request
from google.auth.exceptions import RefreshError
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

SCOPES = ["https://www.googleapis.com/auth/drive"]
TOKEN_FILE = "token.json"


class DriveClient:
    """Google Drive client with automatic token refresh and re-auth."""

    def __init__(self, credentials_path):
        self.credentials_path = credentials_path
        self.token_path = os.path.join(os.path.dirname(credentials_path), TOKEN_FILE)
        self.creds = None
        self.service = None

    def authenticate(self):
        """Authenticate with Google Drive. Opens browser on first run."""
        self.creds = None

        if os.path.exists(self.token_path):
            self.creds = Credentials.from_authorized_user_file(self.token_path, SCOPES)

        if not self.creds or not self.creds.valid:
            self._refresh_or_login()

        self.service = build("drive", "v3", credentials=self.creds)

    def _refresh_or_login(self):
        """Try to refresh token, or start a new login flow."""
        if self.creds and self.creds.expired and self.creds.refresh_token:
            try:
                self.creds.refresh(Request())
                self._save_token()
                return
            except RefreshError:
                pass  # Token invalid, fall through to login

        flow = InstalledAppFlow.from_client_secrets_file(self.credentials_path, SCOPES)
        self.creds = flow.run_local_server(port=0)
        self._save_token()

    def _save_token(self):
        with open(self.token_path, "w") as f:
            f.write(self.creds.to_json())

    def ensure_valid(self):
        """Check token is still valid before an upload, refresh if needed."""
        if not self.creds or not self.creds.valid:
            self._refresh_or_login()
            self.service = build("drive", "v3", credentials=self.creds)

    def upload_and_share(self, file_path, folder_id):
        """Upload a file to Google Drive and return a shareable URL."""
        self.ensure_valid()

        file_name = os.path.basename(file_path)

        ext = os.path.splitext(file_name)[1].lower()
        mime_types = {
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".png": "image/png",
            ".bmp": "image/bmp",
            ".tiff": "image/tiff",
            ".tif": "image/tiff",
            ".gif": "image/gif",
        }
        mime_type = mime_types.get(ext, "application/octet-stream")

        file_metadata = {"name": file_name}
        if folder_id:
            file_metadata["parents"] = [folder_id]

        media = MediaFileUpload(file_path, mimetype=mime_type, resumable=True)
        uploaded = (
            self.service.files()
            .create(body=file_metadata, media_body=media, fields="id")
            .execute()
        )
        file_id = uploaded["id"]

        self.service.permissions().create(
            fileId=file_id,
            body={"type": "anyone", "role": "reader"},
        ).execute()

        return f"https://drive.google.com/file/d/{file_id}/view?usp=sharing"

    def create_folder_and_upload(self, folder_name, file_paths, parent_folder_id):
        """Create a Drive folder, upload all files into it, share it, return folder URL.

        Args:
            folder_name: Name for the new Drive folder.
            file_paths: List of local file paths to upload.
            parent_folder_id: Parent folder ID in Drive.

        Returns:
            Shareable URL of the created Drive folder.
        """
        self.ensure_valid()

        # Create folder
        folder_metadata = {
            "name": folder_name,
            "mimeType": "application/vnd.google-apps.folder",
        }
        if parent_folder_id:
            folder_metadata["parents"] = [parent_folder_id]

        folder = (
            self.service.files()
            .create(body=folder_metadata, fields="id")
            .execute()
        )
        drive_folder_id = folder["id"]

        # Upload each file into the folder
        mime_types = {
            ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
            ".png": "image/png", ".bmp": "image/bmp",
            ".tiff": "image/tiff", ".tif": "image/tiff",
            ".gif": "image/gif",
        }

        for file_path in file_paths:
            file_name = os.path.basename(file_path)
            ext = os.path.splitext(file_name)[1].lower()
            mime_type = mime_types.get(ext, "application/octet-stream")

            file_metadata = {"name": file_name, "parents": [drive_folder_id]}
            media = MediaFileUpload(file_path, mimetype=mime_type, resumable=True)
            self.service.files().create(
                body=file_metadata, media_body=media, fields="id",
            ).execute()

        # Share folder publicly
        self.service.permissions().create(
            fileId=drive_folder_id,
            body={"type": "anyone", "role": "reader"},
        ).execute()

        return f"https://drive.google.com/drive/folders/{drive_folder_id}?usp=sharing"
