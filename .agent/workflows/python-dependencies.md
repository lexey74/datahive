---
description: Установка и управление Python-зависимостями в проекте
---

# Управление Python-зависимостями

## Установка пакетов
```bash
# Всегда через venv/bin/pip — НИКОГДА system pip
venv/bin/pip install -r requirements.txt
venv/bin/pip install newpackage
```

## Добавление нового пакета в проект
1. Установить: `venv/bin/pip install newpackage`
2. Добавить в `requirements.txt` с pin версии: `newpackage>=1.2.0`
3. Проверить импорт: `venv/bin/python3 -c "import newpackage; print('ok')"`

## Если pip не работает
1. Проверить шебанг: `head -1 venv/bin/pip`
   - Должен быть `#!/home/lexey/projects/datahive/venv/bin/python3`
   - Если путь старый (например `/secbrain/`) — пересоздать venv
2. Пересоздание: `rm -rf venv && python3 -m venv venv && venv/bin/pip install -r requirements.txt`

## Запуск Python-кода
```bash
# Использовать python3 (НЕ python) и ВСЕГДА через venv
venv/bin/python3 -m src.bot.main
venv/bin/python3 -m pytest tests/ -v
venv/bin/python3 -c "print('hello')"
```