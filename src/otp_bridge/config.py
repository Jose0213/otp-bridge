"""Settings, stored as JSON in the user's app-data folder."""
import json
import os
import secrets
from pathlib import Path

DEFAULTS = {
    "port": 9233,
    "bind": "0.0.0.0",
    "hotkey": "ctrl+alt+o",
    # How long a code stays usable (and on the clipboard), in seconds.
    "ttl_seconds": 300,
    # Put the previous clipboard text back once a code expires.
    "restore_clipboard": True,
    # Only accept requests from loopback, private LAN and Tailscale addresses.
    "allow_public_ips": False,
    # Relay mode: an ntfy topic URL (e.g. https://ntfy.sh/otp-...). Empty = direct only.
    "relay_url": "",
}


def config_dir() -> Path:
    base = os.environ.get("APPDATA") or Path.home() / ".config"
    path = Path(base) / "otp-bridge"
    path.mkdir(parents=True, exist_ok=True)
    return path


def save(data: dict):
    (config_dir() / "config.json").write_text(json.dumps(data, indent=2), encoding="utf-8")


def load() -> dict:
    path = config_dir() / "config.json"
    data = {}
    if path.exists():
        data = json.loads(path.read_text(encoding="utf-8"))
    changed = False
    for key, value in DEFAULTS.items():
        if key not in data:
            data[key] = value
            changed = True
    if not data.get("token"):
        data["token"] = secrets.token_urlsafe(24)
        changed = True
    if changed:
        save(data)
    return data
