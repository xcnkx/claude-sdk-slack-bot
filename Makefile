.PHONY: run dev lint fmt fix check test docker-run

# Extract OAuth token from macOS Keychain
_OAUTH_TOKEN = $(shell security find-generic-password -s "Claude Code-credentials" -w 2>/dev/null | jq -r '.claudeAiOauth.accessToken // empty' 2>/dev/null)

run:
	@export CLAUDE_CODE_OAUTH_TOKEN=$(_OAUTH_TOKEN) && uv run claude-slack-bot

dev:
	@export CLAUDE_CODE_OAUTH_TOKEN=$(_OAUTH_TOKEN) && uv run python -m claude_slack_bot.main

docker-build:
	docker compose build --no-cache

docker-run:
	@docker compose run --rm \
		-e CLAUDE_CODE_OAUTH_TOKEN=$(_OAUTH_TOKEN) \
		-e LOG_LEVEL=$(or $(LOG_LEVEL),INFO) \
		-e PYTHONUNBUFFERED=1 \
		bot

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
