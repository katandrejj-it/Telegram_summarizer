#!/usr/bin/env python3
"""Утилита для получения ID всех доступных чатов.

Использование:
    python get_chat_ids.py
"""

import asyncio
import sys
from pathlib import Path

# Добавляем путь к модулям проекта
sys.path.insert(0, str(Path(__file__).parent))

from tg_digest.collector import _build_client


async def list_all_chats():
    """Выводит список всех доступных чатов с их ID."""
    print("🔍 Получение списка чатов...\n")
    
    client = _build_client()
    await client.start()
    
    try:
        dialogs = await client.get_dialogs(limit=100)
        
        print(f"📊 Найдено {len(dialogs)} чатов/каналов:\n")
        print("=" * 80)
        
        for i, dialog in enumerate(dialogs, 1):
            name = dialog.name or "Без названия"
            chat_id = dialog.id
            username = getattr(dialog.entity, 'username', None)
            
            # Определяем тип
            entity_type = type(dialog.entity).__name__
            if entity_type == "Channel":
                chat_type = "📢 Канал"
            elif entity_type == "Chat":
                chat_type = "💬 Группа"
            elif entity_type == "User":
                chat_type = "👤 Личный чат"
            else:
                chat_type = f"❓ {entity_type}"
            
            print(f"{i}. {chat_type}: {name}")
            print(f"   ID: {chat_id}")
            
            if username:
                print(f"   Username: @{username}")
                print(f"   Для config.py: \"{username}\"")
            else:
                print(f"   Username: нет")
                print(f"   Для config.py: {chat_id}")
            
            print()
        
        print("=" * 80)
        print("\n💡 Как использовать:")
        print("1. Скопируйте нужные username или ID")
        print("2. Добавьте в tg_digest/config.py в список CHATS_TO_MONITOR")
        print("\nПример:")
        print("CHATS_TO_MONITOR = [")
        print("    \"durov\",           # Если есть username")
        print("    -1001234567890,     # Если нет username (используйте ID)")
        print("]")
        
    finally:
        await client.disconnect()


if __name__ == "__main__":
    asyncio.run(list_all_chats())
