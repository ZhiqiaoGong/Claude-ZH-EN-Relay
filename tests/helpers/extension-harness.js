const fs = require("node:fs");
const path = require("node:path");

const ROOT = path.resolve(__dirname, "../..");
const FIXTURE_HTML = fs.readFileSync(
  path.join(ROOT, "tests/fixtures/claude.html"),
  "utf8"
);

async function mountContentScript(page, settings = {}) {
  await page.setContent(FIXTURE_HTML);
  await page.evaluate((initialSettings) => {
    const state = {
      settings: { ...initialSettings },
      messages: [],
      responses: [],
      pendingResponses: [],
      storageListeners: [],
    };

    window.__zerHarness = {
      state,
      enqueue(type, response, delay = 0, manual = false) {
        state.responses.push({ type, response, delay, manual });
      },
      release(type) {
        const index = state.pendingResponses.findIndex(
          (entry) => entry.type === type
        );
        if (index === -1) throw new Error(`no pending ${type} response`);
        const entry = state.pendingResponses.splice(index, 1)[0];
        entry.callback(structuredClone(entry.response));
      },
      changeSettings(next) {
        const changes = {};
        for (const [key, value] of Object.entries(next)) {
          changes[key] = { oldValue: state.settings[key], newValue: value };
          state.settings[key] = value;
        }
        for (const listener of state.storageListeners) {
          listener(changes, "local");
        }
      },
      setRuntimeId(value) {
        window.chrome.runtime.id = value;
      },
    };

    window.chrome = {
      storage: {
        local: {
          get(defaults, callback) {
            const result = { ...defaults, ...state.settings };
            queueMicrotask(() => callback(result));
          },
        },
        onChanged: {
          addListener(listener) {
            state.storageListeners.push(listener);
          },
        },
      },
      runtime: {
        id: "test-extension",
        lastError: null,
        sendMessage(message, callback) {
          state.messages.push(structuredClone(message));
          const index = state.responses.findIndex(
            (entry) => entry.type === message.type
          );
          const entry =
            index === -1
              ? {
                  response: {
                    ok: false,
                    error: { code: "unmocked_request" },
                  },
                  delay: 0,
                }
              : state.responses.splice(index, 1)[0];
          if (entry.manual) {
            state.pendingResponses.push({
              type: message.type,
              response: entry.response,
              callback,
            });
          } else {
            setTimeout(
              () => callback(structuredClone(entry.response)),
              entry.delay
            );
          }
        },
      },
    };

    document.execCommand = (command, _showUi, value) => {
      if (command !== "insertText") return false;
      const selection = window.getSelection();
      const anchor = selection && selection.anchorNode;
      const element =
        anchor && anchor.nodeType === Node.ELEMENT_NODE
          ? anchor
          : anchor && anchor.parentElement;
      const editor = element && element.closest("[contenteditable]");
      if (!editor) return false;
      editor.textContent = String(value);
      editor.dispatchEvent(
        new InputEvent("input", {
          bubbles: true,
          inputType: "insertText",
          data: String(value),
        })
      );
      return true;
    };
  }, settings);

  await page.addStyleTag({ path: path.join(ROOT, "overlay.css") });
  await page.addScriptTag({ path: path.join(ROOT, "content.js") });
  await page.evaluate(() => new Promise((resolve) => requestAnimationFrame(resolve)));
}

async function enqueueResponse(
  page,
  type,
  response,
  delay = 0
) {
  await page.evaluate(
    ({ requestType, payload, wait }) => {
      window.__zerHarness.enqueue(requestType, payload, wait);
    },
    { requestType: type, payload: response, wait: delay }
  );
}

async function enqueueDeferredResponse(page, type, response) {
  await page.evaluate(
    ({ requestType, payload }) => {
      window.__zerHarness.enqueue(requestType, payload, 0, true);
    },
    { requestType: type, payload: response }
  );
}

