import json
import logging
import threading
import time
import urllib.error
import urllib.request

import pytest

from otp_bridge import server
from otp_bridge.config import DEFAULTS


@pytest.fixture
def running():
    received = []
    cfg = dict(DEFAULTS, bind="127.0.0.1", port=0, token="secret-token")
    httpd = server.start(cfg, lambda code, sender: received.append((code, sender)))
    yield f"http://127.0.0.1:{httpd.server_address[1]}", received
    httpd.shutdown()


def post(url, body, token="secret-token", ctype="application/json"):
    req = urllib.request.Request(url + "/otp", data=body.encode(), method="POST",
                                 headers={"Authorization": f"Bearer {token}", "Content-Type": ctype})
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read())


def test_json_body(running):
    url, received = running
    assert post(url, json.dumps({"text": "Your code is 482913", "sender": "Amazon"})) == {"code": "482913"}
    assert received == [("482913", "Amazon")]


def test_plain_text_body(running):
    url, received = running
    assert post(url, "Your code is 4821", ctype="text/plain")["code"] == "4821"


def test_no_code(running):
    url, received = running
    assert post(url, json.dumps({"text": "see you at 7:30"})) == {"code": None}
    assert received == []


def test_bad_token(running):
    url, received = running
    with pytest.raises(urllib.error.HTTPError) as err:
        post(url, json.dumps({"text": "code 123456"}), token="wrong")
    assert err.value.code == 401
    assert received == []


def test_public_ip_blocked():
    assert server._ip_allowed("100.90.18.9", False)
    assert server._ip_allowed("192.168.1.20", False)
    assert not server._ip_allowed("8.8.8.8", False)
    assert server._ip_allowed("8.8.8.8", True)


def test_capitalized_json_keys(running):
    url, received = running
    assert post(url, json.dumps({"Text": "Your code is 902113", "Sender": "DoorDash"})) == {"code": "902113"}
    assert received == [("902113", "DoorDash")]


def test_token_with_stray_whitespace(running):
    url, received = running
    req = urllib.request.Request(url + "/otp", data=b'{"text": "code 445566"}', method="POST",
                                 headers={"Authorization": "Bearer  secret-token\n".strip() + " ",
                                          "Content-Type": "application/json"})
    with urllib.request.urlopen(req) as resp:
        assert json.loads(resp.read()) == {"code": "445566"}


def test_token_in_json_body(running):
    # iOS Shortcuts sometimes drops the Authorization header; the body field is the fallback.
    url, received = running
    req = urllib.request.Request(url + "/otp", data=b'{"Text": "Your code is 314159", "Token": "secret-token"}',
                                 method="POST", headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req) as resp:
        assert json.loads(resp.read()) == {"code": "314159"}


def test_wrong_token_in_json_body(running):
    url, received = running
    req = urllib.request.Request(url + "/otp", data=b'{"text": "code 314159", "token": "nope"}',
                                 method="POST", headers={"Content-Type": "application/json"})
    with pytest.raises(urllib.error.HTTPError) as err:
        urllib.request.urlopen(req)
    assert err.value.code == 401
    assert received == []


# --- GET /latest (browser extension) -----------------------------------------

@pytest.fixture
def latest_server():
    latest = server.LatestCode(ttl=300)
    cfg = dict(DEFAULTS, bind="127.0.0.1", port=0, token="secret-token", extension_key="ext-key")
    httpd = server.start(cfg, lambda code, sender: latest.publish(code), latest)
    yield f"http://127.0.0.1:{httpd.server_address[1]}", latest
    httpd.shutdown()


def get_latest(url, query="", key="ext-key", headers=None):
    req = urllib.request.Request(f"{url}/latest{query}", headers=dict({"X-OTP-Bridge-Key": key}, **(headers or {})))
    with urllib.request.urlopen(req) as resp:
        assert resp.headers["Cache-Control"] == "no-store"
        return json.loads(resp.read())


