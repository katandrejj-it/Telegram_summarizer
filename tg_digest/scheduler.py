"""Entry point: collects messages, summarizes them and sends the digest.

Usage:
    python -m tg_digest.scheduler            # run on schedule (DIGEST_TIME from .env)
    python -m tg_digest.scheduler --once     # run a single full pipeline pass and exit
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import os
import time

import schedule
from dotenv import load_dotenv

from tg_digest.collector import collect_messages
from tg_digest.database import get_messages_for_digest, init_db, log_digest_run
from tg_digest.digest_sender import send_digest
from tg_digest.summarizer import summarize_all

load_dotenv()
logger = logging.getLogger(__name__)


def _hours_back() -> int:
    return int(os.getenv("HOURS_BACK", "24"))


def _digest_time() -> str:
    return os.getenv("DIGEST_TIME", "08:00")


async def run_pipeline() -> None:
    """Full cycle: collect -> summarize -> send."""
    hours = _hours_back()
    logger.info("=== Pipeline start (HOURS_BACK=%d) ===", hours)

    status = "ok"
    summaries: list[dict] = []
    try:
        await collect_messages(hours_back=hours)
        chats_data = get_messages_for_digest(hours_back=hours)
        summaries = summarize_all(chats_data, hours=hours)
        await send_digest(summaries, hours=hours)
    except Exception as exc:  # noqa: BLE001
        status = f"error: {exc}"
        logger.exception("Pipeline failed")
        raise
    finally:
        log_digest_run(hours_back=hours, chats_count=len(summaries), status=status)
        logger.info("=== Pipeline finished (status=%s) ===", status)


def _job() -> None:
    asyncio.run(run_pipeline())


def main() -> None:
    logging.basicConfig(
        level=os.getenv("LOG_LEVEL", "INFO"),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    parser = argparse.ArgumentParser(description="Telegram AI digest")
    parser.add_argument(
        "--once",
        action="store_true",
        help="Run the pipeline once and exit (skip the scheduler loop).",
    )
    args = parser.parse_args()

    init_db()

    if args.once:
        _job()
        return

    digest_time = _digest_time()
    schedule.every().day.at(digest_time).do(_job)
    logger.info("Scheduler started. Digest will be sent at %s", digest_time)

    while True:
        schedule.run_pending()
        time.sleep(60)


if __name__ == "__main__":
    main()
