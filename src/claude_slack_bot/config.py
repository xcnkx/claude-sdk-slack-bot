from __future__ import annotations

import os


def _list_from_env(key: str, default: str) -> list[str]:
    return [s.strip() for s in os.getenv(key, default).split(",") if s.strip()]


SLACK_BOT_TOKEN: str = os.environ["SLACK_BOT_TOKEN"]
SLACK_APP_TOKEN: str = os.environ["SLACK_APP_TOKEN"]

ALLOWED_TOOLS: list[str] = _list_from_env(
    "ALLOWED_TOOLS",
    "Skill,Read,Bash,Glob,Grep,WebSearch,WebFetch",
)

PERMISSION_MODE: str = os.getenv("PERMISSION_MODE", "bypassPermissions")
SESSION_TTL_SECONDS: int = int(os.getenv("SESSION_TTL_SECONDS", "1800"))
MAX_TURNS: int = int(os.getenv("MAX_TURNS", "30"))
