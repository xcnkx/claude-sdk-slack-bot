from __future__ import annotations

import logging
import re

from slack_bolt.async_app import AsyncApp

from claude_slack_bot.agent import SessionManager
from claude_slack_bot.config import SLACK_BOT_TOKEN

logger = logging.getLogger(__name__)

SLACK_MESSAGE_MAX_LEN = 3900

app = AsyncApp(token=SLACK_BOT_TOKEN)
session_manager = SessionManager()


def _split_text(text: str, max_len: int = SLACK_MESSAGE_MAX_LEN) -> list[str]:
    if len(text) <= max_len:
        return [text]
    chunks: list[str] = []
    while text:
        if len(text) <= max_len:
            chunks.append(text)
            break
        split_at = text.rfind("\n", 0, max_len)
        if split_at == -1:
            split_at = max_len
        chunks.append(text[:split_at])
        text = text[split_at:].lstrip("\n")
    return chunks


def _strip_mention(text: str) -> str:
    return re.sub(r"<@[A-Z0-9]+>", "", text).strip()


@app.event("app_mention")
async def handle_mention(event: dict, say, client) -> None:  # noqa: ANN001
    thread_ts = event.get("thread_ts", event["ts"])
    text = _strip_mention(event.get("text", ""))
    if not text:
        return

    channel = event["channel"]
    ts = event["ts"]

    await client.reactions_add(channel=channel, name="hourglass", timestamp=ts)
    try:
        result = await session_manager.send_message(thread_ts, text)
        for chunk in _split_text(result):
            await say(text=chunk, thread_ts=thread_ts)
    except Exception:
        logger.exception("Error processing message")
        await say(
            text="エラーが発生しました。しばらくしてからお試しください。",
            thread_ts=thread_ts,
        )
    finally:
        try:
            await client.reactions_remove(
                channel=channel, name="hourglass", timestamp=ts
            )
        except Exception:
            pass


@app.event("message")
async def handle_thread_message(event: dict, say, client) -> None:  # noqa: ANN001
    if event.get("subtype"):
        return
    thread_ts = event.get("thread_ts")
    if thread_ts is None:
        return
    if event.get("bot_id"):
        return

    # スレッドにアクティブセッションがある場合のみ反応
    if thread_ts not in session_manager._sessions:
        return

    text = _strip_mention(event.get("text", ""))
    if not text:
        return

    channel = event["channel"]
    ts = event["ts"]

    await client.reactions_add(channel=channel, name="hourglass", timestamp=ts)
    try:
        result = await session_manager.send_message(thread_ts, text)
        for chunk in _split_text(result):
            await say(text=chunk, thread_ts=thread_ts)
    except Exception:
        logger.exception("Error processing thread message")
        await say(
            text="エラーが発生しました。しばらくしてからお試しください。",
            thread_ts=thread_ts,
        )
    finally:
        try:
            await client.reactions_remove(
                channel=channel, name="hourglass", timestamp=ts
            )
        except Exception:
            pass
