# Chrome Web Store Submission Notes

Use this for publishing the `v0.3.1` release.

## Package

- Upload zip: `/Users/zhiqiaogong/Projects/PythonProject/testcc/yifa-zh-en-relay-v0.3.1.zip`
- SHA-256: `c01c18bca58c06da16a2c5f22aa3b5e7715e39ba45c3f622694711ec830c81e7`
- Verification: upload only after the package contents match the `v0.3.1` tag.

## Store Listing

- Category: Productivity
- Language: Chinese (Simplified)
- Store title: `译发 · ZH-EN Relay`
- Short description: `在 claude.ai 用中文输入、英文发送，并将回复译回中文的非官方第三方扩展。`
- Homepage URL: `https://github.com/ZhiqiaoGong/Claude-ZH-EN-Relay`
- Support URL: `https://github.com/ZhiqiaoGong/Claude-ZH-EN-Relay/issues`
- Privacy policy URL: `https://github.com/ZhiqiaoGong/Claude-ZH-EN-Relay/blob/v0.3.1/PRIVACY.md`
- Store icon: `/Users/zhiqiaogong/Projects/PythonProject/testcc/icons/icon128.png`
- Small promo tile: `/Users/zhiqiaogong/Projects/PythonProject/testcc/assets/small-promo-tile-440x280.png`
- Top promo tile: `/Users/zhiqiaogong/Projects/PythonProject/testcc/assets/top-promo-tile-1400x560.png`

### Screenshots

Recommended upload order:

- `/Users/zhiqiaogong/Projects/PythonProject/testcc/chrome-store/assets/cws-screenshot-main.png`
- `/Users/zhiqiaogong/Projects/PythonProject/testcc/chrome-store/assets/cws-screenshot-select.png`
- `/Users/zhiqiaogong/Projects/PythonProject/testcc/chrome-store/assets/cws-screenshot-modes.png`
- `/Users/zhiqiaogong/Projects/PythonProject/testcc/chrome-store/assets/cws-screenshot-popup.png`

### Detailed Description

```text
译发是一款由独立开发者制作、适用于 claude.ai 的非官方第三方扩展，与 Anthropic 无关联，也未获得其赞助、认可或授权。它让中文用户可以继续用中文思考和输入，同时把发送给 Claude 的内容转换为更省 token 的英文。

它只在 claude.ai 生效。你输入中文后，扩展会先把内容翻译成英文并写回输入框，默认暂停等待你核对：回车发送，Esc 撤回。Claude 回复完成后，扩展可以把英文回复自动译回中文，并提供混合、完整对照、纯文字三种排版模式。

主要功能：

- 中文输入，发送前自动译为英文
- 默认先核对译文，避免静默误发
- Claude 回复自动译回中文
- 支持混合、完整对照、纯文字三种回复排版
- 划词即时翻译
- 默认使用 Google 翻译端点，无需 API key
- 可选 DeepL 或 Gemini，需要用户自行填写 API key
- API key 仅保存在浏览器本地
- 不拦截、不修改、不记录 claude.ai 的网络请求
- 无广告、无统计、无作者服务器

隐私说明：

为了完成翻译，扩展会把你输入的文本、Claude 回复文本或你选中的文本发送给所选翻译服务。默认是 Google Translate；如果你选择 DeepL 或 Gemini 并填写 API key，则发送给对应服务。扩展不会把数据发送给作者运营的服务器，也不会做分析、跟踪或广告。请不要通过本扩展处理敏感内容。

Claude is a trademark of Anthropic PBC. Google, DeepL, and Gemini are trademarks of their respective owners. Use of these names identifies compatibility or translation providers and does not imply affiliation or endorsement.
```

## Privacy Tab

### Single Purpose

```text
Help Chinese-speaking users chat on claude.ai by translating outgoing Chinese messages to English before sending, translating Claude replies back to Chinese, and providing selected-text translation on claude.ai.
```

### Permission Justifications

`storage`

```text
Stores extension settings locally, including enable/disable state, auto-send setting, reply layout mode, selected translation engine, and optional DeepL/Gemini API keys. API keys are stored only in chrome.storage.local.
```

`https://claude.ai/*`

```text
Runs the content script only on claude.ai so the extension can read the chat input, replace the input with the translated English text before sending, translate visible Claude reply text, and support selected-text translation.
```

`https://translate.googleapis.com/*`

```text
Sends user-requested text to Google Translate to perform translation when the default Google engine is selected or when optional keyed engines are not configured.
```

`https://api-free.deepl.com/*` and `https://api.deepl.com/*`

```text
Sends user-requested text to DeepL only when the user selects DeepL and provides a DeepL API key. The API key is sent only to DeepL for authentication.
```

`https://generativelanguage.googleapis.com/*`

```text
Sends user-requested text to Gemini only when the user selects Gemini and provides a Gemini API key. The API key is sent only to Google's Gemini API for authentication.
```

### Remote Code

Select: `No, I am not using remote code.`

Suggested explanation if a text box appears:

```text
The extension does not load or execute remotely hosted JavaScript. It calls remote translation APIs only to receive translated text.
```

### Data Usage

Conservative recommended data types to disclose:

- Personal communications: the extension processes text the user types into the claude.ai chat input and selected text the user explicitly asks to translate.
- Website content: the extension reads visible claude.ai reply text so it can translate replies back to Chinese.
- Authentication information: optional DeepL/Gemini API keys are stored locally and sent only to the selected provider for translation requests.

Recommended certification wording, if requested:

```text
User text is used only to provide the extension's visible translation features. It is transferred only to the selected translation provider as necessary to perform translation. The extension does not sell, analyze, or use user data for advertising, tracking, creditworthiness, or unrelated purposes; does not permit humans to read user data; and does not send user data to servers operated by the developer. The extension's use of information complies with the Chrome Web Store User Data Policy, including the Limited Use requirements.
```

## Distribution

- Visibility: Public, unless you want a quiet first review. Unlisted still goes through the same policy review.
- Regions: All regions is reasonable for this extension.
- Pricing: Free.

## Test Instructions

```text
No credentials are required for the extension itself. Full testing requires access to any claude.ai account.

1. Install the extension and open https://claude.ai/.
2. Open a new or existing chat.
3. Type a Chinese message, for example: "请用一句话解释二分查找", then press Enter.
4. The extension translates the message to English in the input box and shows a review bar. Press Enter again to send, or press Esc to restore the original Chinese text.
5. After Claude finishes replying in English, the extension translates reply paragraphs back to Chinese.
6. Highlight any text on the page and click the small "译" pill to test selected-text translation.
7. The default Google translation engine requires no API key. DeepL and Gemini are optional settings and can be skipped during review.

The extension does not intercept claude.ai network requests. It only edits visible page text and calls translation APIs from the background service worker.
```

## Pre-Submit Checks

- Confirm the uploaded package name is exactly `yifa-zh-en-relay-v0.3.1.zip`.
- Confirm the dashboard package version shows `0.3.1`.
- Confirm remote code is declared as not used.
- Confirm the privacy disclosure mentions third-party translation providers.
- Confirm the privacy policy URL is publicly accessible.
- Use deferred publishing if you want to inspect the approved listing before it goes live.
