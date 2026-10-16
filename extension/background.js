// Talks to the OTP Bridge tray app on 127.0.0.1. Content scripts can't reach
// loopback themselves, so they ask here. Codes are passed through, never stored.

const DEFAULTS = { port: 9233, key: "" };
// Long-poll for less than the ~30 s an idle service worker is allowed to live;
// every new message from a content script resets that timer.
const MAX_WAIT = 20;

async function fetchLatest(after, wait) {
  const { port, key } = await chrome.storage.local.get(DEFAULTS);
  if (!key) return { error: "unpaired" };
  const url = `http://127.0.0.1:${Number(port) || 9233}/latest?after=${after}&wait=${wait}`;
  let resp;
  try {
    resp = await fetch(url, { headers: { "X-OTP-Bridge-Key": key }, cache: "no-store", credentials: "omit" });
  } catch {
    return { error: "offline" };
  }
  if (resp.status === 401) return { error: "bad-key" };
  if (!resp.ok) return { error: "offline" };
  return resp.json();
}

// Remember the last code filled (as a hash, in session memory) so the same code
// isn't put into a second form later.
async function fingerprint(id, code) {
  const digest = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(`${id}:${code}`));
  return Array.from(new Uint8Array(digest), (b) => b.toString(16).padStart(2, "0")).join("");
}

async function alreadyFilled(body) {
  const { filled } = await chrome.storage.session.get("filled");
  return Boolean(filled && body.code && filled === (await fingerprint(body.id, body.code)));
}

async function poll({ after = 0, wait = 0 }) {
  const body = await fetchLatest(Math.max(0, after | 0), Math.min(Math.max(0, Number(wait) || 0), MAX_WAIT));
  if (body.code && (await alreadyFilled(body))) return { code: null, id: body.id };
  return body;
}

chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {
  if (sender.id !== chrome.runtime.id) return false;
  if (msg?.type === "poll") {
    poll(msg).then(sendResponse);
    return true;
  }
  if (msg?.type === "filled") {
    fingerprint(msg.id, msg.code).then((filled) => chrome.storage.session.set({ filled }));
    return false;
  }
  if (msg?.type === "test") {
    fetchLatest(0, 0).then((body) => sendResponse(body.error ? body : { ok: true }));
    return true;
  }
  return false;
});

chrome.action.onClicked.addListener(() => chrome.runtime.openOptionsPage());

chrome.runtime.onInstalled.addListener(async ({ reason }) => {
  const { key } = await chrome.storage.local.get(DEFAULTS);
  if (reason === "install" && !key) chrome.runtime.openOptionsPage();
});
