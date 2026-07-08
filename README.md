# Yifa (译发) · Claude ZH-EN Relay

English | [中文](README.zh-CN.md)

Chat with claude.ai in Chinese, send in English, save your usage quota.

![Type Chinese, send English, read the reply back in Chinese](assets/demo-main.gif)

## Why

On Claude, the same sentence in Chinese costs roughly 1.5–2x the tokens of its English equivalent. On a Pro or Max plan your usage limit is spent in tokens, so Chinese conversations burn through it faster and hit the cap sooner.

Yifa lets you keep typing Chinese while Claude receives English, and reads back in Chinese, so the whole conversation stays in compact English under the hood. On long chats that means noticeably more usage before you hit the limit.

## What makes it different

Ordinary translation extensions only translate what is shown on the page. They never change what you send. Yifa works on the message itself:

- **Sends English, not Chinese.** Your input is translated to English before it leaves the box, so the model receives the compact English. This is the part a normal translator cannot do.
- **Review before send.** The English appears in the box first. Press Enter to send, Esc to undo. A bad translation gets caught before the model ever sees it.
- **Replies back in Chinese, three layouts.** Hybrid (default) replaces plain text in place and leaves code blocks and inline code untouched; full bilingual; or plain-text only.
- **Select to translate.** Highlight any text for an instant popup, direction auto-detected.
- **Never touches your traffic.** It only edits text on the page, the way a writing assistant does. No network interception, no server of its own.

Select any text for an instant translation:

![Select to translate](assets/demo-select.gif)

Switch reply layout modes on the fly:

![Reply layout modes](assets/demo-modes.gif)

## Install

1. Download the zip from [Releases](https://github.com/ZhiqiaoGong/Claude-ZH-EN-Relay/releases) and unzip it, or clone this repo.
2. Open `chrome://extensions` and enable Developer mode.
3. Click "Load unpacked" and pick the project folder.
4. Open or refresh claude.ai.

Works on Chromium-based browsers (Chrome, Edge, etc.).

## Recommended one-time setup

The extension translates your input, but it cannot decide which language the model replies in. To maximize quota savings, make the replies English too:

Create a claude.ai Project with the custom instruction `Always reply in English`, and chat inside that Project. Replies come back in English, the extension renders them in Chinese, and the whole context stays compact. The longer the conversation, the more it saves.

## Settings (toolbar popup)

- **Enable** — master switch.
- **Auto-send after translation** — off: pause for review, Enter to send, Esc to undo; on: send immediately once translated.
- **Translate replies to Chinese** — toggle the reply side.
- **Reply layout**:
  - **Hybrid (recommended)** — plain-text paragraphs are replaced in place (click to see the original); paragraphs containing code or links get the translation appended below, keeping the original intact.
  - **Full bilingual** — originals untouched, Chinese appended under every paragraph.
  - **Plain text only** — only plain-text paragraphs are replaced; paragraphs with code or links stay English.

## Translation engine

Currently Google's unofficial translate endpoint: no API key, works out of the box, but it may rate-limit or break occasionally. A keyed DeepL backend is planned as a higher-quality option.

## Privacy

- Input and reply text is sent to Google's translation service for translation. Don't route anything sensitive through it.
- The extension does not modify any claude.ai network requests and uploads nothing to any server of its own.
- Settings are stored locally in the browser.

See [PRIVACY.md](PRIVACY.md).

## Limitations

- Depends on claude.ai's page structure; a redesign may break input interception or reply detection until selectors are updated.
- Machine translation is imperfect, especially around jargon and code. The input side is guarded by the review-before-send pause; on the reply side, click through to the original or use select-to-translate.

## Disclaimer

A personal open-source tool, unaffiliated with Anthropic or Google. It only modifies how pages are displayed locally, the same category of behavior as common writing-assistant and translation extensions. Use at your own risk.

## License

[MIT](LICENSE)
