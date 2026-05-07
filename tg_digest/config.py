"""Project configuration: chats to monitor, blacklist and the summarization prompt.

All secrets live in ``.env`` (see ``.env.example``); this file only holds
non-sensitive settings that are convenient to tweak in code.
"""

from __future__ import annotations

# Chats / channels to monitor.
# Each entry can be:
#   - a public username (e.g. "durov" for @durov)
#   - a private chat username
#   - a numeric chat id (e.g. -1001234567890) for private chats without a username
CHATS_TO_MONITOR: list[str | int] = [
    # "durov",
    # "some_private_chat",
    # -1001234567890,
]

# Chats to skip even if they appear in CHATS_TO_MONITOR (matched by title or username).
CHATS_BLACKLIST: list[str] = [
    # "some_spam_channel",
]

# Summarization prompt. ``{chat_name}``, ``{hours}`` and ``{messages}``
# are filled in by ``summarizer.py``.
SUMMARY_PROMPT: str = """\
Ты помощник, который делает краткий дайджест переписки.

Правила:
- Выдели 3-5 главных тем или событий
- Каждый пункт — 1-2 предложения
- Пропускай флуд, мемы, приветствия
- Если обсуждались важные решения или факты — выдели отдельно
- Отвечай на русском языке
- Формат: маркированный список

Вот сообщения из чата "{chat_name}" за последние {hours} часов:
{messages}
"""

# Minimum number of messages in a chat for it to be included in the digest.
# Override via ``MIN_MESSAGES`` in ``.env`` if needed.
MIN_MESSAGES_DEFAULT: int = 3

# Groq model used for summarization.
GROQ_MODEL: str = "llama-3.3-70b-versatile"
