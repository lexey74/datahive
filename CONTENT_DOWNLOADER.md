# Content Downloader - Универсальный загрузчик контента

## Описание

`ContentDownloader` - это модуль первого уровня в системе SecBrain, который отвечает за **сохранение первоначального контента** из различных источников.

## Возможности

### 1. Автоматическое определение источника

- ✅ **Instagram** (`instagram.com`, `instagr.am`)
- ✅ **YouTube** (`youtube.com`, `youtu.be`)

### 2. Определение типа контента

#### Instagram:
- **POST** - обычный пост с изображением
- **CAROUSEL** - карусель (несколько изображений)
- **REELS** - короткое видео

#### YouTube:
- **VIDEO** - обычное видео
- **SHORT** - YouTube Shorts (аналог reels)

### 3. Организация файлов

Создает структурированные папки:
```
downloads/
├── instagram_ABC123_Название_поста/
│   ├── media_01.jpg
│   ├── media_02.jpg
│   └── description.txt
├── youtube_dQw4w9WgXcQ_Название_видео/
│   ├── video.mp4
│   └── description.txt
└── ...
```

## Использование

### Базовый пример

```python
from pathlib import Path
from src.modules.content_downloader import ContentDownloader

# Создаем загрузчик
downloader = ContentDownloader(output_dir=Path("downloads"))

# Загружаем контент (автоматически определяет тип)
result = downloader.download("https://www.instagram.com/p/ABC123/")

# Результат содержит всю информацию
print(f"Источник: {result.source}")
print(f"Тип: {result.content_type}")
print(f"Папка: {result.folder_path}")
print(f"Медиа файлы: {result.media_files}")
```

### Instagram примеры

```python
# Обычный пост
result = downloader.download("https://www.instagram.com/p/ABC123/")
# Результат:
#   - source: INSTAGRAM
#   - content_type: POST или CAROUSEL (определяется автоматически)
#   - media_files: [media_01.jpg, ...]
#   - description_file: description.txt

# Reels
result = downloader.download("https://www.instagram.com/reel/XYZ456/")
# Результат:
#   - source: INSTAGRAM
#   - content_type: REELS
#   - media_files: [video.mp4]
#   - description_file: description.txt
```

### YouTube примеры

```python
# Обычное видео
result = downloader.download("https://www.youtube.com/watch?v=dQw4w9WgXcQ")
# Результат:
#   - source: YOUTUBE
#   - content_type: VIDEO
#   - media_files: [video.mp4]
#   - description_file: description.txt

# YouTube Shorts
result = downloader.download("https://www.youtube.com/shorts/abc123")
# Результат:
#   - source: YOUTUBE
#   - content_type: SHORT
#   - media_files: [video.mp4]
#   - description_file: description.txt

# Только метаданные (без видео файла)
result = downloader.download(
    "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
    download_video=False
)
```

## API Reference

### ContentDownloader

#### `__init__(output_dir: Path = Path("downloads"))`
Инициализирует загрузчик

**Параметры:**
- `output_dir` - базовая директория для сохранения

#### `download(url: str, download_video: bool = True) -> Optional[ContentInfo]`
Универсальная загрузка контента

**Параметры:**
- `url` - URL контента
- `download_video` - скачивать ли видео (для YouTube)

**Возвращает:**
- `ContentInfo` или `None` при ошибке

#### `detect_source(url: str) -> ContentSource`
Определяет источник по URL

#### `detect_instagram_type(url: str) -> InstagramContentType`
Определяет тип Instagram контента

#### `detect_youtube_type(url: str) -> YouTubeContentType`
Определяет тип YouTube контента

### ContentInfo

Dataclass с информацией о загруженном контенте:

```python
@dataclass
class ContentInfo:
    source: ContentSource              # INSTAGRAM или YOUTUBE
    content_type: str                  # Тип контента
    url: str                           # Исходный URL
    content_id: str                    # ID контента
    title: Optional[str]               # Название
    description: Optional[str]         # Описание
    folder_path: Optional[Path]        # Путь к папке проекта
    media_files: list                  # Список медиа файлов
    description_file: Optional[Path]   # Путь к description.txt
```

## Структура папок

### Формат названия папки

```
{источник}_{ID}_{название}
```

Примеры:
- `instagram_ABC123_Мой_первый_пост`
- `youtube_dQw4w9WgXcQ_Never_Gonna_Give_You_Up`

### Содержимое папки

#### Instagram POST:
```
instagram_ABC123_Название/
├── media_01.jpg          # Изображение
└── description.txt       # Текст поста
```

#### Instagram CAROUSEL:
```
instagram_ABC123_Название/
├── media_01.jpg          # Первое изображение
├── media_02.jpg          # Второе изображение
├── media_03.jpg          # Третье изображение
└── description.txt       # Текст поста
```

#### Instagram REELS:
```
instagram_XYZ456_Название/
├── media_01.mp4          # Видео
└── description.txt       # Описание reels
```

#### YouTube VIDEO:
```
youtube_dQw4w9WgXcQ_Название/
├── video.mp4             # Видео файл
└── description.txt       # Описание видео
```

## Интеграция с другими модулями

```python
from pathlib import Path
from src.modules.content_downloader import ContentDownloader
from src.modules.local_ears import LocalEars
from src.modules.local_brain import LocalBrain

# 1. Загружаем контент
downloader = ContentDownloader(output_dir=Path("downloads"))
content = downloader.download("https://www.youtube.com/watch?v=VIDEO_ID")

# 2. Транскрибируем (если есть видео)
if content.media_files:
    ears = LocalEars()
    transcript = ears.transcribe(content.media_files[0])
    
    # Сохраняем транскрипт
    transcript_file = content.folder_path / "transcript.txt"
    transcript_file.write_text(transcript, encoding='utf-8')

# 3. AI анализ
brain = LocalBrain()
analysis = brain.analyze(
    caption=content.description,
    transcript=transcript
)

# Сохраняем результат
note_file = content.folder_path / "Note.md"
note_file.write_text(analysis, encoding='utf-8')
```

## Тестирование

```bash
# Запустить тесты
python test_content_downloader.py

# Тесты проверяют:
# ✅ Определение источника (Instagram/YouTube)
# ✅ Определение типа контента
# ✅ Извлечение ID из URL
# ✅ Создание безопасных названий папок
```

## Особенности

### Безопасность имен файлов

Автоматически удаляет небезопасные символы:
- `< > : " / \ | ? *` → убираются
- Множественные пробелы → `_`
- Длинные названия → обрезаются до 100 символов

### YouTube Cookies

Для защищенных YouTube видео:
1. Экспортируйте cookies из браузера
2. Сохраните как `youtube_cookies.txt`
3. `ContentDownloader` автоматически их использует

### Карусели Instagram

Тип CAROUSEL определяется автоматически после загрузки:
- Если > 1 изображения → CAROUSEL
- Если 1 изображение → POST

## Troubleshooting

### Ошибка: "Не удалось извлечь ID"

Проверьте формат URL:
- Instagram: `/p/ID/` или `/reel/ID/`
- YouTube: `watch?v=ID` или `/shorts/ID`

### Ошибка: "Sign in to confirm you're not a bot" (YouTube)

Нужны cookies:
1. Экспортируйте из браузера
2. Сохраните как `youtube_cookies.txt`
3. См. `YOUTUBE_COOKIES_GUIDE.md`

### Папка не создается

Проверьте права доступа к `output_dir`

## Roadmap

Планируемые улучшения:
- [ ] Поддержка TikTok
- [ ] Поддержка Twitter/X
- [ ] Batch загрузка (несколько URL)
- [ ] Прогресс бар для больших файлов
- [ ] Возобновление прерванных загрузок
- [ ] Поддержка плейлистов YouTube

## См. также

- `HybridGrabber` - Instagram загрузчик
- `YouTubeGrabber` - YouTube загрузчик
- `LocalEars` - транскрибация аудио
- `LocalBrain` - AI анализ контента
