"""Shared state between operator and user apps via a small JSON file.

Both apps poll this file to detect when the other has handled a photo.
"""
import json
import os
import sys

_STATE_FILE = "state.json"


def _state_path():
    base = os.path.dirname(os.path.abspath(sys.argv[0]))
    return os.path.join(base, _STATE_FILE)


def mark_handled(file_name):
    """Mark a photo as handled (sent, printed, or skipped)."""
    path = _state_path()
    data = {"handled": file_name}
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f)


def get_handled():
    """Return the last handled filename, or empty string if none."""
    path = _state_path()
    if not os.path.exists(path):
        return ""
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data.get("handled", "")
    except (json.JSONDecodeError, OSError):
        return ""


def clear():
    """Clear the state (called when a new photo is detected)."""
    path = _state_path()
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump({"handled": ""}, f)
    except OSError:
        pass
