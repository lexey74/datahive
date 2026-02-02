from pathlib import Path
from typing import List, Optional
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

class BotConfig(BaseSettings):
    """Configuration for Data Hive Bot"""
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

    # Telegram
    telegram_bot_token: str = Field(..., alias="TELEGRAM_BOT_TOKEN")
    admin_id: int = Field(..., alias="ADMIN_ID")

    # Paths
    users_dir: Path = Field(Path("users"), alias="USERS_DIR")
    downloads_dir: Path = Field(Path("downloads"), alias="DOWNLOADS_DIR")

    # Models
    whisper_model: str = Field("small", alias="WHISPER_MODEL")
    whisper_threads: int = Field(16, alias="WHISPER_THREADS")


    # Logs
    transcribe_log: Path = Path("logs/transcribe.log")
    ai_log: Path = Path("logs/ai.log")
    transcribe_pid: Path = Path("logs/transcribe.pid")
    ai_pid: Path = Path("logs/ai.pid")
    auth_file: Path = Path("auth.json")

    def model_post_init(self, __context):
        # Ensure directories exist
        self.transcribe_log.parent.mkdir(parents=True, exist_ok=True)
