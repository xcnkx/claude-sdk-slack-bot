.PHONY: run dev lint fmt fix check

run:
	uv run claude-slack-bot

dev:
	uv run python -m claude_slack_bot.main

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
