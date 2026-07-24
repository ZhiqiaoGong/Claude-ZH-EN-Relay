# Yifa (译发) · ZH-EN Relay

English | [中文](README.zh-CN.md)

An independent, unofficial extension for chatting on claude.ai in Chinese,
sending in English, and reading replies back in Chinese.

![Type Chinese, send English, read the reply back in Chinese](assets/demo-main.gif)

## Why Yifa

Yifa is a message-level bilingual relay, not a generic page translator. It
lets you write in Chinese, review the English text Claude will actually
receive, and read English replies back in Chinese while keeping the original
available.

Token efficiency depends on the Claude model and translation direction. In our
reproducible 3,481-sentence original-Chinese benchmark, Yifa's Google English
translations used **18.9% fewer input tokens on Claude Sonnet 4.6**, but
**18.6% more on Claude Sonnet 5**. Yifa therefore makes no blanket token-saving
claim. See the [large-sample benchmark, raw translations, and verification
scripts](benchmark/README.md).

## Features

Ordinary translation extensions only translate what is shown on the page; they never change what you send. Yifa works on the message itself:

- **Sends English, not Chinese.** Your input is translated to English before it leaves the box, so the model receives the reviewed English text. A normal page translator cannot do this.
- **Review before send.** The English lands in the box with your original Chinese shown right above it, so you can compare the two before it goes out. Enter to send, Esc to undo — a bad translation gets caught before the model ever sees it.
- **Replies back in Chinese, three layouts.** Hybrid (default) replaces plain text in place and leaves code untouched; full bilingual; or plain-text only.
- **Your own messages too.** Your sent bubble shows the English that went out, with the Chinese underneath, so scrolling back through the conversation stays readable.
- **Select to translate.** Highlight any text for an instant popup.
- **Light and dark.** Everything adapts to claude.ai's theme.
- **Never touches your traffic.** It only edits text on the page, the way a writing assistant does. No network interception, no server of its own.

Select any text for an instant translation:

![Select to translate](assets/demo-select.gif)

Switch reply layout modes on the fly:

![Reply layout modes](assets/demo-modes.gif)

## Limitations & notes

- **Your text goes to Google Translate.** Input and replies are sent to Google's translation service to be translated. Don't route anything sensitive through it. Details in [PRIVACY.md](PRIVACY.md).
- **Machine translation isn't perfect,** especially around jargon and code. The input side is guarded by the review pause; on the reply side, click through to the original or use select-to-translate.
- **It rides on claude.ai's page structure.** A major redesign may break input interception or reply detection until the selectors are updated.
- **The default engine is unofficial.** Google's free translate endpoint needs no key but can rate-limit or break. For higher quality, add a DeepL or Gemini key (see [Translation engines](#translation-engines)).
- **Unaffiliated personal tool.** Not affiliated with Anthropic or Google. Use at your own risk.

## Install

1. Download the zip from [Releases](https://github.com/ZhiqiaoGong/Claude-ZH-EN-Relay/releases) and unzip it, or clone this repo.
2. Open `chrome://extensions` and enable Developer mode.
3. Click "Load unpacked" and pick the project folder.
4. Open or refresh claude.ai.

Works on Chromium-based browsers (Chrome, Edge, etc.).

## Recommended one-time setup

Create a claude.ai Project with the custom instruction `Always reply in English` and chat inside it, so replies come back in English too.

## Settings (toolbar popup)

- **Enable** — master switch.
- **Auto-send after translation** — off: pause for review; on: send immediately.
- **Translate replies to Chinese** — toggle the reply side.
- **Reply layout** — Hybrid (recommended) / Full bilingual / Plain text only.
- **Translation engine** (under "Advanced") — see below.

## Translation engines

Google is the default and needs no setup. Two optional engines give higher quality if you add a free API key — pick them in the popup under **Advanced**. Every key is stored locally in your browser and sent only to that provider.

<img src="assets/popup-v0.3.2.jpg" alt="Extension popup with Gemini Flash-Lite active" width="320">

| Engine | Setup | Best for |
| --- | --- | --- |
| **Google** | None (default) | Everyday use. Free, works out of the box; unofficial, may occasionally rate-limit. |
| **DeepL** | Free API key | Higher-quality machine translation, especially technical text. |
| **Gemini** | Free API key | Low-latency Flash-Lite translation with context and tone awareness. |

Without a key, DeepL and Gemini both fall back to Google, so nothing breaks.

## Reliability tests

The repository includes **33 Playwright browser regression scenarios** covering
send interception, review/undo, stale-translation races, guarded auto-send,
streaming replies, all three layouts, code/link preservation, partial-failure
retry, cache re-rendering, and Google/DeepL/Gemini routing.

The suite runs against a deterministic claude.ai DOM fixture with mocked
translation responses. It does not send test text to any translation provider.

```bash
npm ci
npx playwright install chromium
npm test
```

The same suite runs on every push and pull request through GitHub Actions.

## License

[MIT](LICENSE)
