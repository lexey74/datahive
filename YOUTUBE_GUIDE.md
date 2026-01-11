# 🎬 YouTube Grabber - Руководство

## Обзор

YouTube Grabber - модуль для загрузки видео, аудио, метаданных и комментариев с YouTube.

## Возможности

✅ **Метаданные:**
- Название, автор, описание
- Длительность, дата загрузки
- Просмотры, лайки, комментарии
- Теги и категории

✅ **Контент:**
- Видео (разное качество)
- Аудио (для транскрибации)
- Thumbnail (превью)

✅ **Комментарии:**
- Текст, автор
- Лайки, таймстампы
- Настраиваемое количество

## Установка

```bash
pip install yt-dlp
```

## Быстрый старт

### 1. Только метаданные (быстро)

```python
from modules.youtube_grabber import YouTubeGrabber

grabber = YouTubeGrabber()
metadata = grabber.get_metadata("https://www.youtube.com/watch?v=VIDEO_ID")

print(f"Название: {metadata['title']}")
print(f"Автор: {metadata['uploader']}")
print(f"Просмотры: {metadata['view_count']:,}")
```

### 2. Полная загрузка

```python
grabber = YouTubeGrabber()
content = grabber.grab(
    "https://www.youtube.com/watch?v=VIDEO_ID",
    download_video=True,
    download_audio=True
)

print(f"Видео: {content.video_path}")
print(f"Аудио: {content.audio_path}")
print(f"Комментарии: {len(content.comments)}")
```

### 3. Только аудио (для транскрибации)

```python
grabber = YouTubeGrabber()
content = grabber.grab(
    url,
    download_video=False,  # Без видео
    download_audio=True    # Только аудио
)

# Используем с Whisper
from modules.local_ears import LocalEars
ears = LocalEars(model_size="small")
transcript = ears.transcribe(content.audio_path)
```

## Примеры использования

### Анализ видео

```python
grabber = YouTubeGrabber()

# Метаданные
metadata = grabber.get_metadata(url)

print(f"""
Видео: {metadata['title']}
Автор: {metadata['uploader']}
Длительность: {metadata['duration']} сек
Просмотры: {metadata['view_count']:,}
Лайки: {metadata['like_count']:,}
""")

# Комментарии
comments = grabber.get_comments(url, max_comments=50)
for comment in comments[:5]:
    print(f"{comment['author']}: {comment['text'][:50]}...")
```

### Загрузка плейлиста

```python
playlist_urls = [
    "https://www.youtube.com/watch?v=VIDEO1",
    "https://www.youtube.com/watch?v=VIDEO2",
    # ...
]

grabber = YouTubeGrabber()

for url in playlist_urls:
    content = grabber.grab(url, download_video=False, download_audio=True)
    print(f"✅ {content.title}")
```

### Интеграция с SecBrain

```python
# В download.py
from modules.youtube_grabber import YouTubeGrabber
from modules.local_ears import LocalEars

grabber = YouTubeGrabber()
ears = LocalEars(model_size="small")

# Загружаем
content = grabber.grab(url, download_video=False, download_audio=True)

# Транскрибируем
transcript = ears.transcribe(content.audio_path)

# Сохраняем
folder = create_folder(content.title, content.author)
save_youtube_data(folder, content, transcript)
```

## YouTubeContent структура

```python
@dataclass
class YouTubeContent:
    video_id: str           # Уникальный ID
    title: str              # Название
    author: str             # Автор канала
    description: str        # Описание
    duration: int           # Длительность (сек)
    upload_date: str        # Дата загрузки (YYYYMMDD)
    view_count: int         # Просмотры
    like_count: int         # Лайки
    comment_count: int      # Количество комментариев
    tags: List[str]         # Теги
    categories: List[str]   # Категории
    
    # Пути к файлам
    video_path: Optional[Path]
    audio_path: Optional[Path]
    thumbnail_path: Optional[Path]
    
    # Комментарии
    comments: List[Dict]    # [{'author': str, 'text': str, 'likes': int}, ...]
```

## Параметры качества видео

```python
# Лучшее качество
grabber.download_video(url, quality='best')

# Конкретное разрешение
grabber.download_video(url, quality='720p')
grabber.download_video(url, quality='1080p')

# Худшее качество (экономия места)
grabber.download_video(url, quality='worst')
```

## Обработка ошибок

```python
try:
    content = grabber.grab(url)
    if content:
        print(f"✅ Загружено: {content.title}")
    else:
        print("❌ Ошибка загрузки")
except Exception as e:
    print(f"❌ Исключение: {e}")
```

## Ограничения и рекомендации

### YouTube API Limits
- yt-dlp может быть заблокирован при частых запросах
- Рекомендуется пауза 2-5 секунд между загрузками

