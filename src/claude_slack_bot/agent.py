from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from claude_agent_sdk import ClaudeAgentOptions, ClaudeSDKClient
from claude_agent_sdk.types import (
    AssistantMessage,
    HookContext,
    HookMatcher,
    ResultMessage,
    SyncHookJSONOutput,
    TextBlock,
)

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

MEMORY_HOOK_SYSTEM_PROMPT = """\
あなたは記憶管理エージェントです。与えられた会話トランスクリプトを分析し、
長期記憶として保存すべき情報があれば適切なファイルに追記してください。
記憶すべき情報がなければ何もしないでください。
"""

MEMORY_HOOK_PROMPT_TEMPLATE = """\
以下の会話トランスクリプトを分析し、長期記憶として保存すべき情報があれば追記してください。

## 記憶ファイル
- ワークスペース全体の永続的な事実（会社情報、人物情報など） → `{workspace_path}`
{channel_line}

## 会話トランスクリプト
{transcript}

## ルール
- 永続的な事実のみ記憶する（今日の予定・天気など一時的な情報は除く）
- 追記: `printf '\\n- 情報\\n' >> /path/to/file.md`
- 記憶不要なら何もしない
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

    def _build_system_prompt(self, workspace_mem: str, channel_mem: str) -> str:
        parts = [SYSTEM_PROMPT_BASE]
        if workspace_mem:
            parts.append(f"\n## ワークスペース記憶\n{workspace_mem}")
        if channel_mem:
            parts.append(f"\n## チャンネル記憶\n{channel_mem}")
        return "".join(parts)

    def _make_stop_hook(
        self, channel_id: str, channel_mem_enabled: bool
    ):  # -> HookCallback
        async def on_stop(
            hook_input: Any,
            tool_use_id: str | None,
            context: HookContext,
        ) -> SyncHookJSONOutput:
            transcript_path = hook_input.get("transcript_path", "")
            transcript = ""
            if transcript_path:
                try:
                    transcript = Path(transcript_path).read_text()
                except Exception:
                    logger.warning("Could not read transcript at %s", transcript_path)

            asyncio.create_task(
                self._run_memory_hook(channel_id, transcript, channel_mem_enabled)
            )
            return {}

        return on_stop

    def _make_options(
        self, system_prompt: str, channel_id: str, channel_mem_enabled: bool
    ) -> ClaudeAgentOptions:
        return ClaudeAgentOptions(
            system_prompt=system_prompt,
            setting_sources=["user"],
            allowed_tools=list(ALLOWED_TOOLS),
            permission_mode=PERMISSION_MODE,
            max_turns=MAX_TURNS,
            stderr=self._log_stderr,
            hooks={
                "Stop": [
                    HookMatcher(
                        hooks=[self._make_stop_hook(channel_id, channel_mem_enabled)]
                    )
                ]
            },
        )

    async def has_session(self, session_key: str) -> bool:
        async with self._lock:
            return session_key in self._sessions

    async def send_message(self, session_key: str, prompt: str, channel_id: str) -> str:
        async with self._lock:
            entry = self._sessions.get(session_key)

        if entry is None:
            workspace_mem = memory_store.load_workspace()
            channel_mem_enabled = (
                CHANNEL_MEMORY_ALL or channel_id in CHANNEL_MEMORY_ENABLED
            )
            channel_mem = (
                memory_store.load_channel(channel_id) if channel_mem_enabled else ""
            )
            system_prompt = self._build_system_prompt(workspace_mem, channel_mem)
            client = ClaudeSDKClient(
                options=self._make_options(
                    system_prompt, channel_id, channel_mem_enabled
                )
            )
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

    async def _run_memory_hook(
        self,
        channel_id: str,
        transcript: str,
        channel_mem_enabled: bool,
    ) -> None:
        if not transcript:
            return

        channel_line = (
            f"- このチャンネル固有の情報 → `{memory_store.channel_path(channel_id)}`"
            if channel_mem_enabled
            else ""
        )
        memory_prompt = MEMORY_HOOK_PROMPT_TEMPLATE.format(
            workspace_path=memory_store.workspace_path,
            channel_line=channel_line,
            transcript=transcript,
        )
        options = ClaudeAgentOptions(
            system_prompt=MEMORY_HOOK_SYSTEM_PROMPT,
            model="claude-haiku-4-5",
            allowed_tools=["Bash", "Read", "Write"],
            permission_mode="bypassPermissions",
            max_turns=5,
            stderr=self._log_stderr,
            add_dirs=[memory_store._dir],
        )

        # 更新前のファイル mtime を記録
        def _mtime(p: Path) -> float:
            return p.stat().st_mtime if p.exists() else 0.0

        workspace_mtime_before = _mtime(memory_store.workspace_path)
        channel_mtime_before = _mtime(memory_store.channel_path(channel_id))

        logger.info("Memory hook started for channel %s", channel_id)
        client = ClaudeSDKClient(options=options)
        try:
            await client.connect(memory_prompt)
            async for _ in client.receive_response():
                pass
        except Exception:
            logger.exception("Memory hook error for channel %s", channel_id)
        finally:
            try:
                await client.disconnect()
            except Exception:
                pass

        # 更新されたファイルをログに出す
        updated = []
        if _mtime(memory_store.workspace_path) != workspace_mtime_before:
            updated.append("workspace.md")
        if (
            channel_mem_enabled
            and _mtime(memory_store.channel_path(channel_id)) != channel_mtime_before
        ):
            updated.append(f"channels/{channel_id}.md")

        if updated:
            logger.info("Memory hook updated: %s", ", ".join(updated))
        else:
            logger.info("Memory hook completed (no updates) for channel %s", channel_id)

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
