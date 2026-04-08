---
trigger: always_on
---

# VPS Python & venv — Критические правила

Этот проект работает на VPS (Debian/Ubuntu). Ниже перечислены конкретные ошибки,
которые уже происходили, и правила для их предотвращения.

## 1. Python-команда: ВСЕГДА `python3`, не `python`
На Debian/Ubuntu команда `python` по умолчанию **не существует**.
```bash
# ✅ Правильно
python3 --version
python3 -m venv venv
venv/bin/python3 script.py

# ❌ Ошибка — вызовет "command not found"
python --version
python -m venv venv
```

## 2. Активация venv — НИКОГДА не `source activate`
В этом проекте используй **полные пути** к бинарникам внутри `venv/`:
```bash
# ✅ Правильно — абсолютные/относительные пути к venv бинарникам
venv/bin/python3 -m src.bot.main
venv/bin/pip install -r requirements.txt
/home/lexey/projects/datahive/venv/bin/python3 script.py

# ❌ Ненадёжно — зависит от текущего shell-состояния
source venv/bin/activate && python3 script.py
```

## 3. После перемещения/переименования проекта — ПЕРЕСОЗДАТЬ venv
**Инцидент:** Проект переименован из `/secbrain` в `/datahive`, но venv оставлен старый.
Шебанг `pip` указывал на `#!/home/lexey/projects/secbrain/venv/bin/python3` — несуществующий путь.

**Правило:** Если путь проекта изменился, venv ВСЕГДА нужно пересоздать:
```bash
rm -rf venv
python3 -m venv venv
venv/bin/pip install -r requirements.txt
```

**Диагностика:** Если pip/python из venv не работает — первым делом проверь шебанг:
```bash
head -1 venv/bin/pip
# Должно быть: #!/home/lexey/projects/datahive/venv/bin/python3
```

## 4. Установка пакетов — ВСЕГДА через venv/bin/pip
```bash
# ✅ Правильно
venv/bin/pip install somepackage
venv/bin/pip install -r requirements.txt

# ❌ Ошибка — установит в системный Python
pip install somepackage
pip3 install somepackage
sudo pip install somepackage
```

## 5. Запуск бота и модулей — только через venv
```bash
# ✅ Правильно — запуск бота
venv/bin/python3 -m src.bot.main

# ✅ Правильно — запуск тестов
venv/bin/python3 -m pytest tests/ -v

# ❌ Ошибка — system Python без зависимостей
python3 -m src.bot.main
pytest tests/
```

## 6. Reverse Proxy: Caddy (НЕ nginx)
На этом VPS порты 80/443 заняты **Caddy**, который обслуживает несколько доменов (`*.inno.co`).
```bash
# ✅ Правильно — редактировать Caddyfile
sudo nano /etc/caddy/Caddyfile
sudo systemctl reload caddy

# ❌ Ошибка — nginx НЕ может занять порты 80/443
sudo systemctl start nginx  # CONFLICT с Caddy
```

**Caddy auto-TLS:** Caddy автоматически получает и обновляет сертификаты Let's Encrypt.
Не нужно вручную вызывать certbot.

## 7. Текущие рабочие пути
```
Проект:     /home/lexey/projects/datahive/
Venv:       /home/lexey/projects/datahive/venv/
Python:     /home/lexey/projects/datahive/venv/bin/python3  (→ Python 3.12.3)
Pip:        /home/lexey/projects/datahive/venv/bin/pip
Bot entry:  python3 -m src.bot.main
Logs:       /home/lexey/projects/datahive/logs/
Bot state:  /home/lexey/projects/datahive/bot_state/
Домен:      datahive.inno.co (→ 38.242.141.28)
```
