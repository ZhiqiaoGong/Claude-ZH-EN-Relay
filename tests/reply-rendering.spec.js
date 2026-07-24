const { test, expect } = require("@playwright/test");
const {
  addReply,
  addUserBubble,
  changeSettings,
  enqueueResponse,
  messages,
  mountContentScript,
  sentMessages,
  setComposer,
} = require("./helpers/extension-harness");

test("hybrid mode translates prose while preserving inline and block code", async ({
  page,
}) => {
  await mountContentScript(page, { replyMode: "hybrid" });
  await enqueueResponse(page, "translateBatch", {
    ok: true,
    texts: ["使用这条命令。", "现在运行 npm test。"],
  });

  await addReply(
    page,
    [
      '<p id="plain">Use this command.</p>',
      '<p id="inline">Run <code>npm test</code> now.</p>',
      '<pre id="block"><code>npm test</code></pre>',
    ].join("")
  );

  await expect(page.locator("#plain")).toHaveText("使用这条命令。");
  await expect(page.locator("#plain")).toHaveClass(/zer-tr/);
  await expect(page.locator("#inline")).toContainText("npm test");
  await expect(page.locator("#inline + .zer-append")).toHaveText(
    "现在运行 npm test。"
  );
  await expect(page.locator("#block")).toHaveText("npm test");
});

test("clicking translated prose toggles original and translation", async ({
  page,
}) => {
  await mountContentScript(page);
  await enqueueResponse(page, "translateBatch", {
    ok: true,
    texts: ["中文回复"],
  });
  await addReply(page, '<p id="toggle">English reply</p>');
  await expect(page.locator("#toggle")).toHaveText("中文回复");

  await page.locator("#toggle").click();
  await expect(page.locator("#toggle")).toHaveText("English reply");

  await page.locator("#toggle").click();
  await expect(page.locator("#toggle")).toHaveText("中文回复");
});

test("overlay mode skips blocks containing code or links", async ({ page }) => {
  await mountContentScript(page, { replyMode: "overlay" });
  await enqueueResponse(page, "translateBatch", {
    ok: true,
    texts: ["普通中文"],
  });
  await addReply(
    page,
    '<p id="plain">Plain text</p><p id="protected">Open <a href="#">docs</a></p>'
  );

  await expect(page.locator("#plain")).toHaveText("普通中文");
  await expect(page.locator("#protected")).toHaveText("Open docs");
  await expect(page.locator(".zer-append")).toHaveCount(0);
  const requests = await messages(page, "translateBatch");
  expect(requests[0].texts).toEqual(["Plain text"]);
});

test("append mode preserves every original block and adds translations", async ({
  page,
}) => {
  await mountContentScript(page, { replyMode: "append" });
  await enqueueResponse(page, "translateBatch", {
    ok: true,
    texts: ["第一段", "第二段"],
  });
  await addReply(
    page,
    '<p id="one">First</p><p id="two">Run <code>x()</code></p>'
  );

  await expect(page.locator("#one")).toHaveText("First");
  await expect(page.locator("#one + .zer-append")).toHaveText("第一段");
  await expect(page.locator("#two")).toContainText("x()");
  await expect(page.locator("#two + .zer-append")).toHaveText("第二段");
});

test("streaming replies are not translated until the turn completes", async ({
  page,
}) => {
  await mountContentScript(page);
  await enqueueResponse(page, "translateBatch", {
    ok: true,
    texts: ["完成"],
  });
  await addReply(page, '<p id="streaming">Still streaming</p>', {
    streaming: true,
  });

  await page.waitForTimeout(750);
  expect(await messages(page, "translateBatch")).toEqual([]);
  await expect(page.locator("#streaming")).toHaveText("Still streaming");

  await page
    .locator('[data-is-streaming="true"]')
    .evaluate((turn) => turn.setAttribute("data-is-streaming", "false"));
  await expect(page.locator("#streaming")).toHaveText("完成");
});

