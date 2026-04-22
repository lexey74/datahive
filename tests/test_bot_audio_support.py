from __future__ import annotations

import asyncio
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from src.bot.routers import content as content_router
from src.bot.routers import worker_cmds


class FakeStatusMessage:
    def __init__(self) -> None:
        self.texts: list[str] = []

    async def edit_text(self, text: str) -> None:
        self.texts.append(text)


class FakeBot:
    async def get_file(self, file_id: str) -> SimpleNamespace:
        return SimpleNamespace(file_path=f"files/{file_id}")

    async def download_file(self, file_path: str, destination: Path) -> None:
        destination.write_bytes(b"audio-bytes")

    async def send_chat_action(self, chat_id: int, action: str) -> None:
        _ = (chat_id, action)


class FakeMessage:
    def __init__(self, *, audio=None, voice=None, caption: str = "", text: str = "") -> None:
        self.audio = audio
        self.voice = voice
        self.video = None
        self.document = None
        self.photo = None
        self.caption = caption
        self.text = text
        self.forward_origin = None
        self.from_user = SimpleNamespace(id=123, username="tester")
        self.chat = SimpleNamespace(id=555)
        self.bot = FakeBot()
        self.replies: list[str] = []

    async def reply(self, text: str) -> FakeStatusMessage:
        self.replies.append(text)
        return FakeStatusMessage()

    async def answer(self, text: str) -> FakeStatusMessage:
        self.replies.append(text)
        return FakeStatusMessage()


class FakeFSMContext:
    def __init__(self) -> None:
        self.data: dict = {}
        self.state = None

    async def update_data(self, **kwargs) -> None:
        self.data.update(kwargs)

    async def get_data(self) -> dict:
        return dict(self.data)

    async def set_state(self, value) -> None:
        self.state = value

    async def clear(self) -> None:
        self.data.clear()
        self.state = None


@pytest.mark.asyncio
async def test_handle_media_saves_audio_file(tmp_path: Path) -> None:
    config = SimpleNamespace(users_dir=tmp_path / "users", user_name="admin")
    state = FakeFSMContext()
    audio = SimpleNamespace(
        file_id="audio123456",
        file_name="lecture.mp3",
        mime_type="audio/mpeg",
    )
    message = FakeMessage(audio=audio, caption="Аудио для транскриба")

    await content_router.handle_media(message, state, config)

    downloads_root = tmp_path / "users" / "admin" / "downloads"
    folders = [folder for folder in downloads_root.iterdir() if folder.is_dir()]
    assert len(folders) == 1

    media_folder = folders[0]
    assert media_folder.name.endswith("_telegram_audio_Аудио_для_транскриба")
    assert (media_folder / "audio.mp3").exists()
    assert (media_folder / "description.md").exists()
    assert any("Транскрибировать этот файл сейчас" in text for text in message.replies)
    assert state.state == content_router.ContentStates.waiting_media_transcribe_confirmation


@pytest.mark.asyncio
async def test_handle_media_saves_voice_file(tmp_path: Path) -> None:
    config = SimpleNamespace(users_dir=tmp_path / "users", user_name="admin")
    state = FakeFSMContext()
    voice = SimpleNamespace(file_id="voice654321", mime_type="audio/ogg")
    message = FakeMessage(voice=voice, caption="")

    await content_router.handle_media(message, state, config)

    downloads_root = tmp_path / "users" / "admin" / "downloads"
    folders = [folder for folder in downloads_root.iterdir() if folder.is_dir()]
    assert len(folders) == 1

    media_folder = folders[0]
    assert "_telegram_voice_" in media_folder.name
    assert (media_folder / "voice.ogg").exists()
    assert (media_folder / "description.md").exists()


@pytest.mark.asyncio
async def test_media_transcribe_confirmation_no_keeps_file_for_later() -> None:
    state = FakeFSMContext()
    await state.update_data(media_path="/tmp/file.ogg", media_dir="/tmp")
    message = FakeMessage(text="нет")
    config = SimpleNamespace(whisper_url="http://localhost:9000", whisper_api_key="")

    await content_router.handle_media_transcribe_confirmation(message, state, config)

    assert state.state is None
    assert any("/transcribe" in text for text in message.replies)


