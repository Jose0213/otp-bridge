"""Relay mode: receive messages through an ntfy topic instead of an open port.

The PC only makes an outbound connection, so this works from anywhere without
firewall rules or a VPN. Anyone who knows the topic URL can read and post to it,
so the topic name is long and random; self-host ntfy if you want more control.
"""
import json
import logging
import threading
import time
import urllib.request

from .extract import extract_code

log = logging.getLogger("otp_bridge")


def _listen(topic_url: str, on_code):
    url = topic_url.rstrip("/") + "/json"
    backoff = 2
    while True:
        try:
            with urllib.request.urlopen(url, timeout=90) as resp:  # ntfy sends keepalives every ~45s
                log.info("relay connected")
                backoff = 2
                for line in resp:
                    event = json.loads(line)
                    if event.get("event") != "message":
                        continue
                    text = event.get("message", "")
                    sender = event.get("title") or None
                    try:  # the phone may send {"text":..., "sender":...} as the body
                        payload = json.loads(text)
                        text, sender = str(payload.get("text", "")), payload.get("sender") or sender
                    except (ValueError, AttributeError):
                        pass
                    code = extract_code(text)
                    if code:
                        on_code(code, sender)
        except Exception as e:
            log.warning("relay disconnected: %s; retrying in %ss", e, backoff)
            time.sleep(backoff)
            backoff = min(backoff * 2, 60)


def start(topic_url: str, on_code):
    threading.Thread(target=_listen, args=(topic_url, on_code), daemon=True, name="relay").start()
