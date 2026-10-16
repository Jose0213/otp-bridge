"""HTTP endpoint the phone posts incoming text messages to."""
import hmac
import ipaddress
import json
import logging
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from .extract import extract_code, parse_body

log = logging.getLogger("otp_bridge")

TAILSCALE = ipaddress.ip_network("100.64.0.0/10")
MAX_BODY = 16 * 1024


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


def make_handler(cfg: dict, on_code):
    token = cfg["token"].encode()

    class Handler(BaseHTTPRequestHandler):
        server_version = "otp-bridge"

        def log_message(self, fmt, *args):  # keep message contents out of logs
            log.debug("%s %s", self.client_address[0], fmt % args)

        def _reply(self, status, body=None):
            data = json.dumps(body or {}).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
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
            if self.path == "/health":
                self._reply(200, {"ok": True})
            else:
                self._reply(404)

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


def start(cfg: dict, on_code) -> ThreadingHTTPServer:
    httpd = ThreadingHTTPServer((cfg["bind"], cfg["port"]), make_handler(cfg, on_code))
    threading.Thread(target=httpd.serve_forever, daemon=True, name="http").start()
    log.info("listening on %s:%s", cfg["bind"], cfg["port"])
    return httpd
