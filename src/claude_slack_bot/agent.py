from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field

from claude_agent_sdk import ClaudeAgentOptions, ClaudeSDKClient
from claude_agent_sdk.types import AssistantMessage, ResultMessage, TextBlock

from claude_slack_bot.config import (
    ALLOWED_TOOLS,
    CHANNEL_MEMORY_ALL,
    CHANNEL_MEMORY_ENABLED,
    MAX_TURNS,
    MEMORY_DIR,
    PERMISSION_MODE,
    SESSION_TTL_SECONDS,
)
from claude_slack_bot.memory import MemoryStore

logger = logging.getLogger(__name__)

memory_store = MemoryStore(MEMORY_DIR)

SYSTEM_PROMPT_BASE = """\
あなたはSlack上で動作するパーソナルアシスタントです。回答はSlackのmrkdwn記法で整形してください。

## Slack mrkdwn記法ルール
- 太字: *テキスト*
- 斜体: _テキスト_
- 取り消し線: ~テキスト~
- コード: `コード`
- コードブロック: ```コードブロック```
- 引用: > テキスト
- リスト: - 項目 または 1. 項目
- リンク: <URL|表示テキスト>

## 注意
- Markdownの **太字** や ### 見出し は使わない（Slackでは表示されない）
- 回答は簡潔にまとめる
- 長文は箇条書きやコードブロックで見やすく整形する
- 日本語で回答する
"""

MEMORY_UPDATE_INSTRUCTIONS = """\

## 記憶の更新ルール
- ワークスペース全体で使える永続的な事実（会社情報、人物情報、設定など）を学んだ場合は `{workspace_path}` に追記する
- このチャンネル固有の情報（今日の天気、チームの現状、チャンネル内でよく使う情報など）を学んだ場合は `{channel_path}` に追記する
- 記憶の追記: Bash ツールで `printf '\\n- 新しい情報\\n' >> /path/to/file.md`
- 一時的な情報（今日の予定など日付が変われば無意味になる情報）は記憶に書かない
- 更新すべき情報がなければ記憶ファイルは触らない
"""


@dataclass
class _SessionEntry:
    client: ClaudeSDKClient
    channel_id: str
    last_used: float = field(default_factory=time.time)


class SessionManager:
    def __init__(self) -> None:
        self._sessions: dict[str, _SessionEntry] = {}
        self._lock = asyncio.Lock()

    @staticmethod
    def _log_stderr(line: str) -> None:
        logger.warning("agent stderr: %s", line.rstrip())

    def _build_system_prompt(
        self, channel_id: str, workspace_mem: str, channel_mem: str
    ) -> str:
        parts = [SYSTEM_PROMPT_BASE]
        if workspace_mem:
            parts.append(f"\n## ワークスペース記憶\n{workspace_mem}")
        if channel_mem:
            parts.append(f"\n## チャンネル記憶\n{channel_mem}")
        parts.append(
            MEMORY_UPDATE_INSTRUCTIONS.format(
                workspace_path=memory_store.workspace_path,
                channel_path=memory_store.channel_path(channel_id),
            )
        )
        return "".join(parts)

    def _make_options(self, system_prompt: str) -> ClaudeAgentOptions:
        return ClaudeAgentOptions(
            system_prompt=system_prompt,
            setting_sources=["user"],
            allowed_tools=list(ALLOWED_TOOLS),
            permission_mode=PERMISSION_MODE,
            max_turns=MAX_TURNS,
            stderr=self._log_stderr,
        )

    async def has_session(self, session_key: str) -> bool:
        async with self._lock:
            return session_key in self._sessions

    async def send_message(self, session_key: str, prompt: str, channel_id: str) -> str:
        async with self._lock:
            entry = self._sessions.get(session_key)

        if entry is None:
            workspace_mem = memory_store.load_workspace()
            channel_mem = (
                memory_store.load_channel(channel_id)
                if (CHANNEL_MEMORY_ALL or channel_id in CHANNEL_MEMORY_ENABLED)
                else ""
            )
            system_prompt = self._build_system_prompt(
                channel_id, workspace_mem, channel_mem
            )
            client = ClaudeSDKClient(options=self._make_options(system_prompt))
            await client.connect(prompt)
            entry = _SessionEntry(client=client, channel_id=channel_id)
            async with self._lock:
                self._sessions[session_key] = entry
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
