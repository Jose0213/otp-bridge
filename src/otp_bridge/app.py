"""Tray app: holds the latest code, copies it, and types it on the hotkey."""
import logging
import os
import threading
import time

import pyperclip
import pystray
from PIL import Image, ImageDraw

from . import config, relay, server, setup_info, win

log = logging.getLogger("otp_bridge")


def _icon_image():
    img = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle((4, 12, 60, 52), radius=10, fill=(37, 99, 235))
    for i in range(3):
        x = 16 + i * 16
        d.ellipse((x - 5, 27, x + 5, 37), fill="white")
    return img


class OtpBridge:
    def __init__(self, cfg):
        self.cfg = cfg
        self.lock = threading.Lock()
        self.code = None
        self.received_at = 0.0
        self.saved_clipboard = None
        self.icon = None
        self.hotkey_ok = False
        self.latest = server.LatestCode(cfg["ttl_seconds"])  # for the browser extension

    # --- code state -------------------------------------------------------
    def current_code(self):
        with self.lock:
            if self.code and time.monotonic() - self.received_at < self.cfg["ttl_seconds"]:
                return self.code
            return None

    def on_code(self, code, sender):
        with self.lock:
            if code == self.code and time.monotonic() - self.received_at < self.cfg["ttl_seconds"]:
                return  # same text forwarded twice (e.g. two automations matched)
            first = self.code is None or time.monotonic() - self.received_at >= self.cfg["ttl_seconds"]
            self.code, self.received_at = code, time.monotonic()
        log.info("received a %d-character code", len(code))
        self.latest.publish(code)
        try:
            previous = pyperclip.paste()
            if first:
                self.saved_clipboard = previous
            pyperclip.copy(code)
        except pyperclip.PyperclipException:
            log.exception("clipboard unavailable")
        hint = f" · {self.cfg['hotkey'].upper()} to type it" if self.hotkey_ok else ""
        self.notify(f"{code} copied{hint}", f"Code from {sender}" if sender else "One-time code")
        threading.Timer(self.cfg["ttl_seconds"], self._expire, args=(code,)).start()

    def _expire(self, code):
        with self.lock:
            if self.code != code or time.monotonic() - self.received_at < self.cfg["ttl_seconds"] - 1:
                return
            self.code = None
            saved, self.saved_clipboard = self.saved_clipboard, None
        self.latest.clear(code)
        if not self.cfg["restore_clipboard"]:
            return
        try:
            if pyperclip.paste() == code:
                pyperclip.copy(saved or "")
        except pyperclip.PyperclipException:
            pass

    # --- actions ----------------------------------------------------------
    def type_code(self):
        code = self.current_code()
        if not code:
            self.notify("No recent code", "OTP Bridge")
            return
        win.wait_for_modifiers_released()
        win.type_text(code)

    def copy_code(self):
        code = self.current_code()
        if code:
            pyperclip.copy(code)
        else:
            self.notify("No recent code", "OTP Bridge")

    def copy_extension_key(self):
        pyperclip.copy(self.cfg["extension_key"])
        self.notify("Paste it into the OTP Bridge browser extension's options page.", "Pairing key copied")

    def notify(self, message, title):
        if self.icon:
            try:
                self.icon.notify(message, title)
            except Exception:
                log.exception("notification failed")

    # --- run --------------------------------------------------------------
    def run(self):
        server.start(self.cfg, self.on_code, self.latest)
        if self.cfg.get("relay_url"):
            relay.start(self.cfg["relay_url"], self.on_code)
        self.hotkey_ok = win.listen_hotkey(self.cfg["hotkey"], self.type_code)

        def from_tray(fn):  # don't block the tray's message loop
            return lambda icon, item: threading.Thread(target=fn, daemon=True).start()

        menu = pystray.Menu(
            pystray.MenuItem("Copy latest code", from_tray(self.copy_code), default=True),
            pystray.MenuItem(lambda item: f"Hotkey: {self.cfg['hotkey'].upper()}"
                             + ("" if self.hotkey_ok else " (unavailable)"), None, enabled=False),
            pystray.MenuItem("Phone setup…", lambda: os.startfile(setup_info.write_page(self.cfg))),
            pystray.MenuItem("Copy browser pairing key", from_tray(self.copy_extension_key)),
            pystray.MenuItem("Open settings folder", lambda: os.startfile(config.config_dir())),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Quit", lambda icon: icon.stop()),
        )
        self.icon = pystray.Icon("otp-bridge", _icon_image(), "OTP Bridge", menu)
        self.icon.run()
