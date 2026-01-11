#!/usr/bin/env python3
"""
Модуль 2: Транскрибация видео и аудио

Проходит по папкам с контентом и создает транскрибации для видео/аудио файлов,
у которых еще нет файла транскрипции.
"""
from pathlib import Path
from typing import List, Optional
import sys

# Добавляем src в путь
sys.path.insert(0, str(Path(__file__).parent))

from src.modules.local_ears import LocalEars


class TranscriptionProcessor:
    """
    Процессор транскрибации
    
    Сканирует папки, находит видео/аудио без транскрипции,
    создает транскрипцию с таймингами и сохраняет в Markdown.
    """
    
    def __init__(self, content_dir: Path = Path("downloads")):
        """
        Args:
            content_dir: Директория с папками контента
        """
        self.content_dir = Path(content_dir)
        self.ears = LocalEars()
        
        # Поддерживаемые форматы
        self.video_extensions = ['.mp4', '.mov', '.avi', '.mkv', '.webm']
        self.audio_extensions = ['.mp3', '.m4a', '.wav', '.flac', '.ogg']
        self.media_extensions = self.video_extensions + self.audio_extensions
    
    def find_content_folders(self) -> List[Path]:
        """
        Находит все папки с контентом
        
        Returns:
            Список путей к папкам
        """
        if not self.content_dir.exists():
            print(f"❌ Директория не найдена: {self.content_dir}")
            return []
        
        folders = []
        for item in self.content_dir.iterdir():
            if item.is_dir() and (
                item.name.startswith('instagram_') or 
                item.name.startswith('youtube_')
            ):
                folders.append(item)
        
        return sorted(folders)
    
    def find_media_files(self, folder: Path) -> List[Path]:
        """
        Находит медиа файлы в папке
        
        Args:
            folder: Папка для поиска
            
        Returns:
            Список путей к медиа файлам
        """
        media_files = []
        for file in folder.iterdir():
            if file.is_file() and file.suffix.lower() in self.media_extensions:
                media_files.append(file)
        return sorted(media_files)
    
    def has_transcript(self, folder: Path) -> bool:
        """
        Проверяет, есть ли уже транскрипция
        
        Args:
            folder: Папка для проверки
            
        Returns:
            True если transcript.md существует
        """
        transcript_file = folder / "transcript.md"
        return transcript_file.exists()
    
    def transcribe_file(self, media_file: Path, output_folder: Path) -> Optional[Path]:
        """
        Транскрибирует один медиа файл
        
        Args:
            media_file: Путь к медиа файлу
            output_folder: Папка для сохранения транскрипции
            
        Returns:
            Путь к созданному transcript.md или None при ошибке
        """
        print(f"\n🎤 Транскрибация: {media_file.name}")
        print(f"   Размер: {media_file.stat().st_size / 1024 / 1024:.1f} MB")
        
        try:
            # Запускаем транскрибацию
            print("   🔄 Запуск Whisper...")
            transcript = self.ears.transcribe(str(media_file))
            
            if not transcript:
                print("   ❌ Whisper не вернул результат")
                return None
            
            # Создаем transcript.md
            transcript_file = output_folder / "transcript.md"
            
            # Формируем Markdown с таймингами
            markdown = f"# Транскрипция\n\n"
            markdown += f"**Файл**: `{media_file.name}`\n\n"
            markdown += f"**Модель**: `{self.ears.model_size}`\n\n"
            markdown += "---\n\n"
            
            # Добавляем сегменты с таймингами
            for segment in transcript:
                start_time = self._format_timestamp(segment['start'])
                end_time = self._format_timestamp(segment['end'])
                text = segment['text'].strip()
                
                markdown += f"**[{start_time} - {end_time}]**\n\n"
                markdown += f"{text}\n\n"
            
            # Сохраняем
            transcript_file.write_text(markdown, encoding='utf-8')
            
            print(f"   ✅ Сохранено: transcript.md")
            return transcript_file
            
        except Exception as e:
            print(f"   ❌ Ошибка транскрибации: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def _format_timestamp(self, seconds: float) -> str:
        """
        Форматирует таймстемп из секунд в MM:SS
        
        Args:
            seconds: Время в секундах
            
        Returns:
            Строка формата MM:SS или HH:MM:SS
        """
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        
        if hours > 0:
            return f"{hours:02d}:{minutes:02d}:{secs:02d}"
        else:
            return f"{minutes:02d}:{secs:02d}"
    
    def process_folder(self, folder: Path) -> dict:
        """
        Обрабатывает одну папку
        
        Args:
            folder: Папка для обработки
            
        Returns:
            Статистика обработки
        """
        stats = {
            'folder': folder.name,
            'already_has_transcript': False,
            'no_media': False,
            'success': False,
            'error': None
        }
        
        # Проверяем, есть ли уже транскрипция
        if self.has_transcript(folder):
            print(f"⏭️  Пропуск: {folder.name} (transcript.md существует)")
            stats['already_has_transcript'] = True
            return stats
        
        # Ищем медиа файлы
        media_files = self.find_media_files(folder)
        
        if not media_files:
            print(f"⏭️  Пропуск: {folder.name} (нет медиа файлов)")
            stats['no_media'] = True
            return stats
        
        # Берем первый медиа файл (обычно один)
        media_file = media_files[0]
        
        # Транскрибируем
        transcript_file = self.transcribe_file(media_file, folder)
        
        if transcript_file:
            stats['success'] = True
        else:
            stats['error'] = "Ошибка транскрибации"
        
        return stats
    
    def process_all(self) -> dict:
        """
        Обрабатывает все папки
        
        Returns:
            Общая статистика
        """
        print("\n" + "="*70)
        print("🎤 МОДУЛЬ 2: ТРАНСКРИБАЦИЯ")
        print("="*70)
        print(f"📁 Директория: {self.content_dir}")
        print(f"🤖 Модель Whisper: {self.ears.model_size}")
        
        # Находим папки
        folders = self.find_content_folders()
        
        if not folders:
            print("\n⚠️  Папки с контентом не найдены")
            return {'total_folders': 0}
        
        print(f"📊 Найдено папок: {len(folders)}")
        
        # Общая статистика
        total_stats = {
            'total_folders': len(folders),
            'already_has_transcript': 0,
            'no_media': 0,
            'successfully_transcribed': 0,
            'errors': 0
        }
        
        # Обрабатываем каждую папку
        for i, folder in enumerate(folders, 1):
            print(f"\n{'='*70}")
            print(f"📂 [{i}/{len(folders)}] {folder.name}")
            print(f"{'='*70}")
            
            stats = self.process_folder(folder)
            
            if stats['already_has_transcript']:
                total_stats['already_has_transcript'] += 1
            elif stats['no_media']:
                total_stats['no_media'] += 1
            elif stats['success']:
                total_stats['successfully_transcribed'] += 1
            else:
                total_stats['errors'] += 1
        
        # Итоговая статистика
        print("\n" + "="*70)
        print("📊 ИТОГОВАЯ СТАТИСТИКА")
        print("="*70)
        print(f"Всего папок: {total_stats['total_folders']}")
        print(f"Уже есть транскрипция: {total_stats['already_has_transcript']}")
        print(f"Нет медиа файлов: {total_stats['no_media']}")
        print(f"Успешно транскрибировано: {total_stats['successfully_transcribed']}")
        if total_stats['errors'] > 0:
            print(f"Ошибок: {total_stats['errors']}")
        print("="*70)
        
        return total_stats


def main():
    """Точка входа"""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Модуль 2: Транскрибация видео и аудио"
    )
    parser.add_argument(
        '--dir',
        type=Path,
        default=Path('downloads'),
        help='Директория с контентом (по умолчанию: downloads)'
    )
    parser.add_argument(
        '--folder',
        type=str,
        help='Обработать только одну папку (имя папки)'
    )
    
    args = parser.parse_args()
    
    processor = TranscriptionProcessor(content_dir=args.dir)
    
    if args.folder:
        # Обработка одной папки
        folder_path = args.dir / args.folder
        if not folder_path.exists():
            print(f"❌ Папка не найдена: {folder_path}")
            sys.exit(1)
        
        print(f"\n🎯 Обработка одной папки: {args.folder}")
        stats = processor.process_folder(folder_path)
        
        print("\n" + "="*70)
        print("📊 СТАТИСТИКА")
        print("="*70)
        if stats['already_has_transcript']:
            print("⏭️  Транскрипция уже существует")
        elif stats['no_media']:
            print("⏭️  Нет медиа файлов")
        elif stats['success']:
            print("✅ Успешно транскрибировано")
        else:
            print(f"❌ Ошибка: {stats['error']}")
    else:
        # Обработка всех папок
        processor.process_all()


if __name__ == "__main__":
    main()
