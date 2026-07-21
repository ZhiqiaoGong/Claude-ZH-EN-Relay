#!/usr/bin/env bash
# One-step release: read the version from manifest.json, tag it, push the tag,
# and build the install zip. The final step (uploading the zip to a GitHub
# Release) is still done in the web UI, since gh is not required here.
set -euo pipefail
cd "$(dirname "$0")"

ver=$(sed -n 's/.*"version": *"\([^"]*\)".*/\1/p' manifest.json | head -1)
tag="v${ver}"

if [ -z "$ver" ]; then
  echo "could not read version from manifest.json" >&2
  exit 1
fi

# Refuse to tag a dirty tree — the tag should point at committed code.
if [ -n "$(git status --porcelain)" ]; then
  echo "working tree has uncommitted changes; commit them first" >&2
  exit 1
fi

# Don't clobber an existing tag (bump the version in manifest.json first).
if git rev-parse "$tag" >/dev/null 2>&1; then
  echo "tag $tag already exists — bump \"version\" in manifest.json first" >&2
  exit 1
fi

# Build and validate before creating a remote tag, so a packaging failure leaves
# the release safe to retry.
./package.sh
zip="yifa-zh-en-relay-${tag}.zip"
unzip -t "$zip" >/dev/null

git tag -a "$tag" -m "$tag"
git push origin "$tag"

echo
echo "tagged and pushed $tag, built $zip"
echo "next: open the repo's Releases page, draft a release from tag $tag,"
echo "      and attach $zip"
