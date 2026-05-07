"""Collect new messages from monitored chats via Telethon (reads as your account)."""

from __future__ import annotations

import logging
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from telethon import TelegramClient
from telethon.tl.types import Channel, Chat, User

from tg_digest.config import CHATS_BLACKLIST, CHATS_TO_MONITOR
from tg_digest.database import save_messages

load_dotenv()
logger = logging.getLogger(__name__)

SESSION_PATH = Path(__file__).resolve().parent.parent / "session_name"


def _build_client() -> TelegramClient:
    api_id = os.getenv("TG_API_ID")
    api_hash = os.getenv("TG_API_HASH")
    if not api_id or not api_hash:
        raise RuntimeError("TG_API_ID/TG_API_HASH are not set in environment")
    return TelegramClient(str(SESSION_PATH), int(api_id), api_hash)


def _format_chat_name(entity: Channel | Chat | User | object, fallback: str) -> str:
    """Best-effort human readable name for any kind of entity."""
    title = getattr(entity, "title", None)
    if title:
        return str(title)
    first = getattr(entity, "first_name", "") or ""
    last = getattr(entity, "last_name", "") or ""
    full = f"{first} {last}".strip()
    if full:
        return full
    username = getattr(entity, "username", None)
    if username:
        return f"@{username}"
    return fallback


def _format_sender(sender: object) -> str:
    if sender is None:
        return "Unknown"
    first = getattr(sender, "first_name", "") or ""
    last = getattr(sender, "last_name", "") or ""
    full = f"{first} {last}".strip()
    if full:
        return full
    username = getattr(sender, "username", None)
    if username:
        return f"@{username}"
    title = getattr(sender, "title", None)
    if title:
        return str(title)
    return "Unknown"


async def collect_messages(hours_back: int = 24) -> int:
    """Fetch messages from all CHATS_TO_MONITOR and persist them.

    Returns the total number of messages saved (after de-duplication).
    """
    if not CHATS_TO_MONITOR:
        logger.warning(
            "CHATS_TO_MONITOR is empty — nothing to collect. "
            "Add chats in tg_digest/config.py."
        )
        return 0

    client = _build_client()
    phone = os.getenv("TG_PHONE")
    await client.start(phone=phone) if phone else await client.start()

    cutoff_date = datetime.now(tz=timezone.utc) - timedelta(hours=hours_back)
    all_messages: list[dict[str, Any]] = []

    try:
        for chat_identifier in CHATS_TO_MONITOR:
            try:
                entity = await client.get_entity(chat_identifier)
            except Exception as exc:  # noqa: BLE001 - we want to keep going
                logger.error("Cannot resolve %s: %s", chat_identifier, exc)
                continue

            chat_name = _format_chat_name(entity, fallback=str(chat_identifier))
            chat_username = getattr(entity, "username", None)

            if (
                chat_name in CHATS_BLACKLIST
                or (chat_username and chat_username in CHATS_BLACKLIST)
            ):
                logger.info("Skipping blacklisted chat: %s", chat_name)
                continue

            logger.info("Collecting from: %s", chat_name)

            count_in_chat = 0
            try:
                async for message in client.iter_messages(
                    entity, offset_date=cutoff_date, reverse=True
                ):
                    if not message.text or len(message.text.strip()) < 5:
                        continue

                    sender_name = _format_sender(message.sender)

                    all_messages.append(
                        {
                            "chat_id": entity.id,
                            "chat_name": chat_name,
                            "chat_username": chat_username,
                            "message_id": message.id,
                            "sender": sender_name,
                            "text": message.text[:1000],
                            "date": message.date,
                        }
                    )
                    count_in_chat += 1
            except Exception as exc:  # noqa: BLE001
                logger.error("Error iterating %s: %s", chat_name, exc)
                continue

            logger.info("  %d messages collected from %s", count_in_chat, chat_name)
    finally:
        await client.disconnect()

    inserted = save_messages(all_messages)
    logger.info(
        "Collector done: %d messages received, %d new in DB, %d chats configured",
        len(all_messages),
        inserted,
        len(CHATS_TO_MONITOR),
    )
    return inserted
