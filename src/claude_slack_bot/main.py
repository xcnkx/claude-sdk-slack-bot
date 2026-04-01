from __future__ import annotations

import asyncio
import logging
import os
import signal
import sys

from dotenv import load_dotenv

load_dotenv()

from slack_bolt.adapter.socket_mode.async_handler import AsyncSocketModeHandler

from claude_slack_bot.bot import app, session_manager
from claude_slack_bot.config import SLACK_APP_TOKEN

log_level = os.getenv("LOG_LEVEL", "INFO").upper()
logging.basicConfig(
    level=getattr(logging, log_level, logging.INFO),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    stream=sys.stdout,
)
logger = logging.getLogger(__name__)

CLEANUP_INTERVAL_SECONDS = 300


async def _periodic_cleanup() -> None:
    while True:
        await asyncio.sleep(CLEANUP_INTERVAL_SECONDS)
        await session_manager.cleanup()


async def _run() -> None:
    handler = AsyncSocketModeHandler(app, SLACK_APP_TOKEN)

    cleanup_task = asyncio.create_task(_periodic_cleanup())

    loop = asyncio.get_running_loop()
    stop = asyncio.Event()

    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, stop.set)

    logger.info("Starting Claude Slack Bot...")
    await handler.connect_async()
    logger.info("Bot is running. Press Ctrl+C to stop.")

    await stop.wait()

    logger.info("Shutting down...")
    cleanup_task.cancel()
    await session_manager.shutdown()
    await handler.close_async()


def main() -> None:
    asyncio.run(_run())


if __name__ == "__main__":
    main()
