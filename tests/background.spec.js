const { test, expect } = require("@playwright/test");
const {
  enqueueFetch,
  fetches,
  invokeBackground,
  mountBackground,
} = require("./helpers/extension-harness");

test("Google translation joins all returned segments", async ({ page }) => {
  await mountBackground(page, { engine: "google" });
  await enqueueFetch(page, {
    status: 200,
    json: [[["Hello ", "你好"], ["world", "世界"]]],
  });

  const result = await invokeBackground(page, {
    type: "translate",
    text: "你好世界",
    from: "zh-CN",
    to: "en",
  });

  expect(result).toEqual({ ok: true, text: "Hello world" });
  const calls = await fetches(page);
  expect(calls[0].url).toContain("translate.googleapis.com");
  expect(calls[0].url).toContain("q=%E4%BD%A0%E5%A5%BD%E4%B8%96%E7%95%8C");
});

test("Google batch preserves order and isolates one failed item", async ({
  page,
}) => {
  await mountBackground(page, { engine: "google" });
  await enqueueFetch(page, {
    status: 200,
    json: [[["One", "一"]]],
  });
  await enqueueFetch(page, { status: 503, json: {} });
  await enqueueFetch(page, { status: 503, json: {} });
  await enqueueFetch(page, {
    status: 200,
    json: [[["Three", "三"]]],
  });

  const result = await invokeBackground(page, {
    type: "translateBatch",
    texts: ["一", "二", "三"],
    from: "zh-CN",
    to: "en",
  });

  expect(result).toEqual({ ok: true, texts: ["One", null, "Three"] });
});

test("rate-limited Google calls retry once before succeeding", async ({ page }) => {
  await mountBackground(page, { engine: "google" });
  await enqueueFetch(page, { status: 429, json: {} });
  await enqueueFetch(page, {
    status: 200,
    json: [[["Recovered", "恢复"]]],
  });

  const result = await invokeBackground(page, {
    type: "translate",
    text: "恢复",
    from: "zh-CN",
    to: "en",
  });

  expect(result).toEqual({ ok: true, text: "Recovered" });
  expect(await fetches(page)).toHaveLength(2);
});

test("DeepL free keys select the free host and batch in one POST", async ({
  page,
}) => {
  await mountBackground(page, {
    engine: "deepl",
    deeplKey: "secret:fx",
  });
  await enqueueFetch(page, {
    status: 200,
    json: { translations: [{ text: "A" }, { text: "B" }] },
  });

  const result = await invokeBackground(page, {
    type: "translateBatch",
    texts: ["甲", "乙"],
    from: "zh-CN",
    to: "en",
  });

  expect(result).toEqual({ ok: true, texts: ["A", "B"] });
  const calls = await fetches(page);
  expect(calls).toHaveLength(1);
  expect(calls[0].url).toBe("https://api-free.deepl.com/v2/translate");
  expect(calls[0].method).toBe("POST");
  expect(calls[0].body).toContain("text=%E7%94%B2");
  expect(calls[0].body).toContain("text=%E4%B9%99");
});

test("Gemini accepts fenced JSON and requests minimal thinking", async ({
  page,
}) => {
  await mountBackground(page, {
    engine: "gemini",
    geminiKey: "gemini-key",
  });
  await enqueueFetch(page, {
    status: 200,
    json: {
      candidates: [
        {
          content: {
            parts: [{ text: '```json\\n["First","Second"]\\n```' }],
          },
        },
      ],
    },
  });

  const result = await invokeBackground(page, {
    type: "translateBatch",
    texts: ["第一", "第二"],
    from: "zh-CN",
    to: "en",
  });

  expect(result).toEqual({ ok: true, texts: ["First", "Second"] });
  const calls = await fetches(page);
  const body = JSON.parse(calls[0].body);
  expect(calls[0].url).toContain("gemini-3.1-flash-lite:generateContent");
  expect(body.generationConfig.responseMimeType).toBe("application/json");
  expect(body.generationConfig.thinkingConfig.thinkingLevel).toBe("minimal");
});

test("DeepL authentication errors are normalized for the UI", async ({ page }) => {
  await mountBackground(page, {
    engine: "deepl",
    deeplKey: "bad-key",
  });
  await enqueueFetch(page, { status: 403, json: {} });

  const result = await invokeBackground(page, {
    type: "translate",
    text: "hello",
    from: "en",
    to: "zh-CN",
  });

  expect(result).toEqual({
    ok: false,
    error: { code: "auth", status: 403 },
  });
});

test("malformed Gemini output is classified as an invalid response", async ({
  page,
}) => {
  await mountBackground(page, {
    engine: "gemini",
    geminiKey: "key",
  });
  await enqueueFetch(page, {
    status: 200,
    json: {
      candidates: [{ content: { parts: [{ text: "not json" }] } }],
    },
  });

  const result = await invokeBackground(page, {
    type: "translateBatch",
    texts: ["one", "two"],
    from: "en",
    to: "zh-CN",
  });

  expect(result).toEqual({
    ok: false,
    error: { code: "invalid_response", status: null },
  });
});
