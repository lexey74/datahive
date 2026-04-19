from pathlib import Path
from typing import Optional
from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class BotConfig(BaseSettings):
    """Configuration for Data Hive Bot"""

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    # Telegram
    telegram_bot_token: str = Field(..., alias="TELEGRAM_BOT_TOKEN")
    admin_id: int = Field(..., alias="ADMIN_ID")

    # Paths
    users_dir: Path = Field(Path("users"), alias="USERS_DIR")
    downloads_dir: Path = Field(Path("downloads"), alias="DOWNLOADS_DIR")
    user_name: str = Field("admin", alias="USER_NAME")

    # Whisper (HTTP-сервис whisper.inno.co)
    whisper_url: str = Field("", alias="WHISPER_URL")
    whisper_api_key: str = Field("", alias="WHISPER_API_KEY")

    # Llama.cpp (с обратной совместимостью по старым env)
    ollama_url: str = Field(
        "http://localhost:8080",
        validation_alias=AliasChoices("LLAMA_CPP_URL", "OLLAMA_HOST"),
    )
    ollama_model: str = Field(
        "llama3.2",
        validation_alias=AliasChoices("LLAMA_CPP_MODEL", "OLLAMA_MODEL"),
    )
    ollama_model_complex: str = Field(
        "qwen3:4b",
        validation_alias=AliasChoices(
            "LLAMA_CPP_MODEL_COMPLEX", "OLLAMA_MODEL_COMPLEX"
        ),
    )

    # Webhook
    webhook_mode: bool = Field(False, alias="WEBHOOK_MODE")
    webhook_listen: str = Field("127.0.0.1", alias="WEBHOOK_LISTEN")
    webhook_port: int = Field(8080, alias="WEBHOOK_PORT")
    webhook_public_url: str = Field("", alias="WEBHOOK_PUBLIC_URL")
    webhook_path: str = Field("bot", alias="WEBHOOK_PATH")
    webhook_secret_token: Optional[str] = Field(None, alias="WEBHOOK_SECRET_TOKEN")

    # External Site Grabber (YouTube bypass)
    external_site_url: str = Field(
        "https://en.ssyoutube.com/en/download", alias="EXTERNAL_SITE_URL"
    )
    external_site_timeout_ms: int = Field(30_000, alias="EXTERNAL_SITE_TIMEOUT_MS")

    # Logs
    transcribe_log: Path = Path("logs/transcribe.log")
    ai_log: Path = Path("logs/ai.log")
    transcribe_pid: Path = Path("logs/transcribe.pid")
    ai_pid: Path = Path("logs/ai.pid")

    def model_post_init(self, __context: object) -> None:
        # Ensure directories exist
        self.transcribe_log.parent.mkdir(parents=True, exist_ok=True)
