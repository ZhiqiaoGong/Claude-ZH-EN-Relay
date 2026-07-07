// Service worker: performs cross-origin translation calls on behalf of the
// content script. Routing fetch through the background avoids CORS issues and
// keeps any future API keys out of the page context.

// Translate text using Google's unofficial gtx endpoint. No API key required,
// but it is unofficial and may rate-limit or break. DeepL can be added later
// as a keyed alternative behind the same message interface.
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

chrome.runtime.onMessage.addListener((msg, _sender, sendResponse) => {
  if (msg && msg.type === "translate") {
    googleTranslate(msg.text, msg.from, msg.to)
      .then((text) => sendResponse({ ok: true, text }))
      .catch((err) => sendResponse({ ok: false, error: String(err) }));
    return true; // keep the message channel open for the async response
  }
  if (msg && msg.type === "translateBatch") {
    googleTranslateBatch(msg.texts, msg.from, msg.to)
      .then((texts) => sendResponse({ ok: true, texts }))
      .catch((err) => sendResponse({ ok: false, error: String(err) }));
    return true;
  }
  return false;
});
