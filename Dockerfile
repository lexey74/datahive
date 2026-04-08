# ── DataHive Bot ─────────────────────────────────────────────────────────────
FROM python:3.12-slim

# Системные зависимости (yt-dlp, gallery-dl, playwright нужны ffmpeg / chromium)
RUN apt-get update && apt-get install -y --no-install-recommends \
        ffmpeg \
        curl \
        git \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Зависимости Python (без faster-whisper — он в отдельном контейнере)
COPY requirements.txt .
# Сначала ставим torch CPU-only (~220 MB вместо ~2 GB с CUDA)
RUN pip install --no-cache-dir \
        torch==2.4.1 --index-url https://download.pytorch.org/whl/cpu
RUN pip install --no-cache-dir -r requirements.txt

# Playwright браузеры
RUN playwright install chromium --with-deps

COPY . .

CMD ["python", "-m", "src.bot.main"]
