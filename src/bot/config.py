from pathlib import Path
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
    user_name: str = Field("admin", alias="USER_NAME")

    # Whisper
    whisper_model: str = Field("small", alias="WHISPER_MODEL")
    whisper_threads: int = Field(16, alias="WHISPER_THREADS")
    whisper_compute_type: str = Field("int8", alias="WHISPER_COMPUTE_TYPE")

    # Ollama
    ollama_url: str = Field("http://localhost:11434", alias="OLLAMA_HOST")
    ollama_model: str = Field("llama3.2", alias="OLLAMA_MODEL")
    ollama_model_complex: str = Field("qwen2.5:7b", alias="OLLAMA_MODEL_COMPLEX")

    # Logs
    transcribe_log: Path = Path("logs/transcribe.log")
    ai_log: Path = Path("logs/ai.log")
    transcribe_pid: Path = Path("logs/transcribe.pid")
    ai_pid: Path = Path("logs/ai.pid")

    def model_post_init(self, __context):
        # Ensure directories exist
        self.transcribe_log.parent.mkdir(parents=True, exist_ok=True)
