// Content script for claude.ai.
//
// Job: when the user is about to send a message that contains Chinese, block
// the send, translate the text to English, write the English back into the
// ProseMirror editor so the user can review it, then let claude.ai send it
// through its own normal machinery. We never touch network requests.
//
// The translated English is visible in the box before it goes out, which is
// also the safeguard against silent mistranslation on the input side.

(function () {
  "use strict";

  const CJK_RE = /[㐀-鿿豈-﫿]/; // covers common + ext-A Hanzi

  const settings = {
    enabled: true,
    autoSend: false,
    translateReplies: true,
    replyMode: "hybrid", // "hybrid" | "overlay" | "append"
    from: "zh-CN",
    to: "en",
  };

  // pendingConfirm: we have already translated and are waiting for the user to
  // press Enter again (or click send) to actually send the English text.
  let pendingConfirm = false;
  let originalText = ""; // stashed Chinese, for undo
  let activeEditor = null; // last focused editable, for the click path

  console.log("[ZER] content script loaded on", location.href);

  // ---- settings ----------------------------------------------------------
  chrome.storage.local.get(settings, (stored) => Object.assign(settings, stored));
  chrome.storage.onChanged.addListener((changes, area) => {
    if (area !== "local") return;
    for (const key of Object.keys(changes)) {
      if (key in settings) settings[key] = changes[key].newValue;
    }
    // Changing the engine or a key invalidates cached translations.
    if ("engine" in changes || "deeplKey" in changes || "geminiKey" in changes)
      trCache.clear();

    // Re-render existing replies when the layout, toggle, or engine changes.
    if (
      "replyMode" in changes ||
      "translateReplies" in changes ||
      "engine" in changes ||
      "deeplKey" in changes ||
      "geminiKey" in changes
    ) {
      resetTranslations();
      if (settings.enabled && settings.translateReplies) {
        document.querySelectorAll(REPLY_SEL).forEach(scheduleReply);
      }
    }
  });

  // ---- editor helpers ----------------------------------------------------
  // Match any contenteditable, not just ProseMirror by class name, so we are
  // robust to claude.ai's exact markup.
  function getEditor(node) {
    const el = node && node.nodeType === 3 ? node.parentElement : node;
    if (!el || !el.closest) return null;
    const ce = el.closest("[contenteditable]");
    if (!ce || ce.getAttribute("contenteditable") === "false") return null;
    return ce;
  }

  document.addEventListener(
    "focusin",
    (e) => {
      const ed = getEditor(e.target);
      if (ed) activeEditor = ed;
    },
    true
  );

  function getPlainText(editor) {
    return (editor.innerText || "").replace(/ /g, " ").trim();
  }

  // Reliably replace the editor content with `text`. ProseMirror ignores raw
  // DOM mutation, so we go through execCommand('insertText') on a full
  // selection, which fires the input events ProseMirror listens for. A
  // synthetic paste is used as a fallback.
  function writeText(editor, text) {
    editor.focus();
    const sel = window.getSelection();
    const range = document.createRange();
    range.selectNodeContents(editor);
    sel.removeAllRanges();
    sel.addRange(range);

    const ok = document.execCommand("insertText", false, text);
    if (ok) return true;

    try {
      const dt = new DataTransfer();
      dt.setData("text/plain", text);
      editor.dispatchEvent(
        new ClipboardEvent("paste", {
          clipboardData: dt,
          bubbles: true,
          cancelable: true,
        })
      );
      return true;
    } catch (e) {
      return false;
    }
  }

  function findSendButton(editor) {
    const scope = editor.closest("form") || document;
    return scope.querySelector(
      'button[aria-label*="Send" i], button[aria-label*="send" i]'
    );
  }

  function triggerSend(editor) {
    const btn = findSendButton(editor);
    if (btn && !btn.disabled) {
      btn.click();
      return;
    }
    // Fallback: the English text has no CJK, so our own handler passes it
    // through and claude.ai handles this Enter as a normal send.
    editor.dispatchEvent(
      new KeyboardEvent("keydown", {
        key: "Enter",
        code: "Enter",
        bubbles: true,
        cancelable: true,
      })
    );
  }

  // ---- translation -------------------------------------------------------
  // True once the extension has been reloaded/updated out from under this
  // (now orphaned) content script. chrome.runtime then becomes unusable.
  let contextInvalid = false;
  function markContextInvalid() {
    if (contextInvalid) return;
    contextInvalid = true;
    outInFlight = 0;
    updateOutStatus();
    showBar("译发已更新或重载 · 请刷新此页面", "zer-warn");
  }

  // Send a message to the background and always settle: on reply, on error,
  // after a timeout, or if the extension context is gone — so a dead worker or
  // an orphaned content script never leaves callers hanging (or throws).
  function sendWithTimeout(msg, ms, onResp) {
    return new Promise((resolve) => {
      let done = false;
      const finish = (v) => {
        if (!done) {
          done = true;
          resolve(v);
        }
      };
      // chrome.runtime.id is undefined once the context is invalidated.
      if (!chrome.runtime || !chrome.runtime.id) {
        markContextInvalid();
        finish(null);
        return;
      }
      const timer = setTimeout(() => finish(null), ms);
      try {
        chrome.runtime.sendMessage(msg, (resp) => {
          clearTimeout(timer);
          if (chrome.runtime.lastError || !resp || !resp.ok) finish(null);
          else finish(onResp(resp));
        });
      } catch (e) {
        clearTimeout(timer);
        markContextInvalid();
        finish(null);
      }
    });
  }

  function translate(text) {
    return sendWithTimeout(
      { type: "translate", text, from: settings.from, to: settings.to },
      30000,
      (resp) => resp.text
    );
  }

  // ---- status bar --------------------------------------------------------
  let barEl = null;
  function showBar(html, kind) {
    if (!barEl) {
      barEl = document.createElement("div");
      barEl.id = "zer-bar";
      document.body.appendChild(barEl);
    }
    barEl.className = kind || "";
    barEl.innerHTML = html;
    barEl.style.display = "block";
    // Sit just above the composer so it never covers the translated text.
    const composer =
      document.querySelector('[data-chat-input-container="true"]') ||
      (activeEditor && activeEditor.closest("fieldset"));
    if (composer) {
      const r = composer.getBoundingClientRect();
      barEl.style.bottom = window.innerHeight - r.top + 8 + "px";
    }
  }
  function hideBar() {
    if (barEl) barEl.style.display = "none";
  }

  // ---- core flow ---------------------------------------------------------
  async function handleSendIntent(editor, e) {
    // Orphaned content script: don't block the send, just prompt a reload.
    if (contextInvalid) {
      markContextInvalid();
      return;
    }
    const text = getPlainText(editor);
    if (!text) return; // nothing to do, let it through
    if (!CJK_RE.test(text)) return; // already English, let it through

    // Block claude.ai's own send handler for this event.
    e.preventDefault();
    e.stopImmediatePropagation();

    originalText = text;
    showBar("翻译中…", "zer-info");

    const english = await translate(text);
    if (!english) {
      showBar("翻译失败 · 回车按原文发送 · Esc 取消", "zer-warn");
      // Leave the Chinese in place; treat next Enter as a plain send.
      pendingConfirm = true;
      return;
    }

    writeText(editor, english);

    if (settings.autoSend) {
      pendingConfirm = false;
      // Give claude.ai a moment to register the English text in its own state
      // before we send; sending immediately can fire off the stale Chinese.
      showBar("已译为英文 · 发送中…", "zer-info");
      setTimeout(() => {
        hideBar();
        triggerSend(editor);
      }, 150);
      return;
    }

    pendingConfirm = true;
    showBar("已译为英文 · <b>回车</b>发送 · <b>Esc</b> 撤回", "zer-ok");
  }

  function restoreOriginal(editor) {
    if (originalText) writeText(editor, originalText);
    originalText = "";
    pendingConfirm = false;
    hideBar();
  }

  // Single capturing keydown handler at document level: robust to the SPA
  // re-rendering the editor, and runs before claude.ai's own listeners.
  document.addEventListener(
    "keydown",
    (e) => {
      if (!settings.enabled) return;

      const editor = getEditor(e.target);
      if (!editor) return;
      activeEditor = editor;

      if (e.key === "Escape" && pendingConfirm) {
        e.preventDefault();
        e.stopImmediatePropagation();
        restoreOriginal(editor);
        return;
      }

      // Only Enter without modifiers sends; Shift+Enter is a newline. Skip
      // while an IME is composing (Enter there just confirms candidates).
      if (e.key !== "Enter" || e.shiftKey || e.isComposing || e.keyCode === 229) {
        return;
      }

      if (pendingConfirm) {
        // Second Enter: user confirmed. Let claude.ai send the English text.
        pendingConfirm = false;
        hideBar();
        return;
      }

      handleSendIntent(editor, e);
    },
    true // capture
  );

  // Also intercept clicks on the send button (mouse-driven send).
  document.addEventListener(
    "click",
    (e) => {
      if (!settings.enabled || pendingConfirm) return;
      const btn = e.target.closest && e.target.closest("button");
      if (!btn) return;
      const label = (btn.getAttribute("aria-label") || "").toLowerCase();
      if (!label.includes("send")) return;

      const editor = activeEditor || getEditor(document.activeElement);
      if (!editor) return;
      const text = getPlainText(editor);
      if (!text || !CJK_RE.test(text)) return;

      e.preventDefault();
      e.stopImmediatePropagation();
      handleSendIntent(editor, e);
    },
    true
  );

  // =======================================================================
  // Output side: translate finished assistant replies (English) to Chinese,
  // in place, with click-to-toggle back to the original.
  // =======================================================================

  // Assistant message containers. font-claude-response is the confirmed
  // current one; font-claude-message kept as a fallback for other layouts.
  const REPLY_SELECTORS = [
    "div.font-claude-response",
    "div.font-claude-message",
  ];
  const REPLY_SEL = REPLY_SELECTORS.join(",");
  const DONE_ATTR = "data-zer-done";

  const settleTimers = new WeakMap();

  function findReply(node) {
    const el = node && node.nodeType === 3 ? node.parentElement : node;
    if (!el || !el.closest) return null;
    return el.closest(REPLY_SEL);
  }

  // Collect innermost block elements that carry translatable text. We keep
  // blocks that contain inline code/links now — the reply mode decides how to
  // render them. Standalone code blocks (<pre>) are never translated.
  function collectBlocks(root) {
    const all = Array.from(
      root.querySelectorAll("p, li, h1, h2, h3, h4, h5, blockquote")
    );
    const picked = all.filter((n) => {
      if (n.closest("pre, code")) return false; // inside code
      if (n.querySelector("pre")) return false; // wraps a block-level code element
      const txt = n.textContent.trim();
      if (!txt) return false;
      if (CJK_RE.test(txt)) return false; // already Chinese
      return true;
    });
    // keep only leaf-most nodes (drop any that contain another picked node)
    return picked.filter((n) => !picked.some((o) => o !== n && n.contains(o)));
  }

  // A block has structure worth preserving (verbatim) if it holds inline code
  // or a link. Bold/italic are considered safe to flatten.
  function hasProtectedInline(node) {
    return node.querySelector("code, a") !== null;
  }

  // Decide how a block is rendered under the current mode:
  //   "overlay" - replace text in place (compact, click to reveal original)
  //   "append"  - keep the original untouched, add a Chinese line below
  //   "skip"    - leave it as-is (prose-only mode leaves code paragraphs English)
  function decideRender(node) {
    const protectedInline = hasProtectedInline(node);
    if (settings.replyMode === "overlay") {
      return protectedInline ? "skip" : "overlay";
    }
    if (settings.replyMode === "append") return "append";
    // hybrid
    return protectedInline ? "append" : "overlay";
  }

  function applyOverlay(node, orig, translated) {
    if (!translated) return;
    node.setAttribute("data-zer-orig", orig);
    node.setAttribute("data-zer-tr", translated);
    node.setAttribute("data-zer-showing", "tr");
    node.textContent = translated;
    node.classList.add("zer-tr");
  }

  function applyAppend(node, translated) {
    if (!translated) return;
    const next = node.nextElementSibling;
    if (next && next.classList.contains("zer-append")) return; // already done
    const div = document.createElement("div");
    div.className = "zer-append";
    div.textContent = translated;
    node.after(div);
  }

  // Undo all applied translations (both modes), so a mode switch can re-render.
  function resetTranslations() {
    document.querySelectorAll(".zer-tr").forEach((n) => {
      const orig = n.getAttribute("data-zer-orig");
      if (orig != null) n.textContent = orig;
      n.classList.remove("zer-tr");
      n.removeAttribute("data-zer-orig");
      n.removeAttribute("data-zer-tr");
      n.removeAttribute("data-zer-showing");
    });
    document.querySelectorAll(".zer-append").forEach((n) => n.remove());
    document
      .querySelectorAll("[" + DONE_ATTR + "]")
      .forEach((n) => n.removeAttribute(DONE_ATTR));
  }

  function translateBatch(texts) {
    return sendWithTimeout(
      { type: "translateBatch", texts, from: settings.to, to: settings.from },
      30000,
      (resp) => resp.texts
    );
  }

  // Cache of reply translations (English -> Chinese) so re-rendering after a
  // layout-mode switch is instant and never re-hits the network. Capped so a
  // long session cannot grow it without bound (oldest entries drop first).
  const trCache = new Map();
  const TR_CACHE_CAP = 2000;
  function cacheSet(k, v) {
    trCache.set(k, v);
    if (trCache.size > TR_CACHE_CAP) trCache.delete(trCache.keys().next().value);
  }
  async function cachedTranslateBatch(texts) {
    const out = new Array(texts.length);
    const missIdx = [];
    const missTexts = [];
    texts.forEach((t, i) => {
      if (trCache.has(t)) out[i] = trCache.get(t);
      else {
        missIdx.push(i);
        missTexts.push(t);
      }
    });
    if (missTexts.length) {
      const got = await translateBatch(missTexts);
      if (!got) return null; // network failure: signal a retry
      got.forEach((v, j) => {
        out[missIdx[j]] = v;
        if (v != null) cacheSet(missTexts[j], v);
      });
    }
    return out;
  }

  async function translateReply(el) {
    if (contextInvalid || el.hasAttribute(DONE_ATTR)) return;

    // Decide per block, dropping any this mode leaves untouched, so we do not
    // waste translation calls on skipped paragraphs.
    const items = [];
    for (const node of collectBlocks(el)) {
      const how = decideRender(node);
      if (how === "skip") continue;
      items.push({ node, how });
    }
    if (!items.length) return;
    el.setAttribute(DONE_ATTR, "1"); // claim before mutating, prevents re-entry

    const texts = items.map((it) => it.node.textContent.trim());
    outInFlight++;
    updateOutStatus();
    const out = await cachedTranslateBatch(texts);
    outInFlight--;
    updateOutStatus();
    if (!out) {
      el.removeAttribute(DONE_ATTR); // allow a later retry
      flashOutError();
      return;
    }
    items.forEach((it, i) => {
      if (it.how === "overlay") applyOverlay(it.node, texts[i], out[i]);
      else applyAppend(it.node, out[i]);
    });
  }

  // ---- output-side status indicator (top-right) --------------------------
  let outInFlight = 0;
  let outEl = null;
  function outNode() {
    if (!outEl) {
      outEl = document.createElement("div");
      outEl.id = "zer-out";
      document.body.appendChild(outEl);
    }
    return outEl;
  }
  function updateOutStatus() {
    const n = outNode();
    if (outInFlight > 0) {
      n.className = "zer-info";
      n.textContent = "正在翻译回复…";
      n.style.display = "block";
      n.onclick = null;
    } else {
      n.style.display = "none";
    }
  }
  function flashOutError() {
    const n = outNode();
    n.className = "zer-warn";
    n.textContent = "回复翻译失败 · 点此重试";
    n.style.display = "block";
    n.onclick = () => {
      n.style.display = "none";
      document.querySelectorAll(REPLY_SEL).forEach(scheduleReply);
    };
  }

  // claude.ai marks the still-generating turn with data-is-streaming="true".
  function isStreaming(el) {
    const s = el.closest("[data-is-streaming]");
    return s ? s.getAttribute("data-is-streaming") === "true" : false;
  }

  // Translate once the reply is done: while it is still streaming just check
  // back; when it settles, translate after a short beat. Faster and more
  // reliable than waiting out a fixed pause after the last mutation.
  function scheduleReply(el) {
    if (el.hasAttribute(DONE_ATTR)) return;
    clearTimeout(settleTimers.get(el));
    settleTimers.set(
      el,
      setTimeout(() => {
        if (isStreaming(el)) scheduleReply(el);
        else translateReply(el);
      }, isStreaming(el) ? 600 : 400)
    );
  }

  const replyObserver = new MutationObserver((muts) => {
    if (!settings.enabled || !settings.translateReplies) return;
    for (const m of muts) {
      if (m.type === "attributes") {
        // the streaming flag flipped: (re)check replies inside this turn
        m.target.querySelectorAll &&
          m.target.querySelectorAll(REPLY_SEL).forEach(scheduleReply);
        continue;
      }
      const reply = findReply(m.target);
      if (reply) scheduleReply(reply);
    }
  });
  replyObserver.observe(document.body, {
    subtree: true,
    childList: true,
    characterData: true,
    attributes: true,
    attributeFilter: ["data-is-streaming"],
  });

  // Initial sweep for replies already on the page at load.
  setTimeout(() => {
    if (!settings.enabled || !settings.translateReplies) return;
    document.querySelectorAll(REPLY_SEL).forEach(scheduleReply);
  }, 2000);

  // Click a translated block to toggle between Chinese and the original.
  document.addEventListener("click", (e) => {
    const node = e.target.closest && e.target.closest(".zer-tr");
    if (!node) return;
    if (!window.getSelection().isCollapsed) return; // user is selecting text
    const showingTr = node.getAttribute("data-zer-showing") !== "orig";
    node.textContent = node.getAttribute(
      showingTr ? "data-zer-orig" : "data-zer-tr"
    );
    node.setAttribute("data-zer-showing", showingTr ? "orig" : "tr");
  });

  // =======================================================================
  // Select-to-translate: highlight any text, get a floating popup. Direction
  // is auto-detected (Chinese -> English, otherwise -> Chinese). This is the
  // precision tool for content the auto pass handles imperfectly.
  // =======================================================================

  let selPill = null;
  let selPopup = null;

  function removeSelUI() {
    if (selPill) {
      selPill.remove();
      selPill = null;
    }
    if (selPopup) {
      selPopup.remove();
      selPopup = null;
    }
  }

  // Anchor floating UI to the cursor (mouse-release point) rather than to the
  // selection box, so it stays clear of claude.ai's own selection tooltip.
  function placeAt(node, x, y, w) {
    node.style.left = Math.max(4, Math.min(x, window.innerWidth - w - 4)) + "px";
    node.style.top = y + "px";
  }

  function openPopup(x, y, text) {
    const toZh = !CJK_RE.test(text);
    selPopup = document.createElement("div");
    selPopup.id = "zer-popup";
    selPopup.textContent = "翻译中…";
    placeAt(selPopup, x, y, 360);
    document.body.appendChild(selPopup);

    sendWithTimeout(
      {
        type: "translate",
        text,
        from: toZh ? "en" : "zh-CN",
        to: toZh ? "zh-CN" : "en",
      },
      15000,
      (resp) => resp.text
    ).then((translated) => {
      if (!selPopup) return;
      if (translated == null) {
        selPopup.textContent = "翻译失败";
        selPopup.className = "zer-fail";
      } else {
        selPopup.textContent = translated;
        selPopup.className = "";
      }
    });
  }

  document.addEventListener("mouseup", (e) => {
    if (!settings.enabled) return;
    if (e.target.closest && e.target.closest("#zer-pill, #zer-popup")) return;
    // pill sits just below-right of where the mouse was released
    const px = e.clientX + 8;
    const py = e.clientY + 12;
    // let the selection settle after the mouseup
    setTimeout(() => {
      const sel = window.getSelection();
      const text = sel && sel.toString().trim();
      removeSelUI();
      if (!text || text.length < 2) return;

      selPill = document.createElement("div");
      selPill.id = "zer-pill";
      selPill.textContent = "译";
      placeAt(selPill, px, py, 24);
      document.body.appendChild(selPill);

      // keep the selection alive when pressing the pill
      selPill.addEventListener("mousedown", (ev) => ev.preventDefault());
      selPill.addEventListener("click", () => {
        if (selPill) {
          selPill.remove();
          selPill = null;
        }
        openPopup(px, py, text);
      });
    }, 10);
  });

  // dismiss the popup/pill when clicking elsewhere
  document.addEventListener("mousedown", (e) => {
    if (e.target.closest && e.target.closest("#zer-pill, #zer-popup")) return;
    removeSelUI();
  });
})();
