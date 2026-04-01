FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    nodejs \
    npm \
    && rm -rf /var/lib/apt/lists/*

RUN npm install -g @anthropic-ai/claude-code

WORKDIR /app

COPY pyproject.toml uv.lock ./
COPY src/ src/
RUN uv sync --frozen --no-dev

# Required env vars at runtime:
#   SLACK_BOT_TOKEN, SLACK_APP_TOKEN
#   CLAUDE_CODE_OAUTH_TOKEN or ANTHROPIC_API_KEY
CMD ["uv", "run", "claude-slack-bot"]