async function releaseResponse(page, type) {
  await page.evaluate((requestType) => {
    window.__zerHarness.release(requestType);
  }, type);
}

async function changeSettings(page, next) {
  await page.evaluate((values) => {
    window.__zerHarness.changeSettings(values);
  }, next);
}

async function setComposer(page, text) {
  await page.locator("#chat-editor").evaluate((editor, value) => {
    editor.textContent = value;
    editor.dispatchEvent(
      new InputEvent("input", {
        bubbles: true,
        inputType: "insertText",
        data: value,
      })
    );
    editor.focus();
  }, text);
}

async function messages(page, type) {
  return page.evaluate((requestType) => {
    const all = window.__zerHarness.state.messages;
    return requestType ? all.filter((msg) => msg.type === requestType) : all;
  }, type);
}

async function sentMessages(page) {
  return page.evaluate(() => window.__fixture.sent);
}

async function addReply(page, html, { streaming = false } = {}) {
  return page.evaluate(
    ({ body, isStreaming }) => {
      const turn = document.createElement("article");
      turn.setAttribute("data-is-streaming", String(isStreaming));
      turn.innerHTML = `<div class="font-claude-response">${body}</div>`;
      document.querySelector("#conversation").appendChild(turn);
      return true;
    },
    { body: html, isStreaming: streaming }
  );
}

async function addUserBubble(page, html) {
  await page.evaluate((body) => {
    const bubble = document.createElement("div");
    bubble.setAttribute("data-testid", "user-message");
    bubble.innerHTML = body;
    document.querySelector("#conversation").appendChild(bubble);
  }, html);
}

async function mountBackground(page, settings = {}) {
  await page.setContent("<!doctype html><title>Background harness</title>");
  await page.evaluate((initialSettings) => {
    const state = {
      settings: { ...initialSettings },
      fetches: [],
      fetchQueue: [],
      listener: null,
    };
    window.__backgroundHarness = {
      state,
      enqueueFetch(entry) {
        state.fetchQueue.push(entry);
      },
      async invoke(message) {
        return new Promise((resolve) => {
          const keepOpen = state.listener(message, {}, resolve);
          if (!keepOpen) resolve({ __noResponse: true });
        });
      },
    };

    window.chrome = {
      storage: {
        local: {
          async get(keys) {
            return Object.fromEntries(
              keys.map((key) => [key, state.settings[key] || ""])
            );
          },
        },
      },
      runtime: {
        onMessage: {
          addListener(listener) {
            state.listener = listener;
          },
        },
      },
    };

    window.fetch = async (url, options = {}) => {
      state.fetches.push({
        url: String(url),
        method: options.method || "GET",
        headers: options.headers || {},
        body: options.body || null,
      });
      const entry = state.fetchQueue.shift();
      if (!entry) throw new Error("unmocked fetch");
      if (entry.error) {
        const error = new Error(entry.error.message || entry.error);
        if (entry.error.name) error.name = entry.error.name;
        throw error;
      }
      return {
        ok: entry.status >= 200 && entry.status < 300,
        status: entry.status,
        async json() {
          return structuredClone(entry.json);
        },
      };
    };
  }, settings);
  await page.addScriptTag({ path: path.join(ROOT, "background.js") });
}

async function enqueueFetch(page, entry) {
  await page.evaluate((value) => {
    window.__backgroundHarness.enqueueFetch(value);
  }, entry);
}

async function invokeBackground(page, message) {
  return page.evaluate((value) => {
    return window.__backgroundHarness.invoke(value);
  }, message);
}

async function fetches(page) {
  return page.evaluate(() => window.__backgroundHarness.state.fetches);
}

module.exports = {
  addReply,
  addUserBubble,
  changeSettings,
  enqueueFetch,
  enqueueDeferredResponse,
  enqueueResponse,
  fetches,
  invokeBackground,
  messages,
  mountBackground,
  mountContentScript,
  releaseResponse,
  sentMessages,
  setComposer,
};
