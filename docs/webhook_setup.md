# Webhook setup для Data Hive Telegram Bot

Домен: **`datahive.inno.co`**

Схема:
- Бот слушает в webhook-режиме на `127.0.0.1:8080`
- MCP SSE сервер слушает на `127.0.0.1:8000`
- Nginx терминирует TLS на `datahive.inno.co` и проксирует оба сервиса

## 1) Переменные окружения
Добавить в `.env`:

```
WEBHOOK_MODE=true
WEBHOOK_LISTEN=127.0.0.1
WEBHOOK_PORT=8080
# Публичный URL (Telegram будет слать updates сюда)
WEBHOOK_PUBLIC_URL=https://datahive.inno.co
# Путь webhook (лучше держать непредсказуемым)
WEBHOOK_PATH=bot_abcd1234
# Секретный токен для проверки подлинности запросов от Telegram
WEBHOOK_SECRET_TOKEN=<random-secret-string>

# MCP
PUBLIC_MCP_URL=https://datahive.inno.co/mcp
MCP_HOST=127.0.0.1
MCP_PORT=8000
FASTMCP_ALLOW_HOSTS=datahive.inno.co,datahive.inno.co:*,localhost,localhost:*,127.0.0.1,127.0.0.1:*
FASTMCP_ALLOW_ORIGINS=https://datahive.inno.co,http://localhost:*,http://127.0.0.1:*
```

## 2) Получение SSL сертификата (Let's Encrypt)

```bash
sudo apt update
sudo apt install certbot python3-certbot-nginx -y
sudo certbot --nginx -d datahive.inno.co
```

Сертификаты будут в `/etc/letsencrypt/live/datahive.inno.co/`.

Для автопродления:
```bash
sudo systemctl enable --now certbot.timer
```

## 3) Nginx конфигурация

```bash
sudo cp scripts/nginx_bot.conf /etc/nginx/sites-available/datahive
sudo ln -s /etc/nginx/sites-available/datahive /etc/nginx/sites-enabled/datahive
sudo nginx -t
sudo systemctl reload nginx
```

> `proxy_pass` для webhook → `http://127.0.0.1:8080`  
> `proxy_pass` для MCP SSE → `http://127.0.0.1:8000` (с отключённой буферизацией)

## 4) systemd сервис

```bash
sudo cp scripts/datahive-bot.service /etc/systemd/system/datahive-bot.service
sudo systemctl daemon-reload
sudo systemctl enable --now datahive-bot.service
sudo journalctl -u datahive-bot -f
```

## 5) Проверка webhook

После старта бот вызовет `setWebhook` автоматически. Проверить:

```bash
curl -s "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/getWebhookInfo" | jq .
```

Ожидаемый результат: поле `url` = `https://datahive.inno.co/<WEBHOOK_PATH>`, `pending_update_count` = 0.

## Troubleshooting

**409 Conflict** — уже есть активный webhook или polling:
```bash
curl -s -X POST "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/deleteWebhook"
```

**502 Bad Gateway** — бот не запущен или порт не совпадает с `WEBHOOK_PORT`.

**SSE не работает** — убедиться, что в nginx для `/mcp` включено `proxy_buffering off`.
