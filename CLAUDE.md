# Data Hive — Claude Project Rules

## Контекст проекта
Telegram-бот "Data Hive" — контент-ингестор.
**Пайплайн:** Download (Social Media) → Transcribe (Whisper) → Analyze (Ollama) → Save (Obsidian Markdown).

## Среда выполнения
- **OS:** Debian/Ubuntu VPS
- **VPS IP:** `38.242.141.28`
- **Домен:** `datahive.inno.co` (SSL через Caddy auto-TLS)
- **Reverse Proxy:** Caddy (НЕ nginx! Порты 80/443 заняты Caddy)
- **Python:** 3.12+ (`python3`, НЕ `python`)
- **Venv:** `venv/` в корне проекта
- Все сервисы слушают на `0.0.0.0`, не `127.0.0.1`

### Критические правила VPS-окружения
1. **Команда:** Всегда `python3`, не `python` (на Debian `python` не существует)
2. **Venv бинарники:** Использовать `venv/bin/python3`, `venv/bin/pip` — полные пути, не `source activate`
3. **После переименования/перемещения проекта:** Обязательно пересоздать venv (`rm -rf venv && python3 -m venv venv`)
4. **pip шебанг:** Если venv не работает — проверить `head -1 venv/bin/pip` (должен содержать текущий путь проекта)
5. **Caddy, не nginx:** SSL-сертификаты через Caddy auto-TLS, конфиг в `/etc/caddy/Caddyfile`

## Архитектура проекта

```
src/
  bot/              # aiogram 3.x: routers, middlewares, services, states
  modules/          # Бизнес-логика: downloaders, brain, ears, rag, pipeline
  config.py         # Конфигурация (pydantic-settings)
  main.py           # Точка входа
tests/              # pytest тесты (НЕ root)
```

## Технический стек (строго)
- **Framework:** aiogram 3.x (Routers, FSM, Middleware)
- **Event Loop:** uvloop (обязательно на Linux)
- **JSON:** orjson
- **Validation:** Pydantic v2 (для CallbackData и моделей данных)
- **Downloaders:** yt-dlp, gallery-dl, youtube-comment-downloader
- **Browser:** playwright (async_playwright API)
- **ASR:** faster-whisper (CUDA → CPU/int8 fallback)
- **AI:** Ollama локально (`llama3.2` для саммари, `qwen2.5:7b` для сложной логики)
- **Logging:** structlog (JSON-логи) или стандартный logging — никаких `print()`
- **Testing:** pytest + pytest-mock + pytest-cov

## Правила написания кода

### Конкурентность (КРИТИЧНО)
- НИКОГДА не запускай `yt-dlp`, `gallery-dl`, `faster-whisper`, `playwright` в основном event loop синхронно
- Используй `asyncio.get_event_loop().run_in_executor(None, blocking_func)` для блокирующих операций
- Playwright — только через `async_playwright`, всегда закрывай контекст

### Структура и паттерны
- **Factory:** `ContentRouter` выбирает обработчик по URL
- **Strategy:** отдельный класс `DownloaderStrategy` для каждой платформы
- **Data Transfer:** только dataclasses/Pydantic-модели между слоями (не `dict`)
- **DI:** конфигурация (`Config`) передаётся явно через конструктор
- Архитектура: 1 фича = 1 роутер (`routers/transcription.py`, `routers/admin.py`)

### Безопасность
- Никаких хардкода токенов — только `os.getenv` или `pydantic-settings`
- Секреты в `.env` (никогда не коммитить)

### Обработка ошибок
- Ошибки на этапе Download не останавливают бота — уведомить пользователя, залогировать traceback
- Отдельная обработка ошибок истечения Cookie для Instagram
- Глобальный `ErrorRouter` для перехвата необработанных исключений

### PID-файлы
- При запуске фоновых воркеров писать PID в `logs/`, управлять процессами через `psutil`

## Формат вывода в Obsidian

### Структура папок
```
downloads/{YYYY-MM-DD}_{HH-MM}_{Platform}_{slug-title}/
  description.md
  transcript.md
  Knowledge.md
  media.*
```
Медиафайлы ТОЛЬКО внутри папок, никогда в корне `downloads/`.

### YAML Frontmatter (обязателен для всех .md)
```yaml
---
title: "..."
author: "..."           # если известен
date: YYYY-MM-DD
tags: [tag1, tag2]
source: instagram       # instagram | youtube | telegram
type: description       # description | transcript | knowledge
processed: true         # только для Knowledge.md
---
```

### Obsidian-стиль
- Ключевые термины в вики-ссылках: `[[Python]]`, `[[Ollama]]`
- Иерархические теги: `#project/datahive`, `#status/draft`
- AI-саммари в читаемом формате, не сырой dict/JSON

## Тестирование
- Все тесты в `tests/` (не в корне проекта)
- Мокать сетевые вызовы: yt-dlp, Ollama, gallery-dl
- Никаких реальных сетевых запросов в unit-тестах
- `archive/old_tests/` — устаревшие интеграционные тесты, не использовать

## Стиль общения
- Ответы и комментарии в коде — **на русском**
- Строгая типизация везде (Type Hints)
- Не спрашивай разрешения создавать файлы, если это логичное развитие архитектуры
- Сразу к делу: без вступлений и извинений
