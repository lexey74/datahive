#!/usr/bin/env python3
"""
Скрипт для загрузки и обработки YouTube видео
Использует: YouTubeGrabber -> LocalEars (Whisper) -> LocalBrain (AI)
"""

import sys
from pathlib import Path

# Добавляем src в PYTHONPATH
sys.path.insert(0, str(Path(__file__).parent / 'src'))

from modules.youtube_grabber import YouTubeGrabber
from modules.local_ears import LocalEars
from modules.local_brain import LocalBrain
from modules.tag_manager import TagManager
from config import Config


def main():
    # URL видео
    url = "https://www.youtube.com/watch?v=cQjqRz4HH9M&t=1481s"
    
    print("=" * 70)
    print("📺 ЗАГРУЗКА И ОБРАБОТКА YOUTUBE ВИДЕО")
    print("=" * 70)
    print(f"\n🔗 URL: {url}\n")
    
    # Инициализация
    config = Config()
    output_dir = Path('temp/youtube_test')
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # 1. Загрузка видео (только аудио для экономии времени)
    print("\n" + "=" * 70)
    print("📥 ШАГ 1: ЗАГРУЗКА АУДИО И МЕТАДАННЫХ")
    print("=" * 70)
    
    grabber = YouTubeGrabber(output_dir=output_dir)
    
    try:
        # Сначала получаем метаданные
        print("\n📊 Получение метаданных...")
        metadata = grabber.get_metadata(url)
        
        if metadata:
            print(f"\n✅ Видео найдено:")
            print(f"   📝 Название: {metadata.get('title', 'N/A')}")
            print(f"   👤 Автор: {metadata.get('uploader', 'N/A')}")
            print(f"   ⏱️  Длительность: {metadata.get('duration', 0)} сек")
            print(f"   👁️  Просмотры: {metadata.get('view_count', 0):,}")
            print(f"   👍 Лайки: {metadata.get('like_count', 0):,}")
        
        # Загружаем только аудио (видео не нужно для транскрибации)
        print("\n🎵 Загрузка аудио...")
        content = grabber.grab(
            url=url,
            download_video=False,  # Не загружаем видео - экономим время и место
            download_audio=True,
            max_comments=50
        )
        
        if not content or not content.audio_path:
            print("\n❌ ОШИБКА: Не удалось загрузить аудио")
            return 1
        
        print(f"\n✅ Аудио сохранено: {content.audio_path}")
        print(f"   📁 Размер: {content.audio_path.stat().st_size / 1024 / 1024:.1f} MB")
        
    except Exception as e:
        print(f"\n❌ ОШИБКА при загрузке: {e}")
        return 1
    
    # 2. Транскрибация аудио
    print("\n" + "=" * 70)
    print("🎤 ШАГ 2: ТРАНСКРИБАЦИЯ АУДИО (WHISPER)")
    print("=" * 70)
    
    ears = LocalEars()
    
    try:
        print("\n⏳ Транскрибация может занять несколько минут...")
        print(f"   Модель: {ears.model_size}")
        print(f"   Устройство: {ears.device}")
        
        transcript = ears.transcribe(str(content.audio_path))
        
        if transcript:
            print(f"\n✅ Транскрипция готова!")
            print(f"   📝 Длина текста: {len(transcript)} символов")
            print(f"   📄 Первые 200 символов:")
            print(f"   {transcript[:200]}...")
            
            # Сохраняем транскрипт
            transcript_file = output_dir / content.video_id / "transcript.txt"
            transcript_file.write_text(transcript, encoding='utf-8')
            print(f"\n   💾 Сохранено: {transcript_file}")
        else:
            print("\n⚠️  Транскрипция пустая")
            transcript = ""
            
    except Exception as e:
        print(f"\n❌ ОШИБКА при транскрибации: {e}")
        transcript = ""
    
    # 3. AI анализ
    print("\n" + "=" * 70)
    print("🧠 ШАГ 3: AI АНАЛИЗ КОНТЕНТА")
    print("=" * 70)
    
    brain = LocalBrain(
        model=config.ollama_model,
        num_ctx=config.ollama_num_ctx,
        num_thread=config.ollama_num_thread,
        timeout=config.ollama_timeout
    )
    
    tag_manager = TagManager()
    
    try:
        print(f"\n⏳ Анализ через {config.ollama_model}...")
        
        # Подготавливаем данные для анализа
        caption = f"{content.title}\n\n{content.description}"
        comments_text = "\n\n".join([
            f"{c['author']}: {c['text']}" 
            for c in (content.comments or [])[:20]  # Первые 20 комментариев
        ])
        
        # Анализируем
        result = brain.analyze(
            caption=caption,
            transcript=transcript,
            comments=comments_text,
            existing_tags=content.tags or []
        )
        
        if result:
            print(f"\n✅ Анализ завершён!")
            print(f"\n📋 РЕЗУЛЬТАТ:")
            print(f"   🏷️  Теги: {', '.join(result.get('tags', []))}")
            print(f"   📝 Заголовок: {result.get('title', 'N/A')}")
            print(f"\n   📄 Краткое содержание:")
            summary = result.get('summary', 'N/A')
            print(f"   {summary[:300]}...")
            
            # Сохраняем результат
            note_file = output_dir / content.video_id / "Knowledge.md"
            
            note_content = f"""---
title: {result.get('title', content.title)}
tags: {', '.join(result.get('tags', []))}
source: youtube
url: {url}
author: {content.author}
date: {content.upload_date or 'unknown'}
duration: {content.duration}
views: {content.views}
---

# {result.get('title', content.title)}

## 📊 Метаданные

- **Автор**: {content.author}
- **Длительность**: {content.duration} сек
- **Просмотры**: {content.views:,}
- **Лайки**: {content.likes:,}
- **URL**: {url}

## 📝 Краткое содержание

{result.get('summary', 'N/A')}

## 🎯 Основные идеи

{result.get('main_ideas', 'N/A')}

## 🔑 Ключевые моменты

{result.get('key_points', 'N/A')}

## 🏷️ Теги

{', '.join([f'#{tag}' for tag in result.get('tags', [])])}

---

## 📄 Полная транскрипция

{transcript}

---

## 💬 Комментарии ({len(content.comments or [])})

{comments_text}
"""
            
            note_file.write_text(note_content, encoding='utf-8')
            print(f"\n   💾 Knowledge.md сохранён: {note_file}")
            
        else:
            print("\n⚠️  AI анализ не вернул результат")
            
    except Exception as e:
        print(f"\n❌ ОШИБКА при AI анализе: {e}")
    
    print("\n" + "=" * 70)
    print("✅ ОБРАБОТКА ЗАВЕРШЕНА")
    print("=" * 70)
    print(f"\n📁 Результаты сохранены в: {output_dir / content.video_id}")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
