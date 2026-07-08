// Popup settings: bind controls to chrome.storage.local.

const DEFAULTS = {
  enabled: true,
  autoSend: false,
  translateReplies: true,
  replyMode: "hybrid",
  engine: "google",
  deeplKey: "",
};

const enabledEl = document.getElementById("enabled");
const autoSendEl = document.getElementById("autoSend");
const translateRepliesEl = document.getElementById("translateReplies");
const replyModeEl = document.getElementById("replyMode");
const modeHintEl = document.getElementById("modeHint");
const engineEl = document.getElementById("engine");
const deeplBoxEl = document.getElementById("deeplBox");
const deeplKeyEl = document.getElementById("deeplKey");

const MODE_HINTS = {
  hybrid: "纯文字段落就地替换，点击可看原文；含代码或链接的段落在下方附译文。",
  append: "保留原文，每段下方附中文译文，最完整。",
  overlay: "仅替换纯文字段落，含代码或链接的段落保持英文。",
};

function renderModeHint() {
  modeHintEl.textContent = MODE_HINTS[replyModeEl.value] || "";
}

function renderEngine() {
  deeplBoxEl.style.display = engineEl.value === "deepl" ? "block" : "none";
}

chrome.storage.local.get(DEFAULTS, (s) => {
  enabledEl.checked = s.enabled;
  autoSendEl.checked = s.autoSend;
  translateRepliesEl.checked = s.translateReplies;
  replyModeEl.value = s.replyMode;
  engineEl.value = s.engine;
  deeplKeyEl.value = s.deeplKey;
  renderModeHint();
  renderEngine();
});

enabledEl.addEventListener("change", () => {
  chrome.storage.local.set({ enabled: enabledEl.checked });
});

autoSendEl.addEventListener("change", () => {
  chrome.storage.local.set({ autoSend: autoSendEl.checked });
});

translateRepliesEl.addEventListener("change", () => {
  chrome.storage.local.set({ translateReplies: translateRepliesEl.checked });
});

replyModeEl.addEventListener("change", () => {
  chrome.storage.local.set({ replyMode: replyModeEl.value });
  renderModeHint();
});

engineEl.addEventListener("change", () => {
  chrome.storage.local.set({ engine: engineEl.value });
  renderEngine();
});

// Save the key as it is typed (debounced lightly by input coalescing).
deeplKeyEl.addEventListener("change", () => {
  chrome.storage.local.set({ deeplKey: deeplKeyEl.value.trim() });
});
