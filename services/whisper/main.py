"""
Whisper Transcription Service
FastAPI HTTP-сервер поверх faster-whisper.

Эндпоинты:
  POST /transcribe  — транскрибация аудио/видео (требует Bearer-токен)
  GET  /health      — проверка готовности (без авторизации — нужен для healthcheck)

Безопасность:
  Если задана переменная окружения API_KEY, все запросы к /transcribe
  должны содержать заголовок:  Authorization: Bearer <API_KEY>

Управление памятью:
  IDLE_TIMEOUT_MINUTES (default: 30) — через столько минут простоя
  модель выгружается из RAM. Следующий запрос перезагрузит её (~20-30 сек).
  Установите 0 чтобы отключить выгрузку.
  PRELOAD_MODEL=true (default: true) — загрузить модель при старте сервиса.
  Установите false для экономии RAM при старте (загрузка только по запросу).
"""
import asyncio
import gc
import logging
import os
import tempfile
import time
from pathlib import Path
from typing import Annotated

from fastapi import Depends, FastAPI, File, Form, HTTPException, UploadFile, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Конфигурация (переменные окружения)
# ---------------------------------------------------------------------------
MODEL_SIZE: str = os.getenv("WHISPER_MODEL", "small")
DEVICE: str = os.getenv("WHISPER_DEVICE", "cpu")
COMPUTE_TYPE: str = os.getenv("WHISPER_COMPUTE_TYPE", "int8")
NUM_THREADS: int = int(os.getenv("WHISPER_THREADS", "4"))
LANGUAGE: str | None = os.getenv("WHISPER_LANGUAGE", "ru") or None

# Безопасность: если пусто — авторизация отключена (только внутри Docker-сети)
API_KEY: str = os.getenv("API_KEY", "")

# Idle-выгрузка модели: 0 = никогда не выгружать
IDLE_TIMEOUT_MINUTES: int = int(os.getenv("IDLE_TIMEOUT_MINUTES", "30"))

# Предзагрузка модели при старте
PRELOAD_MODEL: bool = os.getenv("PRELOAD_MODEL", "true").lower() == "true"

# ---------------------------------------------------------------------------
# Состояние модели
# ---------------------------------------------------------------------------
_model = None
_last_request_time: float = 0.0
_model_lock = asyncio.Lock()          # защита от одновременной загрузки


def _load_model_sync():
    """Синхронная загрузка модели (вызывается в thread executor)."""
    from faster_whisper import WhisperModel

    logger.info(
        f"🔄 Загрузка Whisper ({MODEL_SIZE}, device={DEVICE}, "
        f"compute={COMPUTE_TYPE}, threads={NUM_THREADS})"
    )
    model = WhisperModel(
        MODEL_SIZE,
        device=DEVICE,
        compute_type=COMPUTE_TYPE,
        cpu_threads=NUM_THREADS,
    )
    logger.info("✅ Whisper модель готова")
    return model


async def get_model():
    """Ленивая потокобезопасная загрузка модели."""
    global _model, _last_request_time
    async with _model_lock:
        if _model is None:
            loop = asyncio.get_event_loop()
            _model = await loop.run_in_executor(None, _load_model_sync)
        _last_request_time = time.monotonic()
    return _model


def _unload_model():
    """Выгрузить модель из RAM."""
    global _model
    if _model is not None:
        logger.info("💤 Idle-таймаут: выгрузка Whisper модели из RAM")
        _model = None
        gc.collect()


# ---------------------------------------------------------------------------
# Фоновая задача: idle-watchdog
# ---------------------------------------------------------------------------
async def _idle_watchdog():
    """Каждые 60 секунд проверяет, не истёк ли idle-таймаут."""
    if IDLE_TIMEOUT_MINUTES <= 0:
        logger.info("⏱  Idle-watchdog отключён (IDLE_TIMEOUT_MINUTES=0)")
        return

    timeout_sec = IDLE_TIMEOUT_MINUTES * 60
    logger.info(f"⏱  Idle-watchdog запущен (таймаут {IDLE_TIMEOUT_MINUTES} мин)")

    while True:
        await asyncio.sleep(60)
        if _model is not None and _last_request_time > 0:
            idle_sec = time.monotonic() - _last_request_time
            if idle_sec >= timeout_sec:
                _unload_model()


# ---------------------------------------------------------------------------
# Безопасность: Bearer-токен
# ---------------------------------------------------------------------------
_bearer_scheme = HTTPBearer(auto_error=False)


