import json
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
