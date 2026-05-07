"""Summarize collected messages per chat using the Groq API."""

from __future__ import annotations

import logging
import os
from typing import Any

from dotenv import load_dotenv
from groq import Groq

from tg_digest.config import GROQ_MODEL, MIN_MESSAGES_DEFAULT, SUMMARY_PROMPT

load_dotenv()
logger = logging.getLogger(__name__)

# Hard cap on prompt size in characters (Groq accepts ~6k tokens for input).
MAX_PROMPT_CHARS = 12000


def _get_client() -> Groq:
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        raise RuntimeError("GROQ_API_KEY is not set in environment")
    return Groq(api_key=api_key)


def _min_messages() -> int:
    raw = os.getenv("MIN_MESSAGES")
    if not raw:
        return MIN_MESSAGES_DEFAULT
    try:
        return int(raw)
    except ValueError:
        logger.warning("Invalid MIN_MESSAGES=%r, falling back to %d", raw, MIN_MESSAGES_DEFAULT)
        return MIN_MESSAGES_DEFAULT


def summarize_chat(
    chat_name: str,
    messages: list[dict[str, Any]],
    hours: int,
    client: Groq | None = None,
) -> str | None:
    """Summarize a single chat. Returns None if there are too few messages."""
    if len(messages) < _min_messages():
        return None

    messages_text = "\n".join(
        f"[{m['date']}] {m['sender']}: {m['text']}" for m in messages
    )
    if len(messages_text) > MAX_PROMPT_CHARS:
        messages_text = messages_text[:MAX_PROMPT_CHARS] + "\n... (обрезано)"

    prompt = SUMMARY_PROMPT.format(
        chat_name=chat_name, hours=hours, messages=messages_text
    )

    groq_client = client or _get_client()
    try:
        response = groq_client.chat.completions.create(
            model=GROQ_MODEL,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=500,
            temperature=0.3,
        )
        return response.choices[0].message.content
    except Exception as exc:  # noqa: BLE001
        logger.error("Groq summarization failed for %s: %s", chat_name, exc)
        return f"⚠️ Не удалось обработать: {exc}"


def summarize_all(
    chats_data: dict[int, dict[str, Any]], hours: int
) -> list[dict[str, Any]]:
    """Summarize every chat, returning a list of dicts ready for the sender."""
    if not chats_data:
        return []

    client = _get_client()
    results: list[dict[str, Any]] = []
    for chat_id, data in chats_data.items():
        chat_name = data.get("name") or str(chat_id)
        logger.info("Summarizing: %s (%d messages)", chat_name, len(data["messages"]))
        summary = summarize_chat(chat_name, data["messages"], hours, client=client)
        if not summary:
            logger.info("  Skipped %s (too few messages)", chat_name)
            continue

        results.append(
            {
                "chat_id": chat_id,
                "chat_name": chat_name,
                "chat_username": data.get("username"),
                "msg_count": len(data["messages"]),
                "first_msg_id": data["messages"][0]["message_id"],
                "summary": summary,
            }
        )
    return results