@pytest.mark.asyncio
async def test_media_transcribe_confirmation_yes_outputs_text_and_asks_delete(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    media_dir = tmp_path / "media"
    media_dir.mkdir(parents=True)
    media_file = media_dir / "voice.ogg"
    media_file.write_bytes(b"ogg")

    class FakeEars:
        def __init__(self, whisper_url: str, whisper_api_key: str) -> None:
            _ = (whisper_url, whisper_api_key)

        def transcribe(self, media_path: Path):
            _ = media_path
            return content_router.TranscriptResult(
                timed_transcript="[00:00] Привет",
                full_text="Привет, это тест транскрибации.",
                language="ru",
                duration=3.2,
            )

    monkeypatch.setattr(content_router, "LocalEars", FakeEars)

    state = FakeFSMContext()
    await state.update_data(
        media_path=str(media_file),
        media_dir=str(media_dir),
        media_file_name="voice.ogg",
        media_title="Тест",
    )
    message = FakeMessage(text="да")
    config = SimpleNamespace(whisper_url="http://localhost:9000", whisper_api_key="")

    await content_router.handle_media_transcribe_confirmation(message, state, config)

    assert state.state == content_router.ContentStates.waiting_media_delete_confirmation
    assert (media_dir / "transcript.md").exists()
    assert any("Извлеченный текст" in text for text in message.replies)
    assert any("Удалить исходный медиафайл" in text for text in message.replies)


@pytest.mark.asyncio
async def test_media_delete_confirmation_yes_removes_source_file(tmp_path: Path) -> None:
    media_file = tmp_path / "voice.ogg"
    media_file.write_bytes(b"ogg")

    state = FakeFSMContext()
    await state.update_data(media_path=str(media_file))
    await state.set_state(content_router.ContentStates.waiting_media_delete_confirmation)

    message = FakeMessage(text="да")
    await content_router.handle_media_delete_confirmation(message, state)

    assert not media_file.exists()
    assert state.state is None
    assert any("удал" in text.lower() for text in message.replies)


class FakeQueueStore:
    async def is_running(self, task_type: str) -> bool:
        _ = task_type
        return False

    async def enqueue(self, task_type: str, user_id: int, username: str) -> int:
        _ = (task_type, user_id, username)
        return 1

    async def set_running(self, task_type: str, user_id: int) -> None:
        _ = (task_type, user_id)


class FakeCommandMessage:
    def __init__(self) -> None:
        self.from_user = SimpleNamespace(id=123, username="tester")
        self.replies: list[str] = []

    async def reply(self, text: str):
        self.replies.append(text)
        return FakeStatusMessage()


@pytest.mark.asyncio
async def test_cmd_transcribe_picks_ogg_audio(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    user_downloads = tmp_path / "users" / "admin" / "downloads"
    latest_folder = user_downloads / "2026-04-22_12-00_telegram_voice_test"
    latest_folder.mkdir(parents=True)
    ogg_file = latest_folder / "voice.ogg"
    ogg_file.write_bytes(b"ogg")

    captured: dict[str, Path] = {}

    async def fake_run_transcription(
        file_path: Path, output_dir: Path, config, message
    ) -> None:
        _ = (output_dir, config, message)
        captured["file_path"] = file_path

    monkeypatch.setattr(worker_cmds, "queue_store", FakeQueueStore())
    monkeypatch.setattr(worker_cmds, "run_transcription", fake_run_transcription)

    message = FakeCommandMessage()
    state = AsyncMock()
    config = SimpleNamespace(users_dir=tmp_path / "users", user_name="admin")

    await worker_cmds.cmd_transcribe(message, state, config)
    await asyncio.sleep(0)

    assert captured["file_path"] == ogg_file
