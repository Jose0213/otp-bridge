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

        def _authorized(self) -> bool:
            if not _ip_allowed(self.client_address[0], cfg["allow_public_ips"]):
                return False
            auth = self.headers.get("Authorization", "")
            supplied = auth[7:] if auth.lower().startswith("bearer ") else self.headers.get("X-OTP-Token", "")
            return hmac.compare_digest(supplied.encode(), token)

        def do_GET(self):
            if self.path == "/health":
                self._reply(200, {"ok": True})
            else:
                self._reply(404)

        def do_POST(self):
            if self.path.rstrip("/") != "/otp":
                return self._reply(404)
            if not self._authorized():
                log.warning("rejected request from %s", self.client_address[0])
                return self._reply(401, {"error": "unauthorized"})
            length = int(self.headers.get("Content-Length") or 0)
            if length > MAX_BODY:
                return self._reply(413)
            raw = self.rfile.read(length).decode("utf-8", "replace")
            text, sender = parse_body(raw)
            code = extract_code(text)
            if not code:
                log.info("message from %s had no code", self.client_address[0])
                return self._reply(200, {"code": None})
            on_code(code, sender)
            self._reply(200, {"code": code})

    return Handler


def start(cfg: dict, on_code) -> ThreadingHTTPServer:
    httpd = ThreadingHTTPServer((cfg["bind"], cfg["port"]), make_handler(cfg, on_code))
    threading.Thread(target=httpd.serve_forever, daemon=True, name="http").start()
    log.info("listening on %s:%s", cfg["bind"], cfg["port"])
    return httpd
