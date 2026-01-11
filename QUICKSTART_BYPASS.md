# 🚀 Быстрый старт: Обход блокировок YouTube

## Проблема
YouTube блокирует cookies через 10-15 минут использования.

## Решение за 5 минут

### Вариант А: Множественные Cookies (Простой)

#### 1. Экспорт cookies с локального компьютера

**На вашем ЛОКАЛЬНОМ компьютере** (не на VPS!):

```bash
# Установите yt-dlp (если ещё нет)
pip install yt-dlp

# Аккаунт 1 (Chrome)
yt-dlp --cookies-from-browser chrome --cookies youtube_cookies_1.txt \
       --skip-download "https://youtube.com/watch?v=test"

# Аккаунт 2 (используйте другой профиль Chrome или Firefox)
# Переключите аккаунт Google в браузере, затем:
yt-dlp --cookies-from-browser chrome --cookies youtube_cookies_2.txt \
       --skip-download "https://youtube.com/watch?v=test"

# Аккаунт 3 (если есть)
yt-dlp --cookies-from-browser firefox --cookies youtube_cookies_3.txt \
       --skip-download "https://youtube.com/watch?v=test"
```

**Альтернатива (через расширение):**
1. Установите [Get cookies.txt LOCALLY](https://chrome.google.com/webstore/detail/get-cookiestxt-locally/cclelndahbckbenkjhflpdbgdldlbecc)
2. Откройте youtube.com → кликните расширение → Export
3. Повторите для других Google аккаунтов

#### 2. Загрузка на сервер

```bash
# Загрузите все 3 файла
scp youtube_cookies_*.txt lexey@38.242.141.28:/home/lexey/projects/secbrain/
```

#### 3. Добавление в систему

```bash
cd /home/lexey/projects/secbrain

# Добавляем каждый cookies
./cookie_manager.py add --file youtube_cookies_1.txt --name account1
./cookie_manager.py add --file youtube_cookies_2.txt --name account2
./cookie_manager.py add --file youtube_cookies_3.txt --name account3

# Проверяем
./cookie_manager.py list
```

#### 4. Тестирование

```bash
# Запускаем тесты
python test_youtube_bypass.py

# Должны увидеть ротацию между cookies
```

#### 5. Использование в коде

Обновите ваш `content_downloader.py`:

```python
# Добавьте в начало файла
from cookie_manager import CookieManager

# В классе ContentDownloader, в методе __init__:
def __init__(self, output_dir: Path = Path('downloads')):
    self.output_dir = output_dir
    self.output_dir.mkdir(exist_ok=True, parents=True)
    
    # Загружаем все cookies для ротации
    cookie_mgr = CookieManager()
    self.cookies_files = cookie_mgr.get_all_cookies()
    
    if self.cookies_files:
        print(f"✅ Загружено {len(self.cookies_files)} cookies для ротации")
    else:
        print("⚠️  Cookies не найдены, добавьте через cookie_manager.py")

# В методе download_youtube, передайте список cookies:
from src.modules.youtube_grabber_advanced import AdvancedYouTubeGrabber

grabber = AdvancedYouTubeGrabber(
    output_dir=temp_dir,
    cookies_files=self.cookies_files,  # <-- Ротация cookies
    min_delay=3.0,   # Задержка между запросами
    max_delay=6.0
)
```

**Готово!** Теперь система автоматически чередует cookies.

### Вариант Б: Прокси (Для массовых загрузок)

Если планируете скачивать >50 видео в день, добавьте прокси.

#### 1. Получите прокси

**Платные (рекомендуется):**
- [Bright Data](https://brightdata.com) - $500/100GB
- [Smartproxy](https://smartproxy.com) - $75/8GB

**Бесплатные (ненадёжные):**
- [free-proxy-list.net](https://free-proxy-list.net/)

#### 2. Добавьте в proxies.txt

```bash
nano proxies.txt

# Добавьте строки:
http://proxy1.example.com:8080
socks5://user:pass@proxy2.example.com:1080
```

#### 3. Используйте в коде

```python
grabber = AdvancedYouTubeGrabber(
    output_dir=temp_dir,
    cookies_files=self.cookies_files,
    proxies_file=Path('proxies.txt'),  # <-- Добавить прокси
    min_delay=3.0,
    max_delay=6.0
)
```

## 📊 Мониторинг

### Проверка cookies

```bash
# Статистика всех cookies
./cookie_manager.py stats

# Увидите:
# - Сколько раз использован каждый
# - Success rate
# - Заблокирован или нет
```

### Разблокировка после обновления

```bash
# После загрузки свежих cookies
./cookie_manager.py unblock
```

### Удаление старых

```bash
# Удалить cookies старше 7 дней
./cookie_manager.py clean --days 7
```

## ⚡ Best Practices

1. **Минимум 3 аккаунта Google** для ротации
2. **Обновляйте cookies каждые 5-7 дней** (даже если работают)
3. **Задержки 3-6 секунд** между запросами
4. **Прокси для массовых загрузок** (50+ видео/день)
5. **Мониторьте статистику** раз в день

## 🆘 Что делать если...

### Все cookies блокируются быстро

```bash
# 1. Увеличьте задержки в коде:
min_delay=10.0, max_delay=15.0

# 2. Добавьте больше аккаунтов (5-7 штук)

# 3. Используйте прокси
```

### Нет 3 аккаунтов Google

```bash
# Создайте новые аккаунты:
# - gmail.com → Create account
# - Используйте только для YouTube scraping
# - НЕ логинтесь с них на VPS!
```

### Success rate < 50%

```bash
# Обновите все cookies:
# 1. Экспортируйте свежие с локального ПК
# 2. Загрузите на сервер
# 3. Разблокируйте:
./cookie_manager.py unblock
```

## 📖 Полная документация

См. [BYPASS_YOUTUBE_BLOCKS.md](./BYPASS_YOUTUBE_BLOCKS.md) для детальной информации.

## 🎯 Ожидаемый результат

**До:**
- ❌ Cookies работают 10-15 минут
- ❌ Постоянные блокировки
- ❌ Success rate ~20%

**После:**
- ✅ Cookies работают дни/недели
- ✅ Редкие блокировки
- ✅ Success rate >80%
