// Service worker: performs cross-origin translation calls on behalf of the
// content script. Routing fetch through the background avoids CORS issues and
// keeps the DeepL API key out of the page context.

// Translate text using Google's unofficial gtx endpoint. No API key required,
// but it is unofficial and may rate-limit or break.
async function googleTranslate(text, from, to) {
  const url =
    "https://translate.googleapis.com/translate_a/single" +
    "?client=gtx" +
    "&sl=" + encodeURIComponent(from) +
    "&tl=" + encodeURIComponent(to) +
    "&dt=t&q=" + encodeURIComponent(text);

  // Time out the request so a slow/hung endpoint never stalls the caller.
  const ctrl = new AbortController();
  const timer = setTimeout(() => ctrl.abort(), 10000);
  try {
    const res = await fetch(url, { signal: ctrl.signal });
    if (!res.ok) throw new Error("translate HTTP " + res.status);
    const data = await res.json();
    // Response shape: [[[translatedSegment, originalSegment, ...], ...], ...].
    if (!Array.isArray(data) || !Array.isArray(data[0])) {
      throw new Error("unexpected translate response");
    }
    return data[0].map((seg) => (seg && seg[0]) || "").join("");
  } finally {
    clearTimeout(timer);
  }
}

// Translate a list of strings sequentially (gentle on the unofficial endpoint).
// A single failure yields null for that item and does not abort the batch, so
// the caller always gets a full array back and never hangs.
async function googleTranslateBatch(texts, from, to) {
  const out = [];
  for (const t of texts) {
    if (!t) {
      out.push("");
      continue;
    }
    try {
      out.push(await googleTranslate(t, from, to));
    } catch (e) {
      out.push(null);
    }
  }
  return out;
}

// DeepL wants uppercase language codes; we only deal with Chinese and English.
function toDeepL(code) {
  return String(code).toLowerCase().startsWith("zh") ? "ZH" : "EN";
}

// Translate a batch through DeepL in a single request. Free keys end with ":fx"
// and use the api-free host; paid keys use api.deepl.com. On any failure this
// throws, so the caller falls back to a retry (same as a failed Google batch).
async function deeplTranslateBatch(texts, from, to, key) {
  const k = key.trim();
  const base = k.endsWith(":fx")
    ? "https://api-free.deepl.com"
    : "https://api.deepl.com";

  const params = new URLSearchParams();
  texts.forEach((t) => params.append("text", t || " "));
  params.append("source_lang", toDeepL(from));
  params.append("target_lang", toDeepL(to));

  const ctrl = new AbortController();
  const timer = setTimeout(() => ctrl.abort(), 10000);
  try {
    const res = await fetch(base + "/v2/translate", {
      method: "POST",
      headers: {
        Authorization: "DeepL-Auth-Key " + k,
        "Content-Type": "application/x-www-form-urlencoded",
      },
      body: params.toString(),
      signal: ctrl.signal,
    });
    if (!res.ok) throw new Error("deepl HTTP " + res.status);
    const data = await res.json();
    return data.translations.map((t) => t.text);
  } finally {
    clearTimeout(timer);
  }
}

// Pick the engine per the user's settings and translate a batch of strings.
async function translateBatch(texts, from, to) {
  const { engine = "google", deeplKey = "" } = await chrome.storage.local.get([
    "engine",
    "deeplKey",
  ]);
  if (engine === "deepl" && deeplKey.trim()) {
    return deeplTranslateBatch(texts, from, to, deeplKey);
  }
  return googleTranslateBatch(texts, from, to);
}

chrome.runtime.onMessage.addListener((msg, _sender, sendResponse) => {
  if (msg && msg.type === "translate") {
    translateBatch([msg.text], msg.from, msg.to)
      .then((texts) => sendResponse({ ok: true, text: texts[0] }))
      .catch((err) => sendResponse({ ok: false, error: String(err) }));
    return true; // keep the message channel open for the async response
  }
  if (msg && msg.type === "translateBatch") {
    translateBatch(msg.texts, msg.from, msg.to)
      .then((texts) => sendResponse({ ok: true, texts }))
      .catch((err) => sendResponse({ ok: false, error: String(err) }));
    return true;
  }
  return false;
});
