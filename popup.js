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
const engineNowEl = document.getElementById("engineNow");

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
  renderEngineNow();
}

// Show which engine is actually in effect. A chosen engine with no key falls
// back to Google; a chosen engine WITH a key is verified by a tiny live
// translation, so a wrong or unusable key is caught here rather than silently
// failing on every reply. Assumes chrome.storage already holds current values.
let verifyToken = 0;
function renderEngineNow() {
  const e = engineEl.value;
  const name = { google: "Google", deepl: "DeepL", gemini: "Gemini" }[e];
  verifyToken++;

  if (e === "google") {
    engineNowEl.textContent = "当前生效：Google";
    return;
  }
  const key = e === "deepl" ? deeplKeyEl.value.trim() : geminiKeyEl.value.trim();
  if (!key) {
    engineNowEl.textContent = "当前生效：Google（" + name + " 未填 key，已回退）";
    return;
  }

  engineNowEl.textContent = "验证 " + name + " 中…";
  const mine = verifyToken; // ignore stale responses if settings changed again
  chrome.runtime.sendMessage(
    { type: "translate", text: "hello", from: "en", to: "zh-CN" },
    (resp) => {
      if (mine !== verifyToken) return;
      if (!chrome.runtime.lastError && resp && resp.ok && resp.text) {
        engineNowEl.textContent = "当前生效：" + name + " ✓";
      } else {
        engineNowEl.textContent = name + " key 无效或不可用 · 翻译会失败";
      }
    }
  );
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

// Render (and verify) only after storage is written, so the background reads
// the new engine/key when the verification translation runs.
engineEl.addEventListener("change", () => {
  deeplBoxEl.style.display = engineEl.value === "deepl" ? "block" : "none";
  geminiBoxEl.style.display = engineEl.value === "gemini" ? "block" : "none";
  chrome.storage.local.set({ engine: engineEl.value }, renderEngineNow);
});

deeplKeyEl.addEventListener("change", () => {
  chrome.storage.local.set({ deeplKey: deeplKeyEl.value.trim() }, renderEngineNow);
});

geminiKeyEl.addEventListener("change", () => {
  chrome.storage.local.set({ geminiKey: geminiKeyEl.value.trim() }, renderEngineNow);
});