### Размер файлов
- Видео 1080p: ~100-500 MB за 10 минут
- Аудио MP3: ~5-10 MB за 10 минут
- Для транскрибации достаточно аудио

### Timeout
- Метаданные: 30 сек
- Аудио: 5 минут
- Видео: 10 минут
- Комментарии: 60 сек

## Troubleshooting

### yt-dlp не найден
```bash
pip install yt-dlp
```

### Ошибка загрузки видео
- Проверьте URL
- Убедитесь, что видео публичное
- Попробуйте обновить yt-dlp: `pip install --upgrade yt-dlp`

### Нет комментариев
- Комментарии могут быть отключены автором
- Проверьте, что видео не в ограниченном режиме

### Медленная загрузка
- Используйте только аудио (`download_video=False`)
- Снизьте качество: `quality='worst'`
- Проверьте интернет соединение

## Тестирование

```bash
# Быстрый тест (только метаданные)
python test_youtube.py
# Нажмите Enter для тестового видео
# Введите 'n' для пропуска загрузки

# Полный тест (с загрузкой)
python test_youtube.py
# Введите URL
# Введите 'y' для полной загрузки
```

## Интеграция с другими модулями

### LocalEars (Whisper транскрибация)
```python
content = grabber.grab(url, download_video=False, download_audio=True)
transcript = ears.transcribe(content.audio_path)
```

### LocalBrain (AI анализ)
```python
analysis = brain.analyze(
    caption=content.description,
    transcript=transcript.full_text,
    comments=[c['text'] for c in content.comments],
    author=content.author
)
```

### TagManager (теги)
```python
# YouTube теги как база
existing_tags = content.tags
new_tags = tag_manager.extract_tags(content.description, existing_tags)
```

## Сравнение с Instagram

| Функция | Instagram (Gallery-dl) | YouTube (yt-dlp) |
|---------|----------------------|------------------|
| Метаданные | ✅ | ✅ |
| Видео | ✅ | ✅ |
| Аудио | ❌ | ✅ |
| Комментарии | ⚠️ Ограничено | ✅ |
| Превью | ✅ | ✅ |
| Скорость | ⚡⚡⚡ | ⚡⚡ |

## Roadmap

- [ ] Поддержка плейлистов (batch download)
- [ ] Субтитры (если доступны)
- [ ] Chapters (таймкоды)
- [ ] Live стримы (архивы)
- [ ] Shorts (поддержка коротких видео)

## Лицензия и Legal

⚠️ **Важно:**
- Соблюдайте Terms of Service YouTube
- Используйте только для личных целей
- Не распространяйте скачанный контент
- Уважайте авторские права

## Примеры реальных кейсов

### 1. Анализ образовательного видео
```python
# Загружаем лекцию
content = grabber.grab(lecture_url, download_video=False, download_audio=True)

# Транскрибируем
transcript = ears.transcribe(content.audio_path)

# Анализируем
summary = brain.analyze(
    caption=content.title,
    transcript=transcript.full_text,
    author=content.author
)

# Сохраняем в Obsidian
save_note(content.title, summary, transcript)
```

### 2. Архив конференции
```python
conference_videos = get_conference_playlist()

for url in conference_videos:
    content = grabber.grab(url, download_video=False, download_audio=True)
    transcript = ears.transcribe(content.audio_path)
    archive_to_obsidian(content, transcript)
    time.sleep(5)  # Пауза между запросами
```

### 3. Анализ комментариев
```python
content = grabber.grab(url, download_video=False, download_audio=False)

# Топ комментарии
top_comments = sorted(content.comments, key=lambda x: x['likes'], reverse=True)[:10]

for i, comment in enumerate(top_comments, 1):
    print(f"{i}. {comment['author']}: {comment['text'][:50]}...")
    print(f"   ❤️  {comment['likes']:,} likes\n")
```

## Ресурсы

- yt-dlp GitHub: https://github.com/yt-dlp/yt-dlp
- YouTube API: https://developers.google.com/youtube
- Supported sites: https://github.com/yt-dlp/yt-dlp/blob/master/supportedsites.md

## FAQ

**Q: Можно ли скачивать плейлисты?**
A: Да, передайте URL плейлиста. yt-dlp автоматически обработает все видео.

**Q: Работает ли с другими сайтами?**
A: yt-dlp поддерживает 1800+ сайтов, но YouTubeGrabber оптимизирован для YouTube.

**Q: Как ускорить загрузку?**
A: Используйте только аудио (`download_video=False`) - в 10-50 раз быстрее.

**Q: Есть ли лимиты?**
A: YouTube может ограничить частые запросы. Добавляйте паузы между загрузками.

**Q: Можно ли получить субтитры?**
A: Да, через yt-dlp напрямую. Будет добавлено в будущих версиях.
