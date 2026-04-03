"""Shared state between operator and user apps via a small JSON file.

Tracks the current session so both apps stay in sync.
"""
import json
import os
import sys

_STATE_FILE = "state.json"


def _state_path():
    base = os.path.dirname(os.path.abspath(sys.argv[0]))
    return os.path.join(base, _STATE_FILE)


def set_session(session_folder, email, status="active"):
    """Set the current session info."""
    data = {"session": session_folder, "email": email, "status": status}
    with open(_state_path(), "w", encoding="utf-8") as f:
        json.dump(data, f)


def get_session():
    """Return (session_folder, email, status) or ("", "", "") if none."""
    path = _state_path()
    if not os.path.exists(path):
        return "", "", ""
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data.get("session", ""), data.get("email", ""), data.get("status", "")
    except (json.JSONDecodeError, OSError):
        return "", "", ""


def mark_handled(session_folder):
    """Mark a session as handled (sent or skipped)."""
    path = _state_path()
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError, FileNotFoundError):
        data = {}
    data["session"] = session_folder
    data["status"] = "handled"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f)


def clear():
    """Clear the state."""
    with open(_state_path(), "w", encoding="utf-8") as f:
        json.dump({"session": "", "email": "", "status": ""}, f)
