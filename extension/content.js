// Finds one-time-code fields, waits for OTP Bridge to receive a code, and fills it once.
(() => {
  if (window.__otpBridge) return;
  window.__otpBridge = true;

  // A code that arrived up to this long before the field showed up still counts
  // (the text often lands while the page is loading).
  const RECENT_SECONDS = 90;
  const WATCH_MS = 5 * 60 * 1000;
  const LONG_POLL = 20;

  const OTP_WORDS =
    /one[\s_-]?time|otp|2fa|mfa|two[\s_-]?(factor|step)|verification|verify|security[\s_-]?code|auth\w*[\s_-]?code|sms[\s_-]?code|passcode|confirm\w*[\s_-]?code|log[\s_-]?in[\s_-]?code|sign[\s_-]?in[\s_-]?code|access[\s_-]?code|\bcode\b/i;
  const NOT_OTP =
    /promo|coupon|voucher|discount|gift|referr|invit|zip|postal|post[\s_-]?code|country|area[\s_-]?code|dial|phone|captcha|tracking|product|qr|redeem|access[\s_-]?key|search/i;
  const SINGLE_TYPES = new Set(["text", "tel", "number", ""]);
  const SPLIT_TYPES = new Set(["text", "tel", "number", "password", ""]);

  const done = new WeakSet(); // fields already filled or typed into by the user
  let paused = new WeakSet(); // watched for WATCH_MS with no code; focusing one wakes it
  let watching = null;
  let stopped = false; // not paired, or the extension was reloaded

  const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

  function visible(el) {
    if (el.disabled || el.readOnly) return false;
    const rect = el.getBoundingClientRect();
    if (rect.width < 4 || rect.height < 4) return false;
    const style = getComputedStyle(el);
    return style.visibility !== "hidden" && style.display !== "none";
  }

  function describe(el) {
    const parts = [el.name, el.id, el.placeholder, el.getAttribute("aria-label"), el.getAttribute("autocomplete")];
    for (const label of el.labels || []) parts.push(label.textContent);
    for (const id of (el.getAttribute("aria-labelledby") || "").split(/\s+/)) {
      if (id) parts.push(document.getElementById(id)?.textContent);
    }
    return parts.filter(Boolean).join(" ").slice(0, 500);
  }

  const isOneTimeCode = (el) => /one-time-code/i.test(el.getAttribute("autocomplete") || "");

  function looksLikeOtp(el) {
    if (!SINGLE_TYPES.has(el.type)) return false;
    if (el.maxLength > 0 && (el.maxLength < 4 || el.maxLength > 10)) return false;
    const text = describe(el);
    return OTP_WORDS.test(text) && !NOT_OTP.test(text);
  }

  // 4 to 8 one-character boxes that sit together, like  [4][8][2][9][1][3].
  function splitGroup(inputs) {
    const boxes = inputs.filter((el) => el.maxLength === 1 && SPLIT_TYPES.has(el.type) && visible(el));
    for (const box of boxes) {
      let node = box.parentElement;
      for (let depth = 0; node && depth < 4; depth++, node = node.parentElement) {
        const members = boxes.filter((b) => node.contains(b));
        if (members.length >= 4 && members.length <= 8) return members;
        if (members.length > 8) break;
      }
    }
    return null;
  }

  function findTarget() {
    const inputs = Array.from(document.querySelectorAll("input")).filter((el) => !done.has(el) && !paused.has(el));
    const group = splitGroup(inputs);
    if (group) return { els: group };
    const single =
      inputs.find((el) => isOneTimeCode(el) && el.type !== "hidden" && visible(el)) ||
      inputs.find((el) => looksLikeOtp(el) && visible(el));
    return single ? { els: [single] } : null;
  }

  // --- filling ------------------------------------------------------------
  const valueSetter = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, "value").set;

  function setValue(el, value) {
    el.focus();
    // The native setter, so frameworks like React notice the change.
    valueSetter.call(el, value);
    el.dispatchEvent(new InputEvent("input", { bubbles: true, inputType: "insertText", data: value }));
    el.dispatchEvent(new Event("change", { bubbles: true }));
  }

  function paste(el, value) {
    el.focus();
    const data = new DataTransfer();
    data.setData("text/plain", value);
    el.dispatchEvent(new ClipboardEvent("paste", { clipboardData: data, bubbles: true, cancelable: true }));
  }

  const filledWith = (els, code) =>
    els.length === 1 ? els[0].value === code : els.map((el) => el.value).join("") === code;

  async function fill(target, code) {
    const { els } = target;
    if (els.length > 1 && els.length !== code.length) return false;
    if (els.length === 1 && els[0].maxLength > 0 && els[0].maxLength < code.length) return false;
    if (els.length === 1) {
      setValue(els[0], code);
    } else {
      els.forEach((el, i) => setValue(el, code[i]));
      await sleep(50);
      if (!filledWith(els, code)) {
        // Some split-box widgets ignore per-box input but handle a paste.
        els.forEach((el) => valueSetter.call(el, ""));
        paste(els[0], code);
      }
    }
    await sleep(50);
    return filledWith(els, code);
  }

  function confirm(anchor) {
    const rect = anchor.getBoundingClientRect();
    const host = document.createElement("div");
    const root = host.attachShadow({ mode: "closed" });
    const top = Math.min(rect.bottom + 6, window.innerHeight - 36);
    const left = Math.max(8, Math.min(rect.left, window.innerWidth - 220));
    root.innerHTML = `
      <style>
        .pill { position: fixed; top: ${top}px; left: ${left}px; z-index: 2147483647; pointer-events: none;
          font: 500 12px/1 system-ui, -apple-system, "Segoe UI", sans-serif; color: #fff; background: #2563eb;
          padding: 7px 10px; border-radius: 999px; box-shadow: 0 2px 8px rgba(0,0,0,.2);
          opacity: 0; transform: translateY(-2px); transition: opacity .18s, transform .18s; }
        .pill.on { opacity: 1; transform: none; }
        @media (prefers-reduced-motion: reduce) { .pill { transition: none; } }
      </style>
      <div class="pill" role="status">✓ Code filled by OTP Bridge</div>`;
    document.documentElement.appendChild(host);
    const pill = root.querySelector(".pill");
    requestAnimationFrame(() => pill.classList.add("on"));
    setTimeout(() => pill.classList.remove("on"), 2200);
    setTimeout(() => host.remove(), 2600);
  }

  // --- only fill where the user is ---------------------------------------
  // A page, or an ad frame inside it, must not receive a code just by showing a
  // code box. Fill only once this frame has had a real click or key press and
  // one of the code fields has focus: the moment you would type the code anyway.
  function userIsOnField(target) {
    const activated = navigator.userActivation ? navigator.userActivation.hasBeenActive : false;
    return activated && document.hasFocus() && target.els.includes(document.activeElement);
  }

  // Resolves when the user moves into a code field, or clicks or types in one
  // that already has focus (many sites focus the code box themselves).
  const USER_EVENTS = ["focusin", "pointerdown", "keydown"];
  const whenFocused = (target, ms) =>
    new Promise((resolve) => {
      const onEvent = (event) => {
        if (target.els.includes(event.target)) setTimeout(finish, 0);
      };
      const finish = () => {
        USER_EVENTS.forEach((type) => document.removeEventListener(type, onEvent, true));
        clearTimeout(timer);
        resolve();
      };
      const timer = setTimeout(finish, ms);
      USER_EVENTS.forEach((type) => document.addEventListener(type, onEvent, true));
    });

  // --- waiting for a code -------------------------------------------------
  function ask(msg) {
    return new Promise((resolve) => {
      try {
        chrome.runtime.sendMessage(msg, (resp) => {
          resolve(chrome.runtime.lastError ? { error: "gone" } : resp);
        });
      } catch {
        resolve({ error: "gone" }); // the extension was reloaded or removed
      }
    });
  }

  const whenVisible = () =>
    new Promise((resolve) => {
      if (!document.hidden) return resolve();
      const onChange = () => {
        if (document.hidden) return;
        document.removeEventListener("visibilitychange", onChange);
        resolve();
      };
      document.addEventListener("visibilitychange", onChange);
    });

  async function watch(target) {
    watching = target;
    const started = Date.now();
    let after = 0;
    let fresh = true; // first ask, or back from a hidden tab: accept a recent code
    while (watching === target && Date.now() - started < WATCH_MS) {
      if (!target.els.every((el) => el.isConnected)) break;
      if (target.els.some((el) => el.value)) {
        target.els.forEach((el) => done.add(el)); // the user is typing it themselves
        break;
      }
      if (document.hidden) {
        // Never fill a tab you aren't looking at.
        await whenVisible();
        fresh = true;
        continue;
      }
      const resp = await ask({ type: "poll", after, wait: fresh ? 0 : LONG_POLL });
      if (!resp || ["gone", "unpaired", "bad-key"].includes(resp.error)) {
        stopped = true;
        break;
      }
      if (resp.error) {
        await sleep(5000); // OTP Bridge isn't running; try again shortly
        continue;
      }
      if (resp.code && !document.hidden && (!fresh || resp.age <= RECENT_SECONDS) && !target.els.some((el) => el.value)) {
        if (!userIsOnField(target)) {
          // Hold the code until the user clicks into the field, then ask again:
          // it's filled if it is still recent.
          await whenFocused(target, 10000);
          fresh = true;
          continue;
        }
        if (await fill(target, resp.code)) {
          target.els.forEach((el) => done.add(el));
          ask({ type: "filled", id: resp.id, code: resp.code });
          confirm(target.els[target.els.length - 1]);
          break;
        }
      }
      after = resp.id;
      fresh = false;
    }
    if (Date.now() - started >= WATCH_MS) target.els.forEach((el) => paused.add(el));
    if (watching === target) watching = null;
    scanSoon();
  }

  // --- noticing fields ----------------------------------------------------
  let scanTimer = 0;
  function scan() {
    scanTimer = 0;
    if (stopped) return;
    if (watching && watching.els.every((el) => el.isConnected)) return;
    const target = findTarget();
    if (target) watch(target);
    else watching = null;
  }
  function scanSoon() {
    if (!scanTimer) scanTimer = setTimeout(scan, 300);
  }

  new MutationObserver(scanSoon).observe(document.documentElement, { childList: true, subtree: true });
  document.addEventListener(
    "focusin",
    (event) => {
      if (paused.has(event.target)) paused = new WeakSet();
      scanSoon();
    },
    true,
  );
  scan();
})();
