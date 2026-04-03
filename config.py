import json
import os
import sys

CONFIG_FILE = "config.json"

DEFAULTS = {
    "watch_folder": "./photos",
    "google_drive_folder_id": "",
    "credentials_file": "./credentials.json",
    "smtp_host": "smtp.gmail.com",
    "smtp_port": 465,
    "sender_email": "",
    "sender_password": "",
    "email_subject": "Your Photobooth Photo!",
    "email_body_template": "Here is your photo!\n\nView: {url}\n\nEnjoy!",
}


def _config_path():
    """Return absolute path to config.json next to the executable/script."""
    base = os.path.dirname(os.path.abspath(sys.argv[0]))
    return os.path.join(base, CONFIG_FILE)


def load_config():
    """Load config from JSON file. Creates default if missing."""
    path = _config_path()
    if not os.path.exists(path):
        save_config(DEFAULTS)
        return dict(DEFAULTS)
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    # Fill in any missing keys with defaults
    for key, value in DEFAULTS.items():
        if key not in data:
            data[key] = value
    return data


def save_config(data):
    """Save config dict to JSON file."""
    path = _config_path()
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)
