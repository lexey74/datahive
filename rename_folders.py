#!/usr/bin/env python3
"""
Скрипт для переименования папок downloads/ в соответствии с новым паттерном.
Паттерн: {YYYY-MM-DD}_{HH-MM}_{Platform}_{SlugTitle}

Дата и время берутся из:
1. Метаданных медиафайлов (modification time)
2. Если нет медиа - из папки

Использование:
    python3 rename_folders.py              # Интерактивный режим с подтверждением
    python3 rename_folders.py --dry-run    # Только просмотр, без подтверждения
    python3 rename_folders.py --apply      # Применить без подтверждения
"""

import re
import sys
from pathlib import Path
from datetime import datetime
import shutil


def get_media_creation_time(folder: Path) -> datetime:
    """
    Получает дату создания из медиафайлов в папке
    
    Args:
        folder: Путь к папке
        
    Returns:
        datetime объект
    """
    folder_name = folder.name
    
    # Для telegram и temp папок пытаемся извлечь дату из имени
    # Формат: telegram_video_YYYYMMDD_HHMMSS или temp_YYYYMMDD_HHMMSS
    date_match = re.search(r'_(\d{8})_(\d{6})$', folder_name)
    if date_match:
        date_str = date_match.group(1)  # YYYYMMDD
        time_str = date_match.group(2)  # HHMMSS
        try:
            return datetime.strptime(f"{date_str}{time_str}", "%Y%m%d%H%M%S")
        except ValueError:
            pass
    
    # Приоритет: mp4 > jpg > webp > png
    media_extensions = ['.mp4', '.jpg', '.webp', '.png', '.jpeg']
    
    for ext in media_extensions:
        media_files = list(folder.glob(f'*{ext}'))
        if media_files:
            # Берем самый старый файл (первый загруженный)
            oldest = min(media_files, key=lambda p: p.stat().st_mtime)
            timestamp = oldest.stat().st_mtime
            return datetime.fromtimestamp(timestamp)
    
    # Если медиа нет, берем время создания папки
    timestamp = folder.stat().st_mtime
    return datetime.fromtimestamp(timestamp)


def extract_platform_and_title(folder_name: str) -> tuple[str, str]:
    """
    Извлекает платформу и заголовок из существующего имени папки
    
    Args:
        folder_name: Имя папки
        
    Returns:
        (platform, title)
    """
    # Паттерны для разных типов папок
    patterns = [
        # instagram_reels_username_CODE_title
        r'^(instagram)_(?:reels|post|auto)_[^_]+_[^_]+_(.+)$',
        # instagram_CODE_title
        r'^(instagram)_[A-Za-z0-9]+_(.+)$',
        # youtube_shorts_Author_CODE_title
        r'^(youtube)_shorts_[^_]+_[^_]+_(.+)$',
        # youtube_Author_CODE_title
        r'^(youtube)_[^_]+_[^_]+_(.+)$',
        # telegram_video_YYYYMMDD_HHMMSS
        r'^(telegram)_(?:video|note)_(.+?)(?:_\d{8}_\d{6})?$',
        # temp_YYYYMMDD_HHMMSS
        r'^(temp)_(.+)$',
    ]
    
    for pattern in patterns:
        match = re.match(pattern, folder_name)
        if match:
            platform = match.group(1)
            title = match.group(2)
            # Очищаем title от даты в конце (если есть)
            title = re.sub(r'_\d{8}_\d{6}$', '', title)
            return platform, title
    
    # Если не подошел ни один паттерн - берем всю строку после первого _
    parts = folder_name.split('_', 1)
    if len(parts) == 2:
        return parts[0], parts[1]
    
    return 'unknown', folder_name


def clean_title(title: str, max_length: int = 50) -> str:
    """
    Очищает заголовок для использования в имени папки
    
    Args:
        title: Исходный заголовок
        max_length: Максимальная длина
        
    Returns:
        Очищенный заголовок
    """
    # Убираем no_title
    if title == 'no_title':
        return 'untitled'
    
    # Ограничиваем длину
    if len(title) > max_length:
        title = title[:max_length]
    
    return title


