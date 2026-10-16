import pytest

from otp_bridge.extract import extract_code, parse_body

CASES = [
    ("Your Amazon OTP is 482913. Don't share it.", "482913"),
    ("G-739201 is your Google verification code.", "739201"),
    ("Your Chase code is 12345678. Call 1-800-935-9935 if you didn't request it.", "12345678"),
    ("123-456 is your Instagram code", "123456"),
    ("Use 4821 as your Uber code", "4821"),
    ("Your verification code: A7K2Q9", "A7K2Q9"),
    ("Bank of America: 2026 transaction of $4,500.00. Code 559102 expires in 10 min", "559102"),
    ("Your DoorDash code is 902 113", "902113"),
    ("Microsoft account security code: 3391", "3391"),
    ("Your code is 0042. Reply STOP to 55555", "0042"),
    ("<#> 731502 is your WhatsApp code. FA+9qCX9VSu", "731502"),
    ("Hey are we still on for 7:30?", None),
    ("Call me at 555-867-5309", None),
    ("", None),
]


@pytest.mark.parametrize("text,expected", CASES)
def test_extract(text, expected):
    assert extract_code(text) == expected


def test_parse_body_capitalized_keys():
    # iOS Shortcuts capitalizes JSON keys typed on the phone.
    assert parse_body('{"Text": "Your code is 4821", "Sender": "Uber"}') == ("Your code is 4821", "Uber")


def test_parse_body_android_forwarder_keys():
    assert parse_body('{"from": "+15550100", "text": "code 111222"}') == ("code 111222", "+15550100")


def test_parse_body_plain_text_and_bad_json():
    assert parse_body("Your code is 4821") == ("Your code is 4821", None)
    assert parse_body("{not json") == ("{not json", None)
