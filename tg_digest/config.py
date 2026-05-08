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
     "vibecoderchat",
     "ArgentinaLawyer",
     "htmlshit",
     "RuArgentina",
     "cybers",
     "ecotopor",
     "it_krasavchik",
     "romarayt",
     "anikin_crypto",
     "AI_Handler",
     "nullscode",
     -1002189876460
     # -2189876460,  # ❌ Неправильный ID - закомментирован
     # Для приватных чатов используйте формат: -100XXXXXXXXXX
     # Чтобы узнать правильный ID:
     # 1. Перешлите сообщение из чата боту @userinfobot
     # 2. Или используйте username чата если есть
]

# Chats to skip even if they appear in CHATS_TO_MONITOR (matched by title or username).
CHATS_BLACKLIST: list[str] = [
    # "some_spam_channel",
]

# Summarization prompt. ``{chat_name}``, ``{hours}`` and ``{messages}``
# are filled in by ``summarizer.py``.
SUMMARY_PROMPT: str = """\
Ты аналитик, который создает структурированный дайджест Telegram-чата.

ЗАДАЧА:
1. Проанализируй сообщения и выдели отдельные ТЕМЫ обсуждения
2. Для каждой темы укажи:
   - Краткое название темы (3-7 слов)
   - Суть обсуждения (1-2 предложения)
   - ID первого сообщения темы (message_id)
   - Важность темы (важно/обычно)

ФИЛЬТРАЦИЯ:
❌ ИГНОРИРУЙ темы: война, военные действия, политика, конфликты
✅ ПРИОРИТЕТ темам: 
   - Технологии, AI, программирование, нейросети
   - Подписки, сервисы, софт, приложения
   - Финансы, криптовалюта, обмен денег, банки
   - Эмиграция, переезд, релокация
   - Гражданство, визы, документы

ПРАВИЛА:
- Пропускай флуд, мемы, приветствия
- Группируй связанные сообщения в одну тему
- Если тема важная (решения, факты, полезная инфо) — отметь как "важно"
- Минимум 2, максимум 7 тем на чат

ФОРМАТ ОТВЕТА (строго JSON):
{{
  "topics": [
    {{
      "title": "Название темы",
      "summary": "Краткое описание обсуждения",
      "first_message_id": 12345,
      "importance": "важно"
    }}
  ]
}}

Чат: "{chat_name}" (последние {hours} часов)
Сообщения:
{messages}

Ответь ТОЛЬКО JSON, без дополнительного текста.
"""

# Minimum number of messages in a chat for it to be included in the digest.
# Override via ``MIN_MESSAGES`` in ``.env`` if needed.
MIN_MESSAGES_DEFAULT: int = 3

# Groq model used for summarization.
GROQ_MODEL: str = "llama-3.3-70b-versatile"

# Фильтрация контента
ENABLE_CONTENT_FILTER: bool = True
FILTER_MODE: str = "soft"  # "soft" | "strict" | "off"

# Тематическая группировка
ENABLE_TOPIC_GROUPING: bool = True
MIN_MESSAGES_PER_TOPIC: int = 3
MAX_TOPICS_PER_CHAT: int = 7

# Ключевые слова для фильтрации
PRIORITY_KEYWORDS: dict[str, list[str]] = {
    "tech": [
        "ai", "ml", "gpt", "chatgpt", "claude", "llm", "нейросет", "нейронн",
        "машинное обучение", "deep learning", "tensorflow", "pytorch",
        "программирование", "код", "разработка", "api", "sdk", "github"
    ],
    "finance": [
        "крипт", "bitcoin", "btc", "eth", "usdt", "обмен", "валют", "курс",
        "деньги", "банк", "карт", "перевод", "wise", "revolut", "paypal",
        "инвестиц", "доллар", "евро", "рубл"
    ],
    "relocation": [
        "эмигр", "переезд", "релокац", "виз", "гражданств", "внж", "пмж",
        "граница", "документ", "посольств", "консульств", "легализац",
        "миграц", "резиденц"
    ],
    "subscriptions": [
        "подписк", "subscription", "сервис", "софт", "приложен", "app",
        "premium", "pro", "trial", "скидк", "промокод", "акци"
    ],
}

EXCLUDE_KEYWORDS: list[str] = [
    "войн", "военн", "армия", "фронт", "удар", "обстрел", "мобилизац",
    "призыв", "военкомат", "всу", "атак", "бомб", "ракет", "снаряд"
]