def status_of(fn):
    with pytest.raises(urllib.error.HTTPError) as err:
        fn()
    return err.value.code


def test_latest_empty(latest_server):
    url, _ = latest_server
    assert get_latest(url) == {"code": None, "id": 0}


def test_latest_returns_posted_code(latest_server):
    url, _ = latest_server
    post(url, json.dumps({"text": "Your code is 482913"}))
    body = get_latest(url)
    assert body["code"] == "482913" and body["id"] == 1 and 0 <= body["age"] < 5
    # Already seen: nothing newer than id 1.
    assert get_latest(url, "?after=1") == {"code": None, "id": 1}


def test_latest_long_poll_wakes_on_new_code(latest_server):
    url, latest = latest_server
    threading.Timer(0.3, latest.publish, args=("771204",)).start()
    started = time.monotonic()
    body = get_latest(url, "?after=0&wait=10")
    assert body["code"] == "771204"
    assert time.monotonic() - started < 5


def test_latest_long_poll_times_out(latest_server):
    url, _ = latest_server
    started = time.monotonic()
    assert get_latest(url, "?wait=0.5") == {"code": None, "id": 0}
    assert time.monotonic() - started >= 0.4


def test_latest_expired_code_not_returned():
    latest = server.LatestCode(ttl=0.2)
    latest.publish("123456")
    assert latest.get()["code"] == "123456"
    time.sleep(0.3)
    assert latest.get() == {"code": None, "id": 1}


def test_latest_cleared_code_not_returned():
    latest = server.LatestCode(ttl=300)
    latest.publish("123456")
    latest.clear("999999")
    assert latest.get()["code"] == "123456"
    latest.clear("123456")
    assert latest.get()["code"] is None


def test_latest_needs_extension_key(latest_server):
    url, latest = latest_server
    latest.publish("482913")
    assert status_of(lambda: get_latest(url, key="")) == 401
    assert status_of(lambda: get_latest(url, key="wrong")) == 401
    # The phone's token is not the extension key.
    assert status_of(lambda: get_latest(url, key="secret-token")) == 401


def test_latest_rejects_web_page_origin(latest_server):
    url, latest = latest_server
    latest.publish("482913")
    assert status_of(lambda: get_latest(url, headers={"Origin": "https://evil.example"})) == 403
    assert status_of(lambda: get_latest(url, headers={"Origin": "null"})) == 403
    ext = get_latest(url, headers={"Origin": "chrome-extension://abcdefghijklmnop"})
    assert ext["code"] == "482913"


def test_latest_rejects_rebound_host(latest_server):
    url, latest = latest_server
    latest.publish("482913")
    assert status_of(lambda: get_latest(url, headers={"Host": "evil.example:9233"})) == 403
    assert get_latest(url, headers={"Host": "localhost:9233"})["code"] == "482913"


def test_latest_not_served_off_loopback():
    assert server._is_loopback("127.0.0.1")
    assert server._is_loopback("::1")
    assert server._is_loopback("::ffff:127.0.0.1")
    assert not server._is_loopback("192.168.10.9")
    assert not server._is_loopback("100.90.18.9")
    assert not server._is_loopback("garbage")


def test_latest_hidden_from_lan(latest_server, monkeypatch):
    url, latest = latest_server
    latest.publish("482913")
    monkeypatch.setattr(server, "_is_loopback", lambda ip: False)
    assert status_of(lambda: get_latest(url)) == 404


def test_latest_off_without_store(running):
    url, _ = running
    assert status_of(lambda: get_latest(url)) == 404


def test_latest_never_logs_code(latest_server, caplog):
    url, latest = latest_server
    caplog.set_level(logging.DEBUG, logger="otp_bridge")
    post(url, json.dumps({"text": "Your code is 482913"}))
    get_latest(url)
    status_of(lambda: get_latest(url, key="wrong"))
    assert "482913" not in caplog.text
    assert "ext-key" not in caplog.text
