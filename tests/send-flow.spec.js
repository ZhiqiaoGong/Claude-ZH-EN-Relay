const { test, expect } = require("@playwright/test");
const {
  changeSettings,
  enqueueDeferredResponse,
  enqueueResponse,
  messages,
  mountContentScript,
  releaseResponse,
  sentMessages,
  setComposer,
} = require("./helpers/extension-harness");

test("Chinese Enter is blocked and replaced with reviewable English", async ({
  page,
}) => {
  await mountContentScript(page);
  await enqueueResponse(page, "translate", { ok: true, text: "Hello world" });
  await setComposer(page, "你好，世界");

  await page.locator("#chat-editor").press("Enter");

  await expect(page.locator("#chat-editor")).toHaveText("Hello world");
  await expect(page.locator("#zer-review")).toContainText("原文：你好，世界");
  expect(await sentMessages(page)).toEqual([]);
});

test("second Enter confirms and sends the reviewed English", async ({ page }) => {
  await mountContentScript(page);
  await enqueueResponse(page, "translate", { ok: true, text: "Hello" });
  await setComposer(page, "你好");
  await page.locator("#chat-editor").press("Enter");
  await expect(page.locator("#zer-review")).toBeVisible();

  await page.locator("#chat-editor").press("Enter");

  expect(await sentMessages(page)).toEqual([
    { kind: "keyboard", text: "Hello" },
  ]);
  await expect(page.locator("#zer-review")).toBeHidden();
});

test("Escape restores the exact original without sending", async ({ page }) => {
  await mountContentScript(page);
  await enqueueResponse(page, "translate", { ok: true, text: "Hello" });
  await setComposer(page, "你 好");
  await page.locator("#chat-editor").press("Enter");
  await expect(page.locator("#chat-editor")).toHaveText("Hello");

  await page.locator("#chat-editor").press("Escape");

  await expect(page.locator("#chat-editor")).toHaveText("你 好");
  await expect(page.locator("#zer-review")).toBeHidden();
  expect(await sentMessages(page)).toEqual([]);
});

test("English input passes through without translation", async ({ page }) => {
  await mountContentScript(page);
  await setComposer(page, "Already English");

  await page.locator("#chat-editor").press("Enter");

  expect(await sentMessages(page)).toEqual([
    { kind: "keyboard", text: "Already English" },
  ]);
  expect(await messages(page)).toEqual([]);
});

test("Shift+Enter is not intercepted as a send", async ({ page }) => {
  await mountContentScript(page);
  await setComposer(page, "中文");

  await page.locator("#chat-editor").press("Shift+Enter");

  expect(await messages(page)).toEqual([]);
  expect(await sentMessages(page)).toEqual([]);
});

test("IME confirmation Enter is not intercepted", async ({ page }) => {
  await mountContentScript(page);
  await setComposer(page, "中文");

  const prevented = await page.locator("#chat-editor").evaluate((editor) => {
    const event = new KeyboardEvent("keydown", {
      key: "Enter",
      code: "Enter",
      bubbles: true,
      cancelable: true,
      isComposing: true,
      keyCode: 229,
    });
    editor.dispatchEvent(event);
    return event.defaultPrevented;
  });

  expect(prevented).toBe(false);
  expect(await messages(page)).toEqual([]);
});

test("repeated Enter while translating creates only one request", async ({
  page,
}) => {
  await mountContentScript(page);
  await enqueueResponse(
    page,
    "translate",
    { ok: true, text: "Delayed English" },
    150
  );
  await setComposer(page, "延迟翻译");

  await page.locator("#chat-editor").press("Enter");
  await page.locator("#chat-editor").press("Enter");
  await page.waitForTimeout(30);

  expect((await messages(page, "translate")).length).toBe(1);
  await expect(page.locator("#zer-bar")).toContainText("翻译中");
  await expect(page.locator("#chat-editor")).toHaveText("Delayed English");
});

