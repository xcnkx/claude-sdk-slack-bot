#!/bin/sh
set -e

# Import gogcli tokens from environment variable
if [ -n "${GOG_TOKEN_WORK:-}" ]; then
  echo "$GOG_TOKEN_WORK" > /tmp/gog_work.json
  GOG_KEYRING_BACKEND=file GOG_KEYRING_PASSWORD="${GOG_KEYRING_PASSWORD:-claude-slack-bot}" \
    gog auth tokens import /tmp/gog_work.json 2>&1
  rm -f /tmp/gog_work.json
  echo "gogcli work account imported"
fi

if [ -n "${GOG_TOKEN_PERSONAL:-}" ]; then
  echo "$GOG_TOKEN_PERSONAL" > /tmp/gog_personal.json
  GOG_KEYRING_BACKEND=file GOG_KEYRING_PASSWORD="${GOG_KEYRING_PASSWORD:-claude-slack-bot}" \
    gog auth tokens import /tmp/gog_personal.json 2>&1
  rm -f /tmp/gog_personal.json
  echo "gogcli personal account imported"
fi

# Set gogcli to use file keyring
export GOG_KEYRING_BACKEND=file
export GOG_KEYRING_PASSWORD="${GOG_KEYRING_PASSWORD:-claude-slack-bot}"

exec uv run claude-slack-bot 2>&1
