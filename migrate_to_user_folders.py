#!/usr/bin/env python3
"""
Скрипт для миграции существующих папок в пользовательскую структуру.
Переносит все папки из downloads/ в downloads/{username}/
"""

import shutil
from pathlib import Path


def migrate_folders(username: str = "lexey"):
    """
    Переносит все папки из downloads/ в downloads/{username}/
    
    Args:
        username: Имя пользователя для создания папки
    """
    downloads_dir = Path("downloads")
    
    if not downloads_dir.exists():
        print("❌ Папка downloads не найдена")
        return
    
    # Создаем пользовательскую папку
    user_folder = downloads_dir / username
    user_folder.mkdir(parents=True, exist_ok=True)
    
    print(f"📁 Создана пользовательская папка: {user_folder}")
    print()
    
    # Получаем все папки в downloads (кроме пользовательских)
    folders = [
        d for d in downloads_dir.iterdir() 
        if d.is_dir() and d.name != username  # Исключаем саму пользовательскую папку
    ]
    
    if not folders:
        print("ℹ️  Нет папок для миграции")
        return
    
    print(f"🔍 Найдено папок для миграции: {len(folders)}")
    print()
    
    # Переносим каждую папку
    moved_count = 0
    for folder in sorted(folders):
        try:
            destination = user_folder / folder.name
            
            # Проверяем, не существует ли уже такая папка
            if destination.exists():
                print(f"⚠️  Пропущена (уже существует): {folder.name}")
                continue
            
            # Переносим папку
            shutil.move(str(folder), str(destination))
            print(f"✅ Перенесена: {folder.name}")
            moved_count += 1
            
        except Exception as e:
            print(f"❌ Ошибка при переносе {folder.name}: {e}")
    
    print()
    print("=" * 80)
    print(f"📊 Миграция завершена!")
    print(f"✅ Успешно перенесено: {moved_count} папок")
    print(f"📂 Целевая папка: {user_folder}")
    print("=" * 80)


if __name__ == "__main__":
    print("=" * 80)
    print("🔄 МИГРАЦИЯ В МНОГОПОЛЬЗОВАТЕЛЬСКУЮ СТРУКТУРУ")
    print("=" * 80)
    print()
    
    # Запрашиваем подтверждение
    response = input("Перенести все папки в downloads/lexey/? (yes/no): ").strip().lower()
    
    if response in ['yes', 'y', 'да']:
        print()
        migrate_folders("lexey")
    else:
        print("❌ Миграция отменена")
