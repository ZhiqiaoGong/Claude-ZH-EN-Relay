#!/usr/bin/env bash
# Build a clean install zip containing only the files the extension needs at
# runtime (no docs, no demo GIFs). Output: yifa-zh-en-relay-v<version>.zip
set -euo pipefail
cd "$(dirname "$0")"

ver=$(sed -n 's/.*"version": *"\([^"]*\)".*/\1/p' manifest.json | head -1)
out="yifa-zh-en-relay-v${ver}.zip"

rm -f "$out"
zip -rq "$out" \
  manifest.json \
  background.js \
  content.js \
  overlay.css \
  popup.html \
  popup.js \
  icons \
  LICENSE \
  -x '*.DS_Store' '*.svg'

echo "built $out"
