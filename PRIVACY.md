# Privacy Policy / 隐私政策

**Yifa (译发) · ZH-EN Relay**

Last updated: 2026-07-21

## English

- **What data is processed.** Text you type into the claude.ai input box and text from claude.ai replies is sent to a translation service solely to perform translation. By default this is Google's endpoint (`translate.googleapis.com`). If you choose DeepL or Gemini and enter a key, it goes to that provider instead (`api-free.deepl.com` / `api.deepl.com`, or `generativelanguage.googleapis.com`). Selected text is sent the same way when you use select-to-translate.
- **What is stored.** Extension settings (toggles, layout mode, chosen engine) and any API key you enter (DeepL or Gemini) are stored locally via `chrome.storage.local` until you remove them or uninstall the extension. A key is sent only to its own provider, through the extension's background worker, never to the page or anywhere else. Reply translations may be held temporarily in page memory to avoid repeated requests and disappear when the page is closed or refreshed. Conversation text is not persistently stored by the extension.
- **Limited use.** User data is used only to provide the extension's visible translation features. It is not sold, used for advertising, creditworthiness, analytics, tracking, or any unrelated purpose. Data is transferred only to the translation provider selected by the user (or to Google when the configured keyed provider has no key), as necessary to perform translation. The developer does not operate a receiving server and does not permit humans to read user data.
- **What is NOT done.** The extension does not modify, intercept, or log any claude.ai network requests; does not send any data to servers operated by the author; does not use analytics, tracking, or ads; does not read pages other than claude.ai.
- **Third parties.** Translation text passes through the selected provider—Google Translate, DeepL, or Gemini—and is subject to that provider's terms and privacy practices. Do not route sensitive content through this extension if that is a concern.
- **Chrome Web Store Limited Use.** The extension's use of information complies with the Chrome Web Store User Data Policy, including the Limited Use requirements.

## 中文

- **处理哪些数据。** 在 claude.ai 输入框中输入的文本、以及 claude.ai 回复中的文本，会被发送到翻译服务，仅用于完成翻译。默认使用 Google 端点（`translate.googleapis.com`）；若你选择 DeepL 或 Gemini 并填写 key，则改为发送到对应服务商（`api-free.deepl.com` / `api.deepl.com`，或 `generativelanguage.googleapis.com`）。使用划词翻译时，选中的文本同样如此。
- **存储哪些数据。** 扩展设置（开关、排版模式、所选引擎）以及你填写的 API key（DeepL 或 Gemini）通过 `chrome.storage.local` 保存在本地浏览器中，直至你删除它们或卸载扩展。key 仅经扩展后台发送给其对应服务商，不会提供给网页或其他服务。回复译文可能暂存在当前页面内存中以避免重复请求，关闭或刷新页面后即消失；扩展不会持久保存对话文本。
- **有限使用。** 用户数据仅用于提供扩展界面中可见的翻译功能，不会被出售，也不会用于广告、信用评估、分析、跟踪或其他无关目的。数据只会在完成翻译所必需的范围内传给用户选择的翻译服务商；若所选付费引擎未填写 key，则按界面说明回退到 Google。开发者不运营接收数据的服务器，也不允许任何人读取用户数据。
- **不做什么。** 不修改、拦截或记录 claude.ai 的任何网络请求；不向作者运营的任何服务器发送数据；无统计、无跟踪、无广告；除 claude.ai 外不读取任何页面。
- **第三方。** 翻译文本会经过所选服务商（Google Translate、DeepL 或 Gemini），并适用该服务商自身的条款与隐私实践。介意的敏感内容请勿经由本扩展发送。
- **Chrome Web Store 有限使用。** 扩展对信息的使用遵守 Chrome Web Store 用户数据政策，包括其中的 Limited Use 要求。
