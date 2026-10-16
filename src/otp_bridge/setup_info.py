"""The values a phone needs, as text (CLI) or a local HTML page (tray menu)."""
import html
import ipaddress
import shutil
import socket
import subprocess

from . import config

TAILNET = ipaddress.ip_network("100.64.0.0/10")


def local_ips():
    ips = set()
    try:
        for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
            ips.add(info[4][0])
    except OSError:
        pass
    if shutil.which("tailscale"):
        try:
            out = subprocess.run(["tailscale", "ip", "-4"], capture_output=True, text=True, timeout=5,
                                 creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)).stdout
            ips.update(line.strip() for line in out.splitlines() if line.strip())
        except (OSError, subprocess.SubprocessError):
            pass
    result = []
    for ip in sorted(ips):
        addr = ipaddress.ip_address(ip)
        if addr.is_loopback or addr.is_link_local:
            continue
        result.append((ip, "Tailscale, works anywhere" if addr in TAILNET else "local network, same Wi-Fi only"))
    return result


def direct_urls(cfg):
    return [(f"http://{ip}:{cfg['port']}/otp", kind) for ip, kind in local_ips()]


def as_text(cfg) -> str:
    lines = ["Phone setup for OTP Bridge", ""]
    if cfg.get("relay_url"):
        lines += ["Relay mode (works from anywhere):",
                  f"  POST  {cfg['relay_url']}",
                  "  Body: the message text (no header needed)", ""]
    lines += ["Direct mode:", "  Method: POST",
              f"  Header: Authorization: Bearer {cfg['token']}",
              '  Body:   JSON {"text": <message>, "sender": <sender>}', "  URL (one your phone can reach):"]
    lines += [f"    {url}    ({kind})" for url, kind in direct_urls(cfg)] or ["    (no network address found)"]
    lines += ["", f"Settings: {config.config_dir() / 'config.json'}"]
    return "\n".join(lines)


def write_page(cfg) -> str:
    e = html.escape
    rows = "".join(f"<li><code>{e(u)}</code> <span>{e(k)}</span></li>" for u, k in direct_urls(cfg))
    relay = ""
    if cfg.get("relay_url"):
        relay = f"""<h2>Relay mode</h2><p>Works from anywhere. In the phone action, POST the message text to:</p>
<p><code class=copy>{e(cfg['relay_url'])}</code></p>"""
    page = f"""<!doctype html><meta charset=utf-8><title>OTP Bridge setup</title>
<style>
body{{font:15px/1.5 system-ui,sans-serif;max-width:720px;margin:40px auto;padding:0 16px;color:#111;background:#fff}}
@media(prefers-color-scheme:dark){{body{{color:#eee;background:#16181d}}code{{background:#262a33!important}}}}
code{{background:#f1f3f5;padding:2px 6px;border-radius:4px;word-break:break-all}} li span{{opacity:.6}}
.copy{{cursor:pointer}} h1{{font-size:22px}} h2{{font-size:17px;margin-top:28px}}
</style>
<h1>Connect your phone to OTP Bridge</h1>
<p>Click any value to copy it. Full steps for iPhone and Android are in the README.</p>
{relay}
<h2>Direct mode</h2>
<p><b>URL</b>: pick one your phone can reach:</p><ul>{rows or '<li>No network address found</li>'}</ul>
<p><b>Method</b> <code>POST</code> &nbsp; <b>Body</b> JSON with a <code>text</code> field (the message)</p>
<p><b>Header</b> <code>Authorization</code>: <code class=copy>Bearer {e(cfg['token'])}</code></p>
<script>document.querySelectorAll('code').forEach(c=>c.onclick=()=>navigator.clipboard.writeText(c.textContent))</script>
"""
    path = config.config_dir() / "setup.html"
    path.write_text(page, encoding="utf-8")
    return str(path)
