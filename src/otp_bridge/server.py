"""HTTP endpoint the phone posts incoming text messages to."""
import hmac
import ipaddress
import json
import logging
import threading
import time
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from .extract import extract_code, parse_body

log = logging.getLogger("otp_bridge")

TAILSCALE = ipaddress.ip_network("100.64.0.0/10")
MAX_BODY = 16 * 1024
# GET /latest is for the browser extension on this PC only.
LOOPBACK_HOSTS = {"127.0.0.1", "localhost", "::1"}
EXTENSION_ORIGINS = ("chrome-extension://", "extension://", "moz-extension://")
MAX_WAIT = 30


class LatestCode:
    """The newest code, for the browser extension to long-poll. Memory only."""

    def __init__(self, ttl: float):
        self.ttl = ttl
        self.changed = threading.Condition()
        self.code = None
        self.received_at = 0.0
        self.seq = 0  # bumps on every new code, so a client can wait for the next one

    def publish(self, code: str):
        with self.changed:
            self.code, self.received_at = code, time.monotonic()
            self.seq += 1
            self.changed.notify_all()

    def clear(self, code: str):
        with self.changed:
            if self.code == code:
                self.code = None

    def _fresh(self):
        return self.code is not None and time.monotonic() - self.received_at < self.ttl

    def get(self, after: int = 0, wait: float = 0) -> dict:
        """The current code if its id is newer than `after`, waiting up to `wait` seconds."""
        with self.changed:
            self.changed.wait_for(lambda: self.seq > after and self._fresh(), timeout=wait)
            if self.seq > after and self._fresh():
                return {"code": self.code, "id": self.seq,
                        "age": round(time.monotonic() - self.received_at, 1)}
            return {"code": None, "id": self.seq}


def _is_loopback(ip: str) -> bool:
    try:
        addr = ipaddress.ip_address(ip)
    except ValueError:
        return False
    if addr.version == 6 and addr.ipv4_mapped:
        addr = addr.ipv4_mapped
    return addr.is_loopback


def _query_number(query: dict, name: str, upper: float) -> float:
    try:
        return min(max(float(query.get(name, ["0"])[0]), 0), upper)
    except ValueError:
        return 0


def _ip_allowed(ip: str, allow_public: bool) -> bool:
    if allow_public:
        return True
    try:
        addr = ipaddress.ip_address(ip)
    except ValueError:
        return False
    if addr.version == 6 and addr.ipv4_mapped:
        addr = addr.ipv4_mapped
    return addr.is_loopback or addr.is_private or addr in TAILSCALE


def _body_token(raw: str) -> str:
    """The "token" field of a JSON body (any letter case), or ""."""
    if not raw.lstrip().startswith("{"):
        return ""
    try:
        payload = json.loads(raw)
    except ValueError:
        return ""
    if not isinstance(payload, dict):
        return ""
    for key, value in payload.items():
        if str(key).lower() == "token" and isinstance(value, str):
            return value
    return ""


def make_handler(cfg: dict, on_code, latest: LatestCode = None):
    token = cfg["token"].encode()
    extension_key = (cfg.get("extension_key") or "").encode()

    class Handler(BaseHTTPRequestHandler):
        server_version = "otp-bridge"

        def log_message(self, fmt, *args):  # keep message contents out of logs
            log.debug("%s %s", self.client_address[0], fmt % args)

        def _reply(self, status, body=None):
            data = json.dumps(body or {}).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def _authorized(self, raw: str) -> bool:
            auth = self.headers.get("Authorization", "").strip()
            if auth[:7].lower() == "bearer ":
                supplied = auth[7:]
            else:
                # Some iOS Shortcuts setups silently drop the Authorization header,
                # so the token can also come as a header or as a "token" body field.
                supplied = self.headers.get("X-OTP-Token", "") or _body_token(raw)
            # Phones can add stray spaces or a trailing line break from a Text action.
            supplied = "".join(supplied.split())
            if hmac.compare_digest(supplied.encode(), token):
                return True
            # Describe what arrived without logging any part of a secret.
            scheme = "none" if not auth else ("bearer" if auth[:7].lower() == "bearer " else "other")
            log.warning("bad token from %s: headers=%s, auth scheme=%s, token supplied=%s",
                        self.client_address[0], sorted(self.headers.keys()), scheme,
                        "yes" if supplied else "no")
            return False

        def do_GET(self):
            path, _, query = self.path.partition("?")
            if path == "/health":
                self._reply(200, {"ok": True})
            elif path.rstrip("/") == "/latest" and latest is not None:
                self._latest(urllib.parse.parse_qs(query))
            else:
                self._reply(404)

        def _latest(self, query):
            # Loopback only: to anything on the LAN or tailnet this path doesn't exist.
            if not _is_loopback(self.client_address[0]):
                log.warning("rejected /latest from %s", self.client_address[0])
                return self._reply(404)
            # Block DNS rebinding (a page whose own hostname resolves to 127.0.0.1)
            # and plain web pages; only the extension's own origin may ask.
            host = urllib.parse.urlsplit("//" + self.headers.get("Host", "")).hostname
            origin = self.headers.get("Origin", "")
            if host not in LOOPBACK_HOSTS or (origin and not origin.startswith(EXTENSION_ORIGINS)):
                log.warning("rejected /latest: host or origin not allowed")
                return self._reply(403, {"error": "forbidden"})
            supplied = self.headers.get("X-OTP-Bridge-Key", "").strip().encode()
            if not extension_key or not hmac.compare_digest(supplied, extension_key):
                log.warning("rejected /latest: extension key %s", "wrong" if supplied else "missing")
                return self._reply(401, {"error": "unauthorized"})
            after = int(_query_number(query, "after", 2**62))
            self._reply(200, latest.get(after, _query_number(query, "wait", MAX_WAIT)))

        def do_POST(self):
            if self.path.rstrip("/") != "/otp":
                return self._reply(404)
            if not _ip_allowed(self.client_address[0], cfg["allow_public_ips"]):
                log.warning("rejected request from %s", self.client_address[0])
                return self._reply(401, {"error": "unauthorized"})
            try:
                length = int(self.headers.get("Content-Length", ""))
            except ValueError:
                return self._reply(411)
            if not 0 <= length <= MAX_BODY:
                return self._reply(413)
            raw = self.rfile.read(length).decode("utf-8", "replace")
            if not self._authorized(raw):
                log.warning("rejected request from %s", self.client_address[0])
                return self._reply(401, {"error": "unauthorized"})
            text, sender = parse_body(raw)
            code = extract_code(text)
            if not code:
                # Lengths only, never content: tells an empty forward apart from a missed code.
                log.info("message from %s had no code (body %d chars, text %d chars)",
                         self.client_address[0], len(raw), len(text))
                return self._reply(200, {"code": None})
            on_code(code, sender)
            self._reply(200, {"code": code})

    return Handler


def start(cfg: dict, on_code, latest: LatestCode = None) -> ThreadingHTTPServer:
    httpd = ThreadingHTTPServer((cfg["bind"], cfg["port"]), make_handler(cfg, on_code, latest))
    threading.Thread(target=httpd.serve_forever, daemon=True, name="http").start()
    log.info("listening on %s:%s", cfg["bind"], cfg["port"])
    return httpd
