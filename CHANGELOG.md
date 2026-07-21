# Changelog

## v0.3.1 — 2026-07-20

- Rebranded the extension as Yifa (译发) · ZH-EN Relay, with claude.ai
  referenced only as the supported service and clear independent/unofficial
  positioning.
- Limited send interception to the actual chat composer so other editable areas
  on claude.ai are never hijacked.
- Prevented stale or duplicate translation requests from overwriting newer
  drafts, and added write-back verification before automatic sending.
- Made partial reply-translation failures visible and retryable, and completed
  enable/disable state handling.
- Migrated Gemini translation from the retired Gemini 2.0 Flash model to Gemini
  3.5 Flash and moved API-key authentication from the URL to a request header.
- Expanded the privacy policy with data retention and Chrome Web Store Limited
  Use disclosures.

## v0.3.0 — 2026-07-09

- Pre-send bilingual review: while checking the English in the box, your original Chinese shows right above it (Enter to send, Esc to undo).
- Your own sent bubbles now show Chinese underneath — the exact text you typed for new messages, a translation for older ones — rendered with the same layout modes as replies.
- Dark mode across all injected UI (review panel, reply annotations, select-to-translate popup), following claude.ai's own theme.
- Live engine check in the popup shows which engine is actually in effect; failure hints point at engine settings only when a keyed engine is active.
- Sturdier networking: retry on rate limits, capped translation cache, more tolerant Gemini response parsing.

## v0.2.0 — 2026-07-08

- Optional DeepL and Gemini engines (bring your own free API key), tucked under an "Advanced" section; Google stays the zero-setup default and is used as fallback when no key is set.
- Reply translations are cached — switching layout modes is instant and never re-hits the network.
- Reply completion detected via claude.ai's streaming flag instead of a fixed delay.
- Select-to-translate button follows the mouse-release point, clear of claude.ai's own selection tooltip.

## v0.1.0 — 2026-07-07

- First release: type Chinese, send English, replies rendered back in Chinese.
- Review-before-send with Enter/Esc; auto-send option.
- Three reply layouts: hybrid (default), full bilingual, plain-text only.
- Select-to-translate popup; Google's free endpoint, no key required.
