from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field

from claude_agent_sdk import ClaudeAgentOptions, ClaudeSDKClient
from claude_agent_sdk.types import AssistantMessage, ResultMessage, TextBlock

from claude_slack_bot.config import (
    ALLOWED_TOOLS,
    MAX_TURNS,
    PERMISSION_MODE,
    SESSION_TTL_SECONDS,
)

logger = logging.getLogger(__name__)


@dataclass
class _SessionEntry:
    client: ClaudeSDKClient
    last_used: float = field(default_factory=time.time)


class SessionManager:
    def __init__(self) -> None:
        self._sessions: dict[str, _SessionEntry] = {}
        self._lock = asyncio.Lock()

    def _make_options(self) -> ClaudeAgentOptions:
        return ClaudeAgentOptions(
            setting_sources=["user"],
            allowed_tools=list(ALLOWED_TOOLS),
            permission_mode=PERMISSION_MODE,
            max_turns=MAX_TURNS,
        )

    async def send_message(self, thread_ts: str, prompt: str) -> str:
        async with self._lock:
            entry = self._sessions.get(thread_ts)

        if entry is None:
            client = ClaudeSDKClient(options=self._make_options())
            await client.connect(prompt)
            entry = _SessionEntry(client=client)
            async with self._lock:
                self._sessions[thread_ts] = entry
        else:
            entry.last_used = time.time()
            await entry.client.query(prompt)

        return await self._collect_response(entry.client)

    async def _collect_response(self, client: ClaudeSDKClient) -> str:
        texts: list[str] = []
        async for message in client.receive_response():
            if isinstance(message, AssistantMessage):
                for block in message.content:
                    if isinstance(block, TextBlock):
                        texts.append(block.text)
            elif isinstance(message, ResultMessage):
                if message.is_error:
                    logger.error("Agent error: %s", message.result)
                    return f"エラーが発生しました: {message.result}"
        return "\n".join(texts) or "完了しました。"

    async def cleanup(self) -> None:
        now = time.time()
        async with self._lock:
            expired = [
                k
                for k, v in self._sessions.items()
                if now - v.last_used > SESSION_TTL_SECONDS
            ]
            for key in expired:
                logger.info("Cleaning up expired session: %s", key)
                await self._sessions[key].client.disconnect()
                del self._sessions[key]

    async def shutdown(self) -> None:
        async with self._lock:
            for key, entry in self._sessions.items():
                logger.info("Disconnecting session: %s", key)
                await entry.client.disconnect()
            self._sessions.clear()