test("partial batch failure stays retryable and reuses successful cache entries", async ({
  page,
}) => {
  await mountContentScript(page);
  await enqueueResponse(page, "translateBatch", {
    ok: true,
    texts: ["缓存成功", null],
  });
  await addReply(page, '<p id="first">First</p><p id="second">Second</p>');

  await expect(page.locator("#zer-out")).toContainText("点此重试");
  await expect(page.locator("#first")).toHaveText("First");
  await enqueueResponse(page, "translateBatch", {
    ok: true,
    texts: ["第二次成功"],
  });

  await page.locator("#zer-out").click();

  await expect(page.locator("#first")).toHaveText("缓存成功");
  await expect(page.locator("#second")).toHaveText("第二次成功");
  const requests = await messages(page, "translateBatch");
  expect(requests).toHaveLength(2);
  expect(requests[0].texts).toEqual(["First", "Second"]);
  expect(requests[1].texts).toEqual(["Second"]);
});

test("layout changes re-render from cache without another network request", async ({
  page,
}) => {
  await mountContentScript(page, { replyMode: "hybrid" });
  await enqueueResponse(page, "translateBatch", {
    ok: true,
    texts: ["缓存译文"],
  });
  await addReply(page, '<p id="cached">Cached original</p>');
  await expect(page.locator("#cached")).toHaveText("缓存译文");
  expect(await messages(page, "translateBatch")).toHaveLength(1);

  await changeSettings(page, { replyMode: "append" });

  await expect(page.locator("#cached")).toHaveText("Cached original");
  await expect(page.locator("#cached + .zer-append")).toHaveText("缓存译文");
  expect(await messages(page, "translateBatch")).toHaveLength(1);
});

test("newly sent user bubbles use the exact captured Chinese without a request", async ({
  page,
}) => {
  await mountContentScript(page);
  await enqueueResponse(page, "translate", { ok: true, text: "Exact English" });
  await setComposer(page, "精确原文");
  await page.locator("#chat-editor").press("Enter");
  await expect(page.locator("#chat-editor")).toHaveText("Exact English");
  await page.locator("#chat-editor").press("Enter");
  expect(await sentMessages(page)).toHaveLength(1);

  await addUserBubble(page, '<p id="own-message">Exact English</p>');

  await expect(page.locator("#own-message")).toHaveText("精确原文");
  expect(await messages(page, "translateBatch")).toEqual([]);
});

test("older user bubbles fall back to translation", async ({ page }) => {
  await mountContentScript(page);
  await enqueueResponse(page, "translateBatch", {
    ok: true,
    texts: ["历史消息"],
  });

  await addUserBubble(page, '<p id="old-message">Old message</p>');

  await expect(page.locator("#old-message")).toHaveText("历史消息");
  const requests = await messages(page, "translateBatch");
  expect(requests[0].texts).toEqual(["Old message"]);
});

test("disabling reply translation while a request is in flight prevents mutation", async ({
  page,
}) => {
  await mountContentScript(page);
  await enqueueResponse(
    page,
    "translateBatch",
    { ok: true, texts: ["迟到译文"] },
    200
  );
  await addReply(page, '<p id="late">Late response</p>');
  await expect
    .poll(async () => (await messages(page, "translateBatch")).length)
    .toBe(1);

  await changeSettings(page, { translateReplies: false });
  await page.waitForTimeout(250);

  await expect(page.locator("#late")).toHaveText("Late response");
  await expect(
    page.locator(".font-claude-response")
  ).not.toHaveAttribute("data-zer-done");
});

test("keyed-engine authentication failures provide a settings hint", async ({
  page,
}) => {
  await mountContentScript(page, {
    engine: "deepl",
    deeplKey: "bad-key",
  });
  await enqueueResponse(page, "translateBatch", {
    ok: false,
    error: { code: "auth", status: 403 },
  });
  await addReply(page, "<p>Needs translation</p>");

  await expect(page.locator("#zer-out")).toContainText("请检查引擎设置");
  await expect(page.locator("#zer-out")).toContainText("Key 无效");
});
