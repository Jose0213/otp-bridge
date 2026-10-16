const form = document.getElementById("form");
const keyInput = document.getElementById("key");
const portInput = document.getElementById("port");
const status = document.getElementById("status");

const MESSAGES = {
  ok: "Connected. Codes will be filled automatically.",
  unpaired: "Paste the pairing key first.",
  "bad-key": "That key doesn't match. Copy it again from the tray menu.",
  offline: "Can't reach OTP Bridge. Is the tray app running?",
};

function show(result) {
  const kind = result?.ok ? "ok" : result?.error || "offline";
  status.textContent = MESSAGES[kind] || MESSAGES.offline;
  status.className = kind === "ok" ? "ok" : "bad";
}

async function test() {
  status.textContent = "Checking…";
  status.className = "";
  show(await chrome.runtime.sendMessage({ type: "test" }));
}

chrome.storage.local.get({ port: 9233, key: "" }).then(({ port, key }) => {
  portInput.value = port;
  keyInput.value = key;
});

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  await chrome.storage.local.set({ key: keyInput.value.trim(), port: Number(portInput.value) || 9233 });
  await test();
});

document.getElementById("test").addEventListener("click", test);
