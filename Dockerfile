FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    nodejs \
    npm \
    && rm -rf /var/lib/apt/lists/*

RUN npm install -g @anthropic-ai/claude-code

WORKDIR /app

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

COPY src/ src/

# Required env vars at runtime:
#   SLACK_BOT_TOKEN, SLACK_APP_TOKEN, ANTHROPIC_API_KEY
CMD ["uv", "run", "claude-slack-bot"]
