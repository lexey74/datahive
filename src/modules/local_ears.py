"""
LocalEars - Транскрибация видео через faster-whisper (локально) или HTTP-сервис.

Режимы работы:
  1. Локальный (по умолчанию): faster-whisper запускается in-process.
  2. Удалённый (whisper_url задан): запросы к DataHive Whisper Service
     (services/whisper/main.py). Локальная модель не загружается.
"""
import logging
import urllib.request
import urllib.error
import json
import mimetypes
import uuid
from pathlib import Path
from typing import Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class TranscriptResult:
    """Результат транскрибации"""
    timed_transcript: str  # С таймкодами [MM:SS]
    full_text: str         # Чистый текст
    language: str = "ru"
    duration: float = 0.0


class LocalEars:
    """Локальная транскрибация аудио/видео (или HTTP к whisper-сервису)"""
    
    def __init__(
        self, 
        model_size: str = "small",
        device: str = "cpu", 
        num_threads: int = 16,
        compute_type: str = "int8",
        whisper_url: str = "",          # Если задан — используется HTTP-режим
        whisper_api_key: str = "",      # Bearer-токен для HTTP-режима
    ):
        """
        Инициализация Whisper модели
        
        Args:
            model_size: Размер модели (tiny, base, small, medium, large-v2, large-v3)
                       Рекомендации для русского:
                       - small: хороший баланс скорость/точность (244M параметров)
                       - medium: высокая точность (769M параметров)
                       - large-v3: максимальная точность (1550M параметров)
            device: Устройство (cpu, cuda)
            num_threads: Количество потоков для CPU (16 для максимальной производительности на 8-ядерном CPU)
            compute_type: Тип вычислений (int8, float16, float32)
                         int8 - оптимально для CPU: быстро + хорошая точность
                         float16 - только для GPU
                         float32 - самое медленное, максимальная точность
            whisper_url: Базовый URL whisper-сервиса (напр. http://whisper:9000).
                        Если пуст — используется локальная модель.
            whisper_api_key: Bearer-токен для авторизации в whisper-сервисе.
                            Если пуст — заголовок Authorization не отправляется.
        """
        self.model_size = model_size
        self.device = device
        self.num_threads = num_threads
        self.compute_type = compute_type
        self.whisper_url = whisper_url.rstrip("/")
        self.whisper_api_key = whisper_api_key
        self.model = None

        if self.whisper_url:
            logger.info(f"🌐 LocalEars: HTTP-режим → {self.whisper_url}")
        else:
            logger.info("💻 LocalEars: локальный режим (faster-whisper)")
    
    def load_model(self) -> None:
        """Ленивая загрузка модели"""
        if self.model is None:
            try:
                from faster_whisper import WhisperModel

                logger.info(f"🔄 Загрузка Whisper модели ({self.model_size}, {self.compute_type})...")
                self.model = WhisperModel(
                    self.model_size,
                    device=self.device,
                    compute_type=self.compute_type,
                    cpu_threads=self.num_threads
                )
                logger.info("✅ Модель Whisper готова")

            except ImportError:
                raise ImportError(
                    "Библиотека faster-whisper не установлена. "
                    "Установите: pip install faster-whisper"
                )
    
    def transcribe(self, media_path: Path) -> Optional[TranscriptResult]:
        """
        Транскрибация медиафайла.
        Автоматически выбирает HTTP-режим (если задан whisper_url) или локальный.
        
        Args:
            media_path: Путь к видео/аудио файлу
            
        Returns:
            TranscriptResult или None если файл не является аудио/видео
        """
        if not media_path or not media_path.exists():
            return None
        
        valid_extensions = ['.mp4', '.mov', '.avi', '.mkv', '.webm', '.mp3', '.m4a', '.wav', '.flac', '.ogg']
        if media_path.suffix.lower() not in valid_extensions:
            logger.info("ℹ️  Это изображение, транскрибация не требуется")
            return None

        if self.whisper_url:
            return self._transcribe_remote(media_path)
        return self._transcribe_local(media_path)

    # ------------------------------------------------------------------
    # HTTP-режим (whisper-сервис в контейнере)
    # ------------------------------------------------------------------

    def _transcribe_remote(self, media_path: Path) -> Optional[TranscriptResult]:
        """Отправляет файл на HTTP-сервис и возвращает TranscriptResult."""
        url = f"{self.whisper_url}/transcribe"
        logger.info(f"🌐 HTTP-транскрибация → {url}  ({media_path.name})")

        # Определяем MIME-тип
        mime_type, _ = mimetypes.guess_type(str(media_path))
        mime_type = mime_type or "application/octet-stream"

        # Формируем multipart/form-data вручную (без зависимостей типа requests)
        boundary = uuid.uuid4().hex
        with open(media_path, "rb") as fh:
            file_data = fh.read()

        body = (
            f"--{boundary}\r\n"
            f'Content-Disposition: form-data; name="file"; filename="{media_path.name}"\r\n'
            f"Content-Type: {mime_type}\r\n\r\n"
        ).encode() + file_data + f"\r\n--{boundary}--\r\n".encode()

        req = urllib.request.Request(
            url,
            data=body,
            method="POST",
            headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
        )
        if self.whisper_api_key:
            req.add_header("Authorization", f"Bearer {self.whisper_api_key}")

        try:
            with urllib.request.urlopen(req, timeout=600) as resp:
                payload = json.loads(resp.read().decode())
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode(errors="replace")
            raise RuntimeError(f"Whisper-сервис вернул {exc.code}: {detail}") from exc
        except urllib.error.URLError as exc:
            raise RuntimeError(f"Не удалось подключиться к whisper-сервису ({url}): {exc.reason}") from exc

        logger.info(
            f"✅ HTTP-транскрибация завершена "
            f"(lang={payload.get('language')}, duration={payload.get('duration', 0):.1f}s)"
        )
        return TranscriptResult(
            timed_transcript=payload["timed_transcript"],
            full_text=payload["full_text"],
            language=payload.get("language", "ru"),
            duration=float(payload.get("duration", 0.0)),
        )

    # ------------------------------------------------------------------
    # Локальный режим (faster-whisper in-process)
    # ------------------------------------------------------------------

    def _transcribe_local(self, media_path: Path) -> Optional[TranscriptResult]:
        """Транскрибация с использованием локальной Whisper модели."""
        self.load_model()

        logger.info(f"🎤 Транскрибация: {media_path.name}")
        
        # Запуск транскрибации с улучшенными параметрами
        segments, info = self.model.transcribe(
            str(media_path),
            language="ru",  # Можно изменить на None для auto-detect
            beam_size=10,   # Увеличено с 5 до 10 для лучшей точности
            best_of=5,      # Выбор лучшего из 5 вариантов
            temperature=0.0,  # Детерминированный вывод
            vad_filter=True,  # Фильтрация тишины
            vad_parameters=dict(
                threshold=0.5,
                min_speech_duration_ms=250,
                max_speech_duration_s=float('inf'),
                min_silence_duration_ms=2000,
                speech_pad_ms=400
            ),
            initial_prompt="Транскрипция видео на русском языке из Instagram. "
                          "Включает разговорную речь, сленг, упоминания технологий и социальных сетей."
        )
        
        timed_lines = []
        full_lines = []
        segment_count = 0
        
        for segment in segments:
            timestamp = self._format_timestamp(segment.start)
            text = segment.text.strip()
            
            timed_lines.append(f"[{timestamp}] {text}")
            full_lines.append(text)
            
            segment_count += 1
            if segment_count % 10 == 0:
                logger.debug(f"   📝 Обработано сегментов: {segment_count}")

        logger.info(f"✅ Транскрибация завершена ({segment_count} сегментов, {info.duration:.1f}s)")
        
        return TranscriptResult(
            timed_transcript="\n".join(timed_lines),
            full_text=" ".join(full_lines),
            language=info.language,
            duration=info.duration
        )
    
    def _format_timestamp(self, seconds: float) -> str:
        """
        Форматирование таймкода MM:SS
        
        Args:
            seconds: Время в секундах
            
        Returns:
            Строка вида "03:45"
        """
        minutes = int(seconds // 60)
        secs = int(seconds % 60)
        return f"{minutes:02d}:{secs:02d}"
