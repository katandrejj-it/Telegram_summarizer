#!/usr/bin/env python3
"""Проверка конкретного чата - есть ли в нем сообщения."""

import asyncio
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from tg_digest.collector import _build_client


async def check_chat(chat_id_or_username, days_back=7):
    """Проверяет есть ли сообщения в чате за последние N дней."""
    print(f"🔍 Проверка чата: {chat_id_or_username}")
    print(f"📅 Период: последние {days_back} дней\n")
    
    client = _build_client()
    await client.start()
    
    try:
        # Получаем информацию о чате
        entity = await client.get_entity(chat_id_or_username)
        
        print(f"✅ Чат найден:")
        print(f"   Название: {getattr(entity, 'title', getattr(entity, 'first_name', 'N/A'))}")
        print(f"   ID: {entity.id}")
        print(f"   Username: @{getattr(entity, 'username', 'нет')}")
        print(f"   Тип: {type(entity).__name__}\n")
        
        # Проверяем сообщения
        cutoff_date = datetime.now(tz=timezone.utc) - timedelta(days=days_back)
        
        print(f"📊 Сбор сообщений с {cutoff_date.strftime('%Y-%m-%d %H:%M')}...\n")
        
        messages = []
        async for message in client.iter_messages(
            entity, offset_date=cutoff_date, reverse=True, limit=100
        ):
            if message.text:
                messages.append({
                    'id': message.id,
                    'date': message.date,
                    'text': message.text[:100],
                    'sender': getattr(message.sender, 'first_name', 'Unknown') if message.sender else 'Unknown'
                })
        
        if not messages:
            print("❌ Сообщений не найдено за указанный период")
            print("\n💡 Возможные причины:")
            print("   1. Чат неактивен")
            print("   2. У вас нет доступа к истории")
            print("   3. Это новый чат без сообщений")
        else:
            print(f"✅ Найдено {len(messages)} сообщений\n")
            print("📝 Последние 5 сообщений:")
            for msg in messages[-5:]:
                print(f"\n   [{msg['date']}] {msg['sender']}")
                print(f"   {msg['text']}")
        
    except Exception as e:
        print(f"❌ Ошибка: {e}")
    finally:
        await client.disconnect()


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Использование: python check_chat.py <chat_id_or_username> [days_back]")
        print("\nПримеры:")
        print("  python check_chat.py -1002189876460")
        print("  python check_chat.py ArgentinaLawyer")
        print("  python check_chat.py -1002189876460 30  # за последние 30 дней")
        sys.exit(1)
    
    chat = sys.argv[1]
    days = int(sys.argv[2]) if len(sys.argv) > 2 else 7
    
    # Преобразуем в int если это ID
    if chat.startswith('-') or chat.isdigit():
        chat = int(chat)
    
    asyncio.run(check_chat(chat, days))
