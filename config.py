import base64
import json
import os
import sys

_OBFUSCATED_PREFIX = "b64:"

CONFIG_FILE = "config.json"

DEFAULTS = {
    "watch_folder": "./photos",
    "google_drive_folder_id": "",
    "credentials_file": "./credentials.json",
    "smtp_host": "smtp.gmail.com",
    "smtp_port": 465,
    "sender_email": "",
    "sender_password": "",
    "printer_name": "",
    "max_photos_per_session": 10,
    "max_prints_per_session": 1,
    "cleanup_days": 30,
    "email_subject": "Your Photobooth Photos!",
    "email_body_template": "Here are your photos!\n\nView: {url}\n\nEnjoy!",
}


def _config_path():
    """Return absolute path to config.json next to the executable/script."""
    base = os.path.dirname(os.path.abspath(sys.argv[0]))
    return os.path.join(base, CONFIG_FILE)


def _encode_password(plain):
    """Encode a password to base64 for storage."""
    if not plain or plain.startswith(_OBFUSCATED_PREFIX):
        return plain
    encoded = base64.b64encode(plain.encode("utf-8")).decode("utf-8")
    return _OBFUSCATED_PREFIX + encoded


def _decode_password(stored):
    """Decode a base64-encoded password back to plain text."""
    if not stored or not stored.startswith(_OBFUSCATED_PREFIX):
        return stored
    encoded = stored[len(_OBFUSCATED_PREFIX):]
    return base64.b64decode(encoded.encode("utf-8")).decode("utf-8")


def load_config():
    """Load config from JSON file. Creates default if missing."""
    path = _config_path()
    if not os.path.exists(path):
        save_config(DEFAULTS)
        return dict(DEFAULTS)
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    for key, value in DEFAULTS.items():
        if key not in data:
            data[key] = value
    # Decode password for in-memory use
    data["sender_password"] = _decode_password(data.get("sender_password", ""))
    return data


def save_config(data):
    """Save config dict to JSON file. Password is obfuscated."""
    to_save = dict(data)
    to_save["sender_password"] = _encode_password(to_save.get("sender_password", ""))
    path = _config_path()
    with open(path, "w", encoding="utf-8") as f:
        json.dump(to_save, f, indent=4, ensure_ascii=False)


def cleanup_old_sessions(watch_folder, max_age_days):
    """Delete session subfolders older than max_age_days."""
    import shutil
    import time
    if not os.path.isdir(watch_folder):
        return
    now = time.time()
    cutoff = now - (max_age_days * 86400)
    for entry in os.scandir(watch_folder):
        if entry.is_dir() and entry.stat().st_mtime < cutoff:
            shutil.rmtree(entry.path, ignore_errors=True)
