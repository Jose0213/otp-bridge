"""Pull a one-time code out of a text message."""
import json
import re

KEYWORDS = re.compile(
    r"\b(code|passcode|otp|pin|verification|verify|one[- ]time|security|login|log-in|sign[- ]in|2fa|auth\w*|confirm\w*)\b",
    re.I,
)

# Ordered most specific first. Each yields (code, start, end).
PATTERNS = [
    re.compile(r"\b[A-Z]{1,3}-(\d{4,8})\b"),               # G-123456
    re.compile(r"(?<![\d$€£.,-])(\d{3})[- ](\d{3})(?![\d%-])"),  # 123-456 / 123 456
    re.compile(r"(?<![\d$€£.,:/-])(\d{4,8})(?![\d%:/-])"),     # 123456
    re.compile(r"\b(?=[A-Z0-9]*\d)(?=[A-Z0-9]*[A-Z])([A-Z0-9]{5,8})\b"),  # A7K2Q9
]


def _candidates(text):
    for rank, pat in enumerate(PATTERNS):
        for m in pat.finditer(text):
            code = "".join(g for g in m.groups() if g)
            yield code, m.start(), m.end(), rank


def extract_code(text):
    """Return the most likely OTP in `text`, or None."""
    if not text:
        return None
    kw = [m.start() for m in KEYWORDS.finditer(text)]
    best = None
    for code, start, end, rank in _candidates(text):
        # Skip things that look like years, times, or phone numbers.
        if len(code) == 4 and re.fullmatch(r"(19|20)\d\d", code) and not kw:
            continue
        before = text[max(0, start - 2):start]
        if before.endswith("+") or before.endswith("("):
            continue
        dist = min((abs(start - k) for k in kw), default=10_000)
        if rank == 3 and dist > 40:
            continue  # bare alphanumeric words need a keyword right next to them
        score = dist + rank * 15 - (6 <= len(code) <= 8) * 10
        if best is None or score < best[0]:
            best = (score, code)
    return best[1] if best else None


def parse_body(raw):
    """Return (text, sender) from a forwarded message body.

    Accepts JSON such as {"text": ..., "sender": ...} with keys in any letter case
    (iOS Shortcuts capitalizes them), or the raw message as plain text.
    """
    if raw.lstrip().startswith("{"):
        try:
            payload = {str(k).lower(): v for k, v in json.loads(raw).items()}
        except (ValueError, AttributeError):
            return raw, None
        text = payload.get("text") or payload.get("message") or payload.get("body") or ""
        sender = payload.get("sender") or payload.get("from")
        return str(text), (str(sender)[:60] if sender else None)
    return raw, None