test("a changed draft is never overwritten by a late translation", async ({
  page,
}) => {
  await mountContentScript(page);
  await enqueueDeferredResponse(page, "translate", {
    ok: true,
    text: "Stale English",
  });
  await setComposer(page, "旧草稿");
  await page.locator("#chat-editor").press("Enter");
  await expect
    .poll(async () => (await messages(page, "translate")).length)
    .toBe(1);

  await setComposer(page, "用户的新草稿");
  await releaseResponse(page, "translate");

  await expect(page.locator("#zer-bar")).toContainText("输入内容已变更");
  await expect(page.locator("#chat-editor")).toHaveText("用户的新草稿");
  expect(await sentMessages(page)).toEqual([]);
});

test("auto-send sends only the verified English draft", async ({ page }) => {
  await mountContentScript(page, { autoSend: true });
  await enqueueResponse(page, "translate", { ok: true, text: "Safe English" });
  await setComposer(page, "安全发送");

  await page.locator("#chat-editor").press("Enter");

  await expect
    .poll(async () => sentMessages(page))
    .toEqual([{ kind: "click", text: "Safe English" }]);
});

test("auto-send stops when the translated draft changes", async ({ page }) => {
  await mountContentScript(page, { autoSend: true });
  await enqueueResponse(page, "translate", { ok: true, text: "English" });
  await setComposer(page, "原始中文");
  await page.locator("#chat-editor").press("Enter");
  await expect(page.locator("#chat-editor")).toHaveText("English");

  await setComposer(page, "English modified");

  await expect(page.locator("#zer-bar")).toContainText("发送前校验失败");
  expect(await sentMessages(page)).toEqual([]);
});

test("send-button clicks follow the same review and confirm flow", async ({
  page,
}) => {
  await mountContentScript(page);
  await enqueueResponse(page, "translate", { ok: true, text: "Click English" });
  await setComposer(page, "点击发送");

  await page.locator("#send-button").click();
  await expect(page.locator("#zer-review")).toBeVisible();
  expect(await sentMessages(page)).toEqual([]);

  await page.locator("#send-button").click();
  expect(await sentMessages(page)).toEqual([
    { kind: "click", text: "Click English" },
  ]);
});

test("unrelated contenteditable areas are never intercepted", async ({ page }) => {
  await mountContentScript(page);
  await page.locator("#other-editor").fill("中文笔记");

  await page.locator("#other-editor").press("Enter");

  expect(await page.evaluate(() => window.__fixture.secondaryEnters)).toBe(1);
  expect(await messages(page)).toEqual([]);
});

test("a failed translation requires a second explicit Enter to send Chinese", async ({
  page,
}) => {
  await mountContentScript(page);
  await enqueueResponse(page, "translate", {
    ok: false,
    error: { code: "rate_limit", status: 429 },
  });
  await setComposer(page, "保留原文");

  await page.locator("#chat-editor").press("Enter");
  await expect(page.locator("#zer-bar")).toContainText("429");
  expect(await sentMessages(page)).toEqual([]);

  await page.locator("#chat-editor").press("Enter");
  expect(await sentMessages(page)).toEqual([
    { kind: "keyboard", text: "保留原文" },
  ]);
});

test("disabling the extension during review restores the original", async ({
  page,
}) => {
  await mountContentScript(page);
  await enqueueResponse(page, "translate", { ok: true, text: "Translated" });
  await setComposer(page, "恢复原文");
  await page.locator("#chat-editor").press("Enter");
  await expect(page.locator("#zer-review")).toBeVisible();

  await changeSettings(page, { enabled: false });

  await expect(page.locator("#chat-editor")).toHaveText("恢复原文");
  await expect(page.locator("#zer-review")).toBeHidden();
});

test("Chinese added to a reviewed translation is translated again, not sent", async ({
  page,
}) => {
  await mountContentScript(page);
  await enqueueResponse(page, "translate", { ok: true, text: "First English" });
  await enqueueResponse(page, "translate", { ok: true, text: "Second English" });
  await setComposer(page, "第一版");
  await page.locator("#chat-editor").press("Enter");
  await expect(page.locator("#chat-editor")).toHaveText("First English");

  await setComposer(page, "First English 加一句");
  await page.locator("#chat-editor").press("Enter");

  await expect(page.locator("#chat-editor")).toHaveText("Second English");
  expect((await messages(page, "translate")).length).toBe(2);
  expect(await sentMessages(page)).toEqual([]);
});
