// Popup settings: bind controls to chrome.storage.local.

const DEFAULTS = {
  enabled: true,
  autoSend: false,
  translateReplies: true,
  replyMode: "hybrid",
  engine: "google",
  deeplKey: "",
  geminiKey: "",
};

const enabledEl = document.getElementById("enabled");
const autoSendEl = document.getElementById("autoSend");
const translateRepliesEl = document.getElementById("translateReplies");
const replyModeEl = document.getElementById("replyMode");
const modeHintEl = document.getElementById("modeHint");
const engineEl = document.getElementById("engine");
const deeplBoxEl = document.getElementById("deeplBox");
const deeplKeyEl = document.getElementById("deeplKey");
const geminiBoxEl = document.getElementById("geminiBox");
const geminiKeyEl = document.getElementById("geminiKey");
const advEl = document.getElementById("adv");

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
  geminiBoxEl.style.display = engineEl.value === "gemini" ? "block" : "none";
}

chrome.storage.local.get(DEFAULTS, (s) => {
  enabledEl.checked = s.enabled;
  autoSendEl.checked = s.autoSend;
  translateRepliesEl.checked = s.translateReplies;
  replyModeEl.value = s.replyMode;
  engineEl.value = s.engine;
  deeplKeyEl.value = s.deeplKey;
  geminiKeyEl.value = s.geminiKey;
  advEl.open = s.engine !== "google"; // reveal advanced if a custom engine is set
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

deeplKeyEl.addEventListener("change", () => {
  chrome.storage.local.set({ deeplKey: deeplKeyEl.value.trim() });
});

geminiKeyEl.addEventListener("change", () => {
  chrome.storage.local.set({ geminiKey: geminiKeyEl.value.trim() });
});
