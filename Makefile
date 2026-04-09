.PHONY: run dev lint fmt fix check test docker-run

# Extract OAuth token from macOS Keychain
_OAUTH_TOKEN = $(shell security find-generic-password -s "Claude Code-credentials" -w 2>/dev/null | jq -r '.claudeAiOauth.accessToken // empty' 2>/dev/null)

# Export gogcli tokens (to temp files, read as env vars)
_GOG_TOKEN_WORK = $(shell gog auth tokens export ca01222@cartahd.com --out /tmp/.gog_work.json >/dev/null 2>&1 && cat /tmp/.gog_work.json && rm -f /tmp/.gog_work.json)
_GOG_TOKEN_PERSONAL = $(shell gog auth tokens export x2cnk8x@gmail.com --out /tmp/.gog_personal.json >/dev/null 2>&1 && cat /tmp/.gog_personal.json && rm -f /tmp/.gog_personal.json)

# GCP OAuth client credentials for gogcli
_GOG_CREDENTIALS = $(shell cat ~/.googlecloud/client_secret_*.json 2>/dev/null)

run:
	@export CLAUDE_CODE_OAUTH_TOKEN=$(_OAUTH_TOKEN) && uv run claude-slack-bot

dev:
	@export CLAUDE_CODE_OAUTH_TOKEN=$(_OAUTH_TOKEN) && uv run python -m claude_slack_bot.main

docker-build:
	GITHUB_TOKEN=$(shell gh auth token -u xcnkx) docker compose build

docker-run: docker-build
	@docker compose run --rm -d \
		-e CLAUDE_CODE_OAUTH_TOKEN=$(_OAUTH_TOKEN) \
		-e GOG_TOKEN_WORK='$(_GOG_TOKEN_WORK)' \
		-e GOG_TOKEN_PERSONAL='$(_GOG_TOKEN_PERSONAL)' \
		-e GOG_CREDENTIALS='$(_GOG_CREDENTIALS)' \
		-e LOG_LEVEL=$(or $(LOG_LEVEL),INFO) \
		-e PYTHONUNBUFFERED=1 \
		bot

docker-stop:
	@docker ps --filter "name=claude-slack-bot" --format "{{.ID}}" | xargs -r docker stop 2>/dev/null || true
	@docker compose down --remove-orphans 2>/dev/null || true

docker-logs:
	docker compose logs -f bot

lint:
	uv run ruff check src/

fmt:
	uv run ruff format src/

fix:
	uv run ruff check --fix src/

check: lint
	uv run ruff format --check src/

test:
	uv run pytest
