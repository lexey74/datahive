# ── Whisper Transcription Service ────────────────────────────────────────────
# Собирается на python:3.12-slim, без GPU.
# Для GPU-варианта замените базовый образ на nvidia/cuda:12.*-runtime-ubuntu22.04
# и поставьте WHISPER_DEVICE=cuda / WHISPER_COMPUTE_TYPE=float16.
# ─────────────────────────────────────────────────────────────────────────────

FROM python:3.12-slim

# Системные зависимости для faster-whisper (ffmpeg нужен для декодирования)
RUN apt-get update && apt-get install -y --no-install-recommends \
        ffmpeg \
        libsndfile1 \
        curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY main.py .

# ── Переменные окружения (можно переопределить в docker-compose) ──────────────
ENV WHISPER_MODEL=small \
    WHISPER_DEVICE=cpu \
    WHISPER_COMPUTE_TYPE=int8 \
    WHISPER_THREADS=4 \
    WHISPER_LANGUAGE=ru

# Порт сервиса
EXPOSE 9000

# Запуск Uvicorn
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "9000", "--workers", "1"]
