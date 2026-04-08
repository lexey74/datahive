# 🎨 Оформление Telegram Бота Data Hive

## 📋 Чек-лист настройки через @BotFather

### 1. Название бота
```
/setname

Новое имя:
🧠 Data Hive — Personal Knowledge Manager
```

### 2. Описание (показывается при первом запуске)
```
/setdescription

Новое описание:
👋 Привет! Я Data Hive — твой личный помощник для сохранения контента.

Я умею:
📥 Скачивать посты из Instagram и YouTube
🎤 Транскрибировать аудио и видео
🤖 Анализировать контент с помощью AI
📝 Сохранять всё в Obsidian (Markdown)

🔒 100% приватность: все нейросети работают локально!

Просто отправь мне ссылку или медиафайл, а я сделаю остальное.
```

### 3. Короткое описание (показывается в профиле)
```
/setabouttext

Новый текст:
🧠 Personal Knowledge Manager с локальным AI. Сохраняет контент из Instagram/YouTube в Obsidian. Privacy-first.
```

### 4. Аватар
```
/setuserpic

[Загрузи изображение 512x512px]
```

**Идеи для аватара:**
- 🧠 Мозг с замком (Knowledge + Privacy)
- 📚 Архив документов с AI элементом
- ☁️ Облако из слов/тегов с лампочкой

**Где создать:**
- [Canva](https://www.canva.com/) - бесплатные шаблоны
- [Figma](https://www.figma.com/) - профессиональный дизайн
- [Flaticon](https://www.flaticon.com/) - готовые иконки

**AI Промпт для генерации:**
```
Create a minimalist bot avatar for "Data Hive" - a knowledge management assistant.
Style: Modern, flat design, tech-inspired
Elements: Brain or cloud with documents, lock symbol (privacy), AI elements
Colors: Blue and purple gradient
Size: 512x512px, transparent background
Must be recognizable at small sizes (100x100px)
```

### 5. Команды бота
```
/setcommands

Список команд:
start - 🚀 Запустить бота и увидеть приветствие
help - ❓ Помощь по использованию
status - 📊 Статус системы (AI, Whisper, Ollama)
settings - ⚙️ Настройки бота
cancel - ❌ Отменить текущую операцию
```

## 🎨 Цветовая схема

Рекомендуемые цвета для аватара и брендинга:

- **Основной:** `#5B67CA` (синий - технологии, доверие)
- **Акцент:** `#9B59B6` (фиолетовый - AI, креативность)
- **Фон:** `#F8F9FA` (светло-серый)
- **Текст:** `#2C3E50` (темно-серый)

## ✨ Дополнительные улучшения

### Inline кнопки
Добавить быстрые действия в сообщения:
```python
keyboard = [
    [InlineKeyboardButton("📥 Скачать", callback_data='download')],
    [InlineKeyboardButton("🎤 Транскрибировать", callback_data='transcribe')],
    [InlineKeyboardButton("🤖 AI Анализ", callback_data='analyze')]
]
```

### Статусы обработки
Использовать эмодзи для индикации прогресса:
- ⏳ Скачивание...
- 🎤 Транскрипция...
- 🤖 AI анализ...
- ✅ Готово!

### Форматирование сообщений
- **Жирный** для заголовков
- `Моноширинный` для кода/путей
- • Буллеты для списков
- ━━━ Разделители для секций

## 📝 Проверка

После настройки проверь:
- [ ] Аватар отображается корректно
- [ ] Название выглядит профессионально
- [ ] Описание понятное и привлекательное
- [ ] Команды работают и описаны
- [ ] /start показывает красивое приветствие
- [ ] Эмодзи отображаются правильно
