# 🎯 SecBrain - Quick Reference

Краткий справочник команд для работы с SecBrain.

## 🚀 Основные команды

### Активация окружения

```bash
cd /home/lexey/projects/secbrain
source venv/bin/activate
```

### Модуль 1: Загрузка контента

```bash
# Интерактивный режим (запрашивает URL)
python module1_download.py

# Или через старый интерфейс
python src/main.py

# Результат: downloads/source_ID_title/
# Файлы: media_XX.jpg/mp4, description.md
```

### Модуль 2: Транскрибация

```bash
# Все папки
python module2_transcribe.py

# Одна папка
python module2_transcribe.py --folder FOLDER_NAME

# Кастомная директория
python module2_transcribe.py --dir /path/to/dir

# Результат: transcript.md в каждой папке с видео
```

### Модуль 3: AI Анализ

```bash
# Все папки
python module3_analyze.py

# Одна папка
python module3_analyze.py --folder FOLDER_NAME

# Кастомная база тегов
python module3_analyze.py --tags custom_tags.json

# Результат: Note.md в формате Obsidian
```

## 📊 Типичные workflows

### YouTube видео с транскрибацией

```bash
# 1. Загрузка
python src/main.py
# Вводим: https://www.youtube.com/watch?v=VIDEO_ID

# 2. Транскрибация
python module2_transcribe.py

# 3. AI анализ
python module3_analyze.py
```

### Instagram пост (только фото)

```bash
# 1. Загрузка
python src/main.py
# Вводим: https://www.instagram.com/p/POST_ID/

# 2. AI анализ (транскрибация не нужна)
python module3_analyze.py
```

### Пакетная обработка

```bash
# Скачиваем несколько URL
python src/main.py  # URL 1
python src/main.py  # URL 2
python src/main.py  # URL 3

# Обрабатываем все за раз
python module2_transcribe.py  # Транскрибируем все видео
python module3_analyze.py     # Анализируем весь контент
```

## 🔍 Проверка статуса

### Список папок

```bash
# Все папки
ls -la downloads/

# Папки YouTube
ls -d downloads/youtube_*

# Папки Instagram
ls -d downloads/instagram_*
```

### Проверка файлов в папке

```bash
# Общий список
ls -la downloads/FOLDER_NAME/

# Проверка, есть ли транскрипция
ls downloads/FOLDER_NAME/transcript.md

# Проверка, есть ли Note
ls downloads/FOLDER_NAME/Note.md
```

### Чтение файлов

```bash
# Описание
cat downloads/FOLDER_NAME/description.md

# Транскрипция
cat downloads/FOLDER_NAME/transcript.md

# Note (AI анализ)
cat downloads/FOLDER_NAME/Note.md
```

## 🏷️ Работа с тегами

### Просмотр базы тегов

```bash
# Форматированный вывод
cat tags.json | python -m json.tool

# Количество тегов
cat tags.json | python -c "import sys, json; print(len(json.load(sys.stdin)))"
```

### Поиск по тегам

```bash
# Найти все Note.md с конкретным тегом
grep -r "#тег" downloads/*/Note.md
```

## 🛠️ Troubleshooting

### Проверка Whisper

```bash
# Тест Whisper
python -c "from faster_whisper import WhisperModel; m = WhisperModel('small'); print('OK')"
```

### Проверка Ollama

```bash
# Статус сервиса
curl http://localhost:11434/api/tags

# Тест модели
curl http://localhost:11434/api/generate -d '{
  "model": "qwen2.5:7b",
  "prompt": "Hello",
  "stream": false
}'
```

### Проверка зависимостей

```bash
# Список установленных пакетов
pip list | grep -E "yt-dlp|gallery-dl|faster-whisper|ollama"

# Версии
python -c "import yt_dlp; print(f'yt-dlp: {yt_dlp.version.__version__}')"
python -c "from faster_whisper import __version__; print(f'faster-whisper: {__version__}')"
```

## 📈 Мониторинг процессов

### Проверка запущенных процессов

```bash
# Whisper
ps aux | grep whisper

# Python процессы
ps aux | grep python

# Ollama
ps aux | grep ollama
```

### Использование ресурсов

```bash
# Память и CPU
htop

# Дисковое пространство
df -h
du -sh downloads/
```

## 🧹 Очистка

### Удаление обработанных папок

```bash
# Папки без Note.md (не завершены)
find downloads -type d -name "youtube_*" ! -exec test -e '{}/Note.md' \; -print

# Удалить папки без Note.md (осторожно!)
find downloads -type d -name "youtube_*" ! -exec test -e '{}/Note.md' \; -exec rm -rf {} +
```

### Пересоздание транскрипций

```bash
# Удалить все transcript.md
find downloads -name "transcript.md" -delete

# Заново транскрибировать
python module2_transcribe.py
```

### Пересоздание Note.md

```bash
# Удалить все Note.md
find downloads -name "Note.md" -delete

# Заново проанализировать
python module3_analyze.py
```

## 📦 Архивация

### Создание архива обработанных папок

```bash
# Архивируем папки с Note.md
tar czf secbrain_backup_$(date +%Y%m%d).tar.gz downloads/*/Note.md downloads/*/description.md downloads/*/transcript.md

# Проверка архива
tar tzf secbrain_backup_*.tar.gz
```

## 🔧 Настройки

### Изменение модели Whisper

Редактировать `src/modules/local_ears.py`:

```python
model_size = "base"   # Быстрее, хуже качество
model_size = "small"  # Баланс (по умолчанию)
model_size = "medium" # Медленнее, лучше качество
```

### Изменение модели Ollama

Редактировать `src/modules/local_brain.py`:

```python
model_name = "qwen2.5:7b"    # По умолчанию
model_name = "llama3.2:3b"   # Быстрее
model_name = "llama3.3:70b"  # Лучше качество
```

### Изменение директории загрузок

```bash
# При запуске модулей
python module2_transcribe.py --dir /custom/path
python module3_analyze.py --dir /custom/path
```

## 📚 Дополнительная документация

- **[MODULES.md](MODULES.md)** - Подробная документация модулей
- **[README.md](README.md)** - Общая информация о проекте
- **[SETUP.md](SETUP.md)** - Инструкции по установке

---

**Обновлено**: 2024-12-20
