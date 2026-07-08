# Privacy Policy / 隐私政策

**Yifa (译发) · Claude ZH-EN Relay**

Last updated: 2026-07-07

## English

- **What data is processed.** Text you type into the claude.ai input box and text from claude.ai replies is sent to a translation service solely to perform translation. By default this is Google's endpoint (`translate.googleapis.com`). If you choose DeepL or Gemini and enter a key, it goes to that provider instead (`api-free.deepl.com` / `api.deepl.com`, or `generativelanguage.googleapis.com`). Selected text is sent the same way when you use select-to-translate.
- **What is stored.** Extension settings (toggles, layout mode, chosen engine) and any API key you enter (DeepL or Gemini) are stored locally via `chrome.storage.local`. A key is sent only to its own provider, through the extension's background worker, never to the page or anywhere else. Nothing else is stored.
- **What is NOT done.** The extension does not modify, intercept, or log any claude.ai network requests; does not send any data to servers operated by the author; does not use analytics, tracking, or ads; does not read pages other than claude.ai.
- **Third parties.** Translation text passes through Google's service and is subject to Google's own terms and privacy practices. Do not route sensitive content through this extension if that is a concern.

## 中文

- **处理哪些数据。** 在 claude.ai 输入框中输入的文本、以及 claude.ai 回复中的文本，会被发送到翻译服务，仅用于完成翻译。默认使用 Google 端点（`translate.googleapis.com`）；若你选择 DeepL 或 Gemini 并填写 key，则改为发送到对应服务商（`api-free.deepl.com` / `api.deepl.com`，或 `generativelanguage.googleapis.com`）。使用划词翻译时，选中的文本同样如此。
- **存储哪些数据。** 扩展设置（开关、排版模式、所选引擎）以及你填写的 API key（DeepL 或 Gemini）通过 `chrome.storage.local` 保存在本地浏览器中。key 仅经扩展后台发送给其对应的服务商，不会给页面或其他任何地方。除此之外不存储任何内容。
- **不做什么。** 不修改、拦截或记录 claude.ai 的任何网络请求；不向作者运营的任何服务器发送数据；无统计、无跟踪、无广告；除 claude.ai 外不读取任何页面。
- **第三方。** 翻译文本会经过 Google 的服务，适用 Google 自身的条款与隐私实践。介意的敏感内容请勿经由本扩展发送。