def verify_api_key(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer_scheme)],
) -> None:
    """
    Проверяет Bearer-токен, если API_KEY задан.
    Если API_KEY пуст — пропускает всех (режим внутренней сети).
    """
    if not API_KEY:
        return  # авторизация отключена
    if credentials is None or credentials.credentials != API_KEY:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API key",
            headers={"WWW-Authenticate": "Bearer"},
        )


# ---------------------------------------------------------------------------
# Схемы
# ---------------------------------------------------------------------------
class TranscriptResponse(BaseModel):
    timed_transcript: str
    full_text: str
    language: str
    duration: float


class HealthResponse(BaseModel):
    status: str
    model: str
    device: str
    model_loaded: bool
    idle_timeout_minutes: int


# ---------------------------------------------------------------------------
# Приложение
# ---------------------------------------------------------------------------
app = FastAPI(
    title="DataHive Whisper Service",
    version="1.1.0",
    # Скрываем /docs за авторизацией не нужно — достаточно API_KEY на эндпоинтах
)


@app.on_event("startup")
async def _startup() -> None:
    """Прогрев + запуск idle-watchdog."""
    if PRELOAD_MODEL:
        await get_model()
    else:
        logger.info("💡 Предзагрузка отключена (PRELOAD_MODEL=false). Модель загрузится по первому запросу.")
    asyncio.create_task(_idle_watchdog())


# ---------------------------------------------------------------------------
# Эндпоинты
# ---------------------------------------------------------------------------

@app.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    """
    Проверка готовности сервиса.
    Не требует авторизации — нужен для Docker healthcheck и внешних мониторингов.
    """
    return HealthResponse(
        status="ok",
        model=MODEL_SIZE,
        device=DEVICE,
        model_loaded=_model is not None,
        idle_timeout_minutes=IDLE_TIMEOUT_MINUTES,
    )


@app.post(
    "/transcribe",
    response_model=TranscriptResponse,
    dependencies=[Depends(verify_api_key)],
)
async def transcribe(
    file: UploadFile = File(..., description="Аудио или видео файл"),
    language: str | None = Form(default=None, description="Язык (ru, en, …). None = авто"),
) -> TranscriptResponse:
    """
    Транскрибирует загруженный файл.

    Требует заголовок:  Authorization: Bearer <API_KEY>
    (только если задана переменная окружения API_KEY)
    """
    valid_extensions = {
        ".mp4", ".mov", ".avi", ".mkv", ".webm",
        ".mp3", ".m4a", ".wav", ".flac", ".ogg",
    }
    suffix = Path(file.filename or "media.mp4").suffix.lower()
    if suffix not in valid_extensions:
        raise HTTPException(
            status_code=422,
            detail=f"Неподдерживаемый формат: {suffix}. Ожидается: {sorted(valid_extensions)}",
        )

    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp_path = Path(tmp.name)
        tmp.write(await file.read())

    try:
        model = await get_model()
        lang = language or LANGUAGE

        logger.info(f"🎤 Транскрибация: {file.filename}  lang={lang or 'auto'}")

        # faster-whisper синхронный — запускаем в executor
        loop = asyncio.get_event_loop()
        segments, info = await loop.run_in_executor(
            None,
            lambda: model.transcribe(
                str(tmp_path),
                language=lang,
                beam_size=10,
                best_of=5,
                temperature=0.0,
                vad_filter=True,
                vad_parameters=dict(
                    threshold=0.5,
                    min_speech_duration_ms=250,
                    max_speech_duration_s=float("inf"),
                    min_silence_duration_ms=2000,
                    speech_pad_ms=400,
                ),
                initial_prompt=(
                    "Транскрипция видео на русском языке. "
                    "Включает разговорную речь, сленг, упоминания технологий."
                ),
            ),
        )

        timed_lines: list[str] = []
        full_lines: list[str] = []
        count = 0

        for seg in segments:
            minutes = int(seg.start // 60)
            secs = int(seg.start % 60)
            timed_lines.append(f"[{minutes:02d}:{secs:02d}] {seg.text.strip()}")
            full_lines.append(seg.text.strip())
            count += 1
            if count % 10 == 0:
                logger.debug(f"   📝 Сегментов: {count}")

        logger.info(
            f"✅ Готово: {count} сегментов, "
            f"lang={info.language}, duration={info.duration:.1f}s"
        )

        return TranscriptResponse(
            timed_transcript="\n".join(timed_lines),
            full_text=" ".join(full_lines),
            language=info.language,
            duration=info.duration,
        )

    except Exception as exc:
        logger.exception(f"❌ Ошибка транскрибации: {exc}")
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    finally:
        tmp_path.unlink(missing_ok=True)