def rename_folder(folder: Path, dry_run: bool = True) -> bool:
    """
    Переименовывает папку в соответствии с новым паттерном
    
    Args:
        folder: Путь к папке
        dry_run: Если True, только показывает что будет сделано
        
    Returns:
        True если переименование успешно (или было бы успешно)
    """
    old_name = folder.name
    
    # Пропускаем уже переименованные папки
    if re.match(r'^\d{4}-\d{2}-\d{2}_\d{2}-\d{2}_', old_name):
        print(f"⏭️  Пропуск (уже новый формат): {old_name}")
        return False
    
    # Получаем дату из медиафайлов
    creation_time = get_media_creation_time(folder)
    date_prefix = creation_time.strftime("%Y-%m-%d")
    time_prefix = creation_time.strftime("%H-%M")
    
    # Извлекаем платформу и заголовок
    platform, title = extract_platform_and_title(old_name)
    clean_title_str = clean_title(title)
    
    # Формируем новое имя
    new_name = f"{date_prefix}_{time_prefix}_{platform}_{clean_title_str}"
    new_path = folder.parent / new_name
    
    # Если папка с таким именем уже существует, добавляем суффикс
    counter = 1
    original_new_path = new_path
    while new_path.exists() and new_path != folder:
        new_path = folder.parent / f"{original_new_path.name}_{counter}"
        counter += 1
    
    if dry_run:
        print(f"📋 {old_name}")
        print(f"   → {new_path.name}")
        print(f"   📅 Дата: {creation_time.strftime('%Y-%m-%d %H:%M:%S')}")
        print()
    else:
        try:
            folder.rename(new_path)
            print(f"✅ {old_name}")
            print(f"   → {new_path.name}")
            print()
        except Exception as e:
            print(f"❌ Ошибка при переименовании {old_name}: {e}")
            return False
    
    return True


def main():
    """Основная функция"""
    downloads_dir = Path('downloads')
    
    if not downloads_dir.exists():
        print("❌ Папка downloads/ не найдена")
        return
    
    # Получаем все папки
    folders = [f for f in downloads_dir.iterdir() if f.is_dir()]
    
    if not folders:
        print("📭 Нет папок для переименования")
        return
    
    print("=" * 80)
    print("🔍 ПРЕДВАРИТЕЛЬНЫЙ ПРОСМОТР (Dry Run)")
    print("=" * 80)
    print()
    
    # Dry run - показываем что будет сделано
    renamed_count = 0
    for folder in sorted(folders):
        if rename_folder(folder, dry_run=True):
            renamed_count += 1
    
    print("=" * 80)
    print(f"📊 Будет переименовано: {renamed_count} из {len(folders)} папок")
    print("=" * 80)
    print()
    
    # Проверяем аргументы командной строки
    if len(sys.argv) > 1:
        arg = sys.argv[1].lower()
        if arg == '--dry-run':
            print("ℹ️  Режим --dry-run: переименование не выполнено")
            return
        elif arg == '--apply':
            print("⚠️  Режим --apply: переименование будет выполнено без подтверждения")
            response = 'yes'
        else:
            print(f"❌ Неизвестный аргумент: {sys.argv[1]}")
            print("Использование: python3 rename_folders.py [--dry-run|--apply]")
            return
    else:
        # Запрашиваем подтверждение
        response = input("Продолжить переименование? (yes/no): ").strip().lower()
    
    if response not in ['yes', 'y', 'да']:
        print("❌ Отменено пользователем")
        return
    
    print()
    print("=" * 80)
    print("🚀 ПЕРЕИМЕНОВАНИЕ")
    print("=" * 80)
    print()
    
    # Реальное переименование
    success_count = 0
    for folder in sorted(folders):
        if rename_folder(folder, dry_run=False):
            success_count += 1
    
    print("=" * 80)
    print(f"✅ Успешно переименовано: {success_count} папок")
    print("=" * 80)


if __name__ == "__main__":
    main()
