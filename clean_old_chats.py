#!/usr/bin/env python3
"""Удаляет сообщения из чатов, которых больше нет в CHATS_TO_MONITOR."""

import sqlite3
from pathlib import Path
from tg_digest.config import CHATS_TO_MONITOR

DB_PATH = Path(__file__).parent / "digest.db"

def clean_old_chats():
    """Удаляет сообщения из чатов, не входящих в CHATS_TO_MONITOR."""
    conn = sqlite3.connect(DB_PATH)
    
    # Получаем список всех чатов в БД
    cursor = conn.execute("SELECT DISTINCT chat_name, chat_username FROM messages")
    all_chats = cursor.fetchall()
    
    # Определяем какие чаты нужно удалить
    to_delete = []
    for chat_name, chat_username in all_chats:
        # Проверяем есть ли чат в CHATS_TO_MONITOR
        is_monitored = False
        for monitor in CHATS_TO_MONITOR:
            if isinstance(monitor, str):
                if monitor.lower() in (chat_name.lower() if chat_name else ""):
                    is_monitored = True
                    break
                if chat_username and monitor.lower() == chat_username.lower():
                    is_monitored = True
                    break
        
        if not is_monitored:
            to_delete.append(chat_name)
    
    if not to_delete:
        print("✅ Нет чатов для удаления. Все чаты в БД актуальны.")
        return
    
    print(f"🗑️  Найдено {len(to_delete)} чатов для удаления:\n")
    for chat in to_delete:
        count = conn.execute(
            "SELECT COUNT(*) FROM messages WHERE chat_name = ?", (chat,)
        ).fetchone()[0]
        print(f"   • {chat} ({count} сообщений)")
    
    confirm = input("\n❓ Удалить эти чаты? (yes/no): ")
    if confirm.lower() != "yes":
        print("❌ Отменено")
        return
    
    # Удаляем
    total_deleted = 0
    for chat in to_delete:
        cursor = conn.execute("DELETE FROM messages WHERE chat_name = ?", (chat,))
        total_deleted += cursor.rowcount
    
    conn.commit()
    conn.close()
    
    print(f"\n✅ Удалено {total_deleted} сообщений из {len(to_delete)} чатов")

if __name__ == "__main__":
    clean_old_chats()
