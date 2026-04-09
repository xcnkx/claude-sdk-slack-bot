FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    curl \
    git \
    nodejs \
    npm \
    && rm -rf /var/lib/apt/lists/*

RUN npm install -g @anthropic-ai/claude-code

# Install gogcli (Google Workspace CLI)
ARG TARGETARCH
RUN ARCH=$([ "$TARGETARCH" = "arm64" ] && echo "arm64" || echo "amd64") \
    && curl -fsSL "https://github.com/steipete/gogcli/releases/latest/download/gogcli_0.12.0_linux_${ARCH}.tar.gz" \
    | tar -xz -C /usr/local/bin gog

# Run as non-root (required by Claude Code CLI with bypassPermissions)
RUN useradd -m bot && mkdir -p /app && chown bot:bot /app \
    && mkdir -p /home/bot/.claude && chown bot:bot /home/bot/.claude

# Pull dotfiles and install Claude Code config & skills
# Requires GITHUB_TOKEN secret (passed via docker compose secrets)
RUN --mount=type=secret,id=github_token \
    GITHUB_TOKEN=$(cat /run/secrets/github_token) \
    && git clone --depth 1 https://${GITHUB_TOKEN}:x-oauth-basic@github.com/xcnkx/dotfiles.git /tmp/dotfiles \
    && cp -R /tmp/dotfiles/claude/skills /home/bot/.claude/skills \
    && cp -R /tmp/dotfiles/claude/commands /home/bot/.claude/commands \
    && cp /tmp/dotfiles/claude/settings.json /home/bot/.claude/settings.json \
    && cp /tmp/dotfiles/claude/CLAUDE.md /home/bot/.claude/CLAUDE.md \
    && chown -R bot:bot /home/bot/.claude \
    && rm -rf /tmp/dotfiles

WORKDIR /app

COPY --chown=bot:bot pyproject.toml uv.lock README.md ./
COPY --chown=bot:bot src/ src/
COPY --chown=bot:bot entrypoint.sh ./

USER bot
RUN uv sync --frozen --no-dev

# Required env vars at runtime:
#   SLACK_BOT_TOKEN, SLACK_APP_TOKEN
#   CLAUDE_CODE_OAUTH_TOKEN or ANTHROPIC_API_KEY
# Optional for gogcli:
#   GOG_TOKEN_WORK, GOG_TOKEN_PERSONAL
CMD ["./entrypoint.sh"]
