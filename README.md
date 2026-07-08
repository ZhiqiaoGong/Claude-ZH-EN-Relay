# Yifa (译发) · Claude ZH-EN Relay

English | [中文](README.zh-CN.md)

A Chrome extension for claude.ai: chat in Chinese, send in English, save your usage quota.

Chinese text typically costs 1.5–2x more tokens than the equivalent English. This extension translates your Chinese input to English right before it is sent, and translates English replies back to Chinese for reading — so the entire conversation context stays in compact English, stretching a Pro/Max usage limit noticeably on long conversations.

Every translation is visible and reversible. The extension never touches network traffic; it only edits text on the page, the same way writing assistants and translation extensions do.

![Type Chinese, send English, read the reply back in Chinese](assets/demo-main.gif)

## How it works

- **Input side**: type Chinese in the normal input box and press Enter. The text is translated to English in place, and by default the send pauses so the English can be reviewed — this doubles as the safeguard against silent mistranslation. Confirm with Enter, or press Esc to restore the Chinese.
- **Reply side**: once a reply finishes rendering, its English is translated back to Chinese. Three layout modes (see below).
- **Select to translate**: select any text in a reply for an instant popup translation, direction auto-detected. Useful for double-checking technical passages.

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

Create a claude.ai Project with the custom instruction `Always reply in English`, and chat inside that Project. Replies come back in English, the extension renders them in Chinese, and the whole context stays compact — the longer the conversation, the more it saves.

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
