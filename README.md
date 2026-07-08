# Yifa (译发) · Claude ZH-EN Relay

English | [中文](README.zh-CN.md)

Chat with claude.ai in Chinese, send in English, save your usage quota.

![Type Chinese, send English, read the reply back in Chinese](assets/demo-main.gif)

## Why Yifa

On Claude, the same sentence in Chinese costs roughly 1.5–2x the tokens of its English equivalent. On a Pro or Max plan your usage limit is spent in tokens, so Chinese conversations burn through it faster and hit the cap sooner.

Yifa lets you keep typing Chinese while Claude receives English, and reads back in Chinese, so the whole conversation stays in compact English under the hood. On long chats that means noticeably more usage before you hit the limit.

## Features

Ordinary translation extensions only translate what is shown on the page; they never change what you send. Yifa works on the message itself:

- **Sends English, not Chinese.** Your input is translated to English before it leaves the box, so the model receives the compact English. A normal translator cannot do this.
- **Review before send.** The English appears in the box first — Enter to send, Esc to undo. A bad translation gets caught before the model ever sees it.
- **Replies back in Chinese, three layouts.** Hybrid (default) replaces plain text in place and leaves code untouched; full bilingual; or plain-text only.
- **Select to translate.** Highlight any text for an instant popup.
- **Never touches your traffic.** It only edits text on the page, the way a writing assistant does. No network interception, no server of its own.

Select any text for an instant translation:

![Select to translate](assets/demo-select.gif)

Switch reply layout modes on the fly:

![Reply layout modes](assets/demo-modes.gif)

## Limitations & notes

- **Your text goes to Google Translate.** Input and replies are sent to Google's translation service to be translated. Don't route anything sensitive through it. Details in [PRIVACY.md](PRIVACY.md).
- **Machine translation isn't perfect,** especially around jargon and code. The input side is guarded by the review pause; on the reply side, click through to the original or use select-to-translate.
- **It rides on claude.ai's page structure.** A major redesign may break input interception or reply detection until the selectors are updated.
- **The default engine is unofficial.** Google's free translate endpoint needs no key but can rate-limit or break. For higher quality, switch to DeepL in the popup (free key, better with technical text).
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
- **Translation engine** — Google (default, no key) or DeepL (free key, better quality).

## License

[MIT](LICENSE)
