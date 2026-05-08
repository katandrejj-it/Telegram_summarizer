"""Format the summarized digest and send it to you via your Telegram bot."""

from __future__ import annotations

import logging
import os
import re
from typing import Any

from dotenv import load_dotenv
from telegram import Bot
from telegram.constants import ParseMode

load_dotenv()
logger = logging.getLogger(__name__)

# Markdown V1 special chars that must be escaped in chat names / sender labels
# to avoid Telegram parser errors.
_MD_SPECIALS = re.compile(r"([_*\[\]`])")


def _escape_md(text: str) -> str:
    return _MD_SPECIALS.sub(r"\\\1", text)


def make_tg_link(chat_id: int, message_id: int, username: str | None = None) -> str:
    """Build a direct link to a Telegram message.

    - Public chats with a username -> https://t.me/<username>/<msg_id>
    - Private/super-groups         -> https://t.me/c/<id without -100>/<msg_id>
    """
    if username:
        return f"https://t.me/{username}/{message_id}"
    clean_id = str(chat_id).lstrip("-")
    if clean_id.startswith("100"):
        clean_id = clean_id[3:]
    return f"https://t.me/c/{clean_id}/{message_id}"


def _build_bot() -> Bot:
    token = os.getenv("BOT_TOKEN")
    if not token:
        raise RuntimeError("BOT_TOKEN is not set in environment")
    return Bot(token=token)


def _target_chat_id() -> str:
    chat_id = os.getenv("YOUR_CHAT_ID")
    if not chat_id:
        raise RuntimeError("YOUR_CHAT_ID is not set in environment")
    return chat_id


def _format_digest_item(item: dict[str, Any]) -> str:
    """Format digest item with topics and links."""
    topics = item.get("topics", [])
    
    header = (
        f"💬 *{_escape_md(item['chat_name'])}*\n"
        f"📊 {item['msg_count']} сообщений\n\n"
    )
    
    if not topics:
        return header + "Нет значимых обсуждений\n"
    
    body = ""
    for topic in topics:
        importance = topic.get("importance", "обычно")
        icon = "⚡" if importance == "важно" else "🔹"
        
        title = topic.get("title", "Без названия")
        summary = topic.get("summary", "")
        first_msg_id = topic.get("first_message_id", item.get("first_msg_id"))
        
        link = make_tg_link(
            item["chat_id"], 
            first_msg_id, 
            item.get("chat_username")
        )
        
        body += (
            f"{icon} *{_escape_md(title)}*\n"
            f"   {summary}\n"
            f"   [→ Перейти к обсуждению]({link})\n\n"
        )
    
    return header + body


def _format_digest_item_plain(item: dict[str, Any]) -> str:
    """Format digest item as plain text (fallback)."""
    topics = item.get("topics", [])
    
    header = (
        f"💬 {item['chat_name']}\n"
        f"📊 {item['msg_count']} сообщений\n\n"
    )
    
    if not topics:
        return header + "Нет значимых обсуждений\n"
    
    body = ""
    for topic in topics:
        importance = topic.get("importance", "обычно")
        icon = "⚡" if importance == "важно" else "🔹"
        
        title = topic.get("title", "Без названия")
        summary = topic.get("summary", "")
        first_msg_id = topic.get("first_message_id", item.get("first_msg_id"))
        
        link = make_tg_link(
            item["chat_id"], 
            first_msg_id, 
            item.get("chat_username")
        )
        
        body += f"{icon} {title}\n   {summary}\n   {link}\n\n"
    
    return header + body


async def send_digest(summaries: list[dict[str, Any]], hours: int) -> None:
    """Send the assembled digest to the configured chat."""
    bot = _build_bot()
    target = _target_chat_id()

    if not summaries:
        await bot.send_message(
            chat_id=target,
            text=f"📭 Дайджест за {hours}ч: новых сообщений не найдено",
        )
        return

    header = (
        f"📰 *Дайджест за последние {hours} часов*\n"
        f"\n✅ Обработано чатов: {len(summaries)}\n"
        f"{'─' * 30}\n"
    )
    await bot.send_message(chat_id=target, text=header, parse_mode=ParseMode.MARKDOWN)

    for item in summaries:
        text = _format_digest_item(item)
        try:
            await bot.send_message(
                chat_id=target,
                text=text,
                parse_mode=ParseMode.MARKDOWN,
                disable_web_page_preview=True,
            )
        except Exception as exc:  # noqa: BLE001
            logger.error("Failed to send digest item for %s: %s", item["chat_name"], exc)
            # Fallback to plain text
            try:
                plain_text = _format_digest_item_plain(item)
                await bot.send_message(
                    chat_id=target,
                    text=plain_text,
                    disable_web_page_preview=True,
                )
            except Exception as exc2:  # noqa: BLE001
                logger.error("Plain text fallback also failed: %s", exc2)
