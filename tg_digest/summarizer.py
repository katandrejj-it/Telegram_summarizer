"""Summarize collected messages per chat using the Groq API."""

from __future__ import annotations

import json
import logging
import os
import re
from typing import Any

from dotenv import load_dotenv
from groq import Groq

from tg_digest.config import GROQ_MODEL, MIN_MESSAGES_DEFAULT, SUMMARY_PROMPT
from tg_digest.message_filter import filter_messages, smart_sample_messages

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


def _extract_json_from_response(response_text: str) -> dict[str, Any] | None:
    """Extract JSON from LLM response, handling markdown code blocks."""
    if not response_text:
        return None
    
    # Try to find JSON in markdown code block
    json_match = re.search(r'```(?:json)?\s*({.*?})\s*```', response_text, re.DOTALL)
    if json_match:
        try:
            return json.loads(json_match.group(1))
        except json.JSONDecodeError:
            pass
    
    # Try to parse entire response as JSON
    try:
        return json.loads(response_text)
    except json.JSONDecodeError:
        pass
    
    # Try to find JSON object in text
    json_match = re.search(r'{.*}', response_text, re.DOTALL)
    if json_match:
        try:
            return json.loads(json_match.group(0))
        except json.JSONDecodeError:
            pass
    
    return None


def _format_message_with_id(m: dict[str, Any]) -> str:
    """Format message with ID for LLM to reference."""
    return f"[{m['date']}] [ID:{m['message_id']}] {m['sender']}: {m['text']}"


def summarize_chat(
    chat_name: str,
    messages: list[dict[str, Any]],
    hours: int,
    client: Groq | None = None,
) -> dict[str, Any] | None:
    """Summarize a single chat. Returns dict with topics or None if too few messages."""
    if len(messages) < _min_messages():
        return None

    # Apply filtering and smart sampling
    filtered_messages = filter_messages(messages)
    if not filtered_messages:
        logger.info("All messages filtered out for %s", chat_name)
        return None
    
    sampled_messages = smart_sample_messages(filtered_messages, MAX_PROMPT_CHARS)
    
    messages_text = "\n".join(
        _format_message_with_id(m) for m in sampled_messages
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
            max_tokens=800,
            temperature=0.2,
        )
        response_text = response.choices[0].message.content
        
        # Try to parse JSON response
        result = _extract_json_from_response(response_text)
        if result and "topics" in result:
            return result
        
        # Fallback: return as plain text
        logger.warning("Could not parse JSON from response for %s, using fallback", chat_name)
        return {
            "topics": [
                {
                    "title": "Общее обсуждение",
                    "summary": response_text[:500],
                    "first_message_id": sampled_messages[0]["message_id"],
                    "importance": "обычно",
                }
            ]
        }
    except Exception as exc:  # noqa: BLE001
        logger.error("Groq summarization failed for %s: %s", chat_name, exc)
        return {
            "topics": [
                {
                    "title": "Ошибка обработки",
                    "summary": f"⚠️ Не удалось обработать: {exc}",
                    "first_message_id": messages[0]["message_id"],
                    "importance": "обычно",
                }
            ]
        }


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
        summary_result = summarize_chat(chat_name, data["messages"], hours, client=client)
        if not summary_result:
            logger.info("  Skipped %s (too few messages)", chat_name)
            continue

        results.append(
            {
                "chat_id": chat_id,
                "chat_name": chat_name,
                "chat_username": data.get("username"),
                "msg_count": len(data["messages"]),
                "first_msg_id": data["messages"][0]["message_id"],
                "topics": summary_result.get("topics", []),
            }
        )
    return results
