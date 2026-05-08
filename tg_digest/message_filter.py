"""Filter messages by keywords and priority topics."""

from __future__ import annotations

import logging
from typing import Any

from tg_digest.config import (
    ENABLE_CONTENT_FILTER,
    EXCLUDE_KEYWORDS,
    FILTER_MODE,
    PRIORITY_KEYWORDS,
)

logger = logging.getLogger(__name__)


def _has_keyword(text: str, keywords: list[str]) -> bool:
    """Check if text contains any of the keywords (case-insensitive)."""
    text_lower = text.lower()
    return any(kw in text_lower for kw in keywords)


def _calculate_priority_score(text: str) -> int:
    """Calculate priority score based on keyword matches."""
    score = 0
    text_lower = text.lower()
    for category_keywords in PRIORITY_KEYWORDS.values():
        if any(kw in text_lower for kw in category_keywords):
            score += 1
    return score


def filter_messages(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Filter messages by keywords and add priority scores.
    
    Returns filtered list with 'priority_score' added to each message.
    """
    if not ENABLE_CONTENT_FILTER or FILTER_MODE == "off":
        for msg in messages:
            msg["priority_score"] = 0
        return messages

    filtered: list[dict[str, Any]] = []
    excluded_count = 0

    for msg in messages:
        text = msg.get("text", "")
        
        # Exclude unwanted topics
        if _has_keyword(text, EXCLUDE_KEYWORDS):
            if FILTER_MODE == "strict":
                excluded_count += 1
                continue
            # In soft mode, just mark with negative priority
            msg["priority_score"] = -1
        else:
            # Calculate priority score
            msg["priority_score"] = _calculate_priority_score(text)
        
        filtered.append(msg)

    if excluded_count > 0:
        logger.info("Filtered out %d messages with excluded keywords", excluded_count)

    return filtered


def smart_sample_messages(
    messages: list[dict[str, Any]], max_chars: int = 12000
) -> list[dict[str, Any]]:
    """Smart sampling of messages when total text exceeds max_chars.
    
    Strategy:
    1. Always include high-priority messages (priority_score > 0)
    2. Take first 20% (discussion starts)
    3. Take last 30% (recent activity)
    4. From middle: only long messages (>100 chars) or priority messages
    """
    if not messages:
        return []

    # Calculate total size
    total_chars = sum(len(m.get("text", "")) for m in messages)
    if total_chars <= max_chars:
        return messages

    logger.info(
        "Chat has %d chars, sampling to fit %d chars limit", total_chars, max_chars
    )

    # Sort by priority (keep original order for same priority)
    messages_with_idx = [(i, m) for i, m in enumerate(messages)]
    
    # Separate high-priority messages
    high_priority = [
        (i, m) for i, m in messages_with_idx if m.get("priority_score", 0) > 0
    ]
    
    total = len(messages)
    start_count = max(int(total * 0.2), 5)
    end_count = max(int(total * 0.3), 10)
    
    # Take start and end
    start_msgs = messages_with_idx[:start_count]
    end_msgs = messages_with_idx[-end_count:]
    
    # From middle: long or priority messages
    middle_start = start_count
    middle_end = total - end_count
    middle_msgs = [
        (i, m)
        for i, m in messages_with_idx[middle_start:middle_end]
        if len(m.get("text", "")) > 100 or m.get("priority_score", 0) > 0
    ]
    
    # Combine and deduplicate by index
    selected_indices = set()
    selected: list[tuple[int, dict[str, Any]]] = []
    
    for idx, msg in start_msgs + high_priority + middle_msgs + end_msgs:
        if idx not in selected_indices:
            selected_indices.add(idx)
            selected.append((idx, msg))
    
    # Sort by original index to maintain chronological order
    selected.sort(key=lambda x: x[0])
    result = [m for _, m in selected]
    
    # Check if still too large, trim from middle
    current_chars = sum(len(m.get("text", "")) for m in result)
    if current_chars > max_chars:
        # Simple truncation from middle
        keep_ratio = max_chars / current_chars
        keep_count = int(len(result) * keep_ratio)
        
        start_keep = keep_count // 2
        end_keep = keep_count - start_keep
        
        result = result[:start_keep] + result[-end_keep:]
    
    logger.info("Sampled %d messages from %d total", len(result), total)
    return result
