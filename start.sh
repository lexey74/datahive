#!/bin/bash
# Скрипт запуска Data Hive (Bot)

# Определение директории скрипта
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$DIR"

# 1. Проверка и активация окружения
if [ ! -d "venv" ]; then
    echo "⚠️  Virtual environment not found. Creating..."
    python3 -m venv venv
    source venv/bin/activate
    echo "📦 Installing dependencies from requirements.txt..."
    pip install -r requirements.txt
else
    source venv/bin/activate
fi

# 2. Загрузка переменных (если есть) или дефолты
# Простой парсинг .env для скрипта (или полагаемся, что python сам загрузит)
# Но для uvicorn нам нужны аргументы здесь
if [ -f .env ]; then
    export $(grep -v '^#' .env | xargs)
fi

    export $(grep -v '^#' .env | xargs)
fi

# 4. Запуск Бота
echo "🤖 Starting Data Hive Bot..."
python telegram_bot.py
