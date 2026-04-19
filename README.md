# 🧠 Data Hive - Content to Knowledge Base

**Privacy-First** модульная система для автоматического сохранения контента из **Instagram** и **YouTube** в структурированные заметки для Obsidian.

## ✨ Особенности

- 🔒 **100% Privacy**: Только локальные нейросети (llama.cpp, Whisper)
- 📦 **Модульная архитектура**: 3 независимых модуля (Download → Transcribe → Analyze)
- 🎯 **Multi-Source**: Instagram (Posts, Reels) + YouTube (Videos, Shorts)
- 🏷️ **Smart Tagging**: Автоматическое создание и управление тегами
- 📝 **Obsidian-Ready**: Markdown с frontmatter, теги, ссылки на медиа
- 🤖 **AI-Powered**: Локальный AI анализ, суммаризация, категоризация
- ⚡ **Manual Control**: Каждый модуль запускается вручную по необходимости


## 🗄 Структура хранения

Подробное описание организации файлов и папок Data Hive см. в [`structure.md`](structure.md).

## 📋 Требования (Pre-requisites)

Перед использованием установите:

### 1. Системные зависимости

- **Python 3.10+**
- **FFmpeg** ([скачать](https://ffmpeg.org/download.html))

  ```bash
  # macOS
  brew install ffmpeg
  
  # Ubuntu/Debian
  sudo apt install ffmpeg
  ```

### 2. llama.cpp server

Нужен OpenAI-совместимый HTTP endpoint llama.cpp. По умолчанию проект ожидает сервер на `http://localhost:8080`.

Пример запуска:

```bash
./server \
  -m /path/to/model.gguf \
  --host 0.0.0.0 \
  --port 8080 \
  --jinja \
  --ctx-size 8192
```


### 3. Instagram Cookies

Для работы `yt-dlp` нужны куки браузера:

1. Установите расширение [Get cookies.txt LOCALLY](https://chrome.google.com/webstore/detail/get-cookiestxt-locally/cclelndahbckbenkjhflpdbgdldlbecc)
2. Войдите в Instagram
3. Экспортируйте cookies → сохраните как `cookies.txt` в корень проекта

### 4. Instagrapi Session (опционально)

Для получения комментариев:

```python
# Одноразовая настройка
from instagrapi import Client
cl = Client()
cl.login("username", "password")
cl.dump_settings("session.json")
```

## 🚀 Установка

```bash
# 1. Клонируйте репозиторий
git clone <repo-url>
cd datahive

# 2. Создайте виртуальное окружение
python3 -m venv venv
source venv/bin/activate  # macOS/Linux
# venv\Scripts\activate   # Windows

# 3. Установите runtime и dev-зависимости
pip install -r requirements.txt -r requirements-dev.txt
```

## Developer Checks

Единые команды для локальной проверки:

```bash
make format
make lint
make typecheck
make test
make check
```

Если `make` не используется:

```bash
venv/bin/python3 -m ruff format src tests module2_transcribe.py module3_analyze.py scripts
venv/bin/python3 -m ruff check src tests module2_transcribe.py module3_analyze.py scripts
venv/bin/python3 -m mypy --config-file mypy.ini
venv/bin/python3 -m pytest tests -q
```

На GitHub те же проверки выполняются автоматически в workflow `.github/workflows/ci.yml`.

## 📖 Использование

### 3-модульный workflow

#### Модуль 1: Загрузка контента

```bash
python module1_download.py
```

Программа запросит URL (Instagram или YouTube) и скачает:

- Папку `downloads/source_ID_title/`
- Медиа файлы (видео/фото)
- `description.md` с описанием

#### Модуль 2: Транскрибация (вручную)

```bash
# Обработать все папки с видео
python module2_transcribe.py

# Или одну конкретную папку
python module2_transcribe.py --folder youtube_VIDEO_ID_title
```

Результат: `transcript.md` с таймингами для каждого видео

#### Модуль 3: AI Анализ (вручную)

```bash
# Обработать все папки
python module3_analyze.py

# Или одну конкретную папку
python module3_analyze.py --folder youtube_VIDEO_ID_title
```

Результат: `Note.md` в формате Obsidian с тегами и саммари

### Быстрый пример

```bash
# 1. Скачиваем YouTube видео
python module1_download.py
# Вводим URL: https://www.youtube.com/watch?v=dQw4w9WgXcQ

# 2. Транскрибируем (если есть видео/аудио)
python module2_transcribe.py

# 3. AI анализ
python module3_analyze.py
```

📚 **Подробная документация**: [MODULES.md](MODULES.md)

## 📂 Структура вывода (Asset Bundle)

```
SecondBrain_Inbox/
└── 2024-01-25_username_ai_powered_note/
    ├── media.mp4          # Оригинальное видео
    └── Note.md            # Markdown заметка
```

### Пример Note.md

```markdown
---
created: 2024-01-25
author: tech_guru
url: https://instagram.com/p/ABC123
category: Tutorial
tags:
  - ai
  - coding
  - productivity
  - inbox
---

# tech_guru: AI-Powered Note Taking

![[media.mp4]]

## 🧠 AI Summary
- Рассказывает о новом инструменте для заметок
- [02:15] Демонстрация функции автоматической транскрибации
- Сравнение с Notion и Obsidian

## 💬 Valuable Insights (Comments)
> **user1**: Попробовал, работает лучше чем Otter.ai
> **user2**: На русском языке точность 90%+

---
<details>
<summary>📂 Raw Data</summary>

### Caption
Check out this amazing AI tool! #ai #productivity

### Transcript
[00:00] Привет всем...
[00:45] Сегодня покажу как...
</details>
```

## ⚙️ Конфигурация

Файл `config.json` создаётся автоматически при первом запуске:

```json
{
  "output_dir": "SecondBrain_Inbox",
  "whisper_model": "base",
  "llama_cpp_model": "llama3.2",
  "device": "cpu",
  "max_comments": 50,
  "max_tags": 15
}
```

## 🏗️ Архитектура

```
src/
├── main.py                    # CLI точка входа
├── config.py                  # Управление конфигурацией
└── modules/
    ├── tag_manager.py         # База тегов (known_tags.json)
    ├── hybrid_grabber.py      # Парсинг (yt-dlp + instagrapi)
    ├── local_ears.py          # Транскрибация (faster-whisper)
    ├── local_brain.py         # AI анализ (llama.cpp)
    └── pipeline.py            # Оркестрация процесса
```

## 🔧 Troubleshooting

### Ошибка: "Ollama не отвечает"

```bash
# Проверьте, что Ollama запущен
ollama serve

# Проверьте модель
ollama list
```

### Ошибка: "yt-dlp не может скачать"

- Обновите cookies.txt (они устаревают)
- Убедитесь, что пост публичный или вы подписаны

### Ошибка: "faster-whisper Out of Memory"

Используйте меньшую модель в `config.json`:

```json
"whisper_model": "tiny"  // вместо "base"
```

## 🧪 Testing

Unit tests are available using pytest:

```bash
# Run all tests
pytest tests/

# With coverage report
pytest tests/ --cov=src/modules --cov-report=term-missing

# Verbose output
pytest tests/ -v

# Type checking (mypy)
mypy --config-file mypy.ini
```

Текущий охват mypy: весь проект (`src`, `scripts`, `tests`) и legacy shim-модули совместимости.

**Test Results**: ✅ 23 tests passing | Coverage: 76-86% on core modules (TagManager, LocalEars)

See [tests/README.md](tests/README.md) for detailed test documentation.

## 📝 TODO

- [x] Unit тесты для core модулей (TagManager, LocalEars, LocalBrain, HybridGrabber)
- [ ] Завершить реализацию `instagrapi` для комментариев
- [ ] Добавить прогресс-бар для транскрибации
- [ ] Поддержка карусели (множественные фото)
- [ ] Export в Notion API
- [ ] Batch processing (список URL из файла)

## 📄 Лицензия

MIT

## 🙏 Благодарности

- [yt-dlp](https://github.com/yt-dlp/yt-dlp)
- [instagrapi](https://github.com/subzeroid/instagrapi)
- [faster-whisper](https://github.com/guillaumekln/faster-whisper)
- [Ollama](https://ollama.ai)
