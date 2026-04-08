"""
QueueStore — персистентная очередь задач на SQLite (aiosqlite).

Заменяет in-memory ProcessQueue: очередь переживает рестарт бота.
"""
import logging
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
from typing import AsyncIterator, Optional

import aiosqlite

logger = logging.getLogger(__name__)

# Абсолютный путь от корня проекта (3 уровня вверх от этого файла)
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
DB_PATH = _PROJECT_ROOT / "bot_state" / "queue.db"


@asynccontextmanager
async def _get_db() -> AsyncIterator[aiosqlite.Connection]:
    """Контекстный менеджер для подключения к SQLite."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    db = await aiosqlite.connect(DB_PATH)
    db.row_factory = aiosqlite.Row
    try:
        yield db
    finally:
        await db.close()


async def init_db() -> None:
    """Создать таблицы при старте бота."""
    async with _get_db() as db:
        await db.executescript("""
            CREATE TABLE IF NOT EXISTS task_queue (
                id        INTEGER PRIMARY KEY AUTOINCREMENT,
                task_type TEXT    NOT NULL,   -- 'transcribe' | 'ai' | 'rag'
                user_id   INTEGER NOT NULL,
                username  TEXT,
                status    TEXT    NOT NULL DEFAULT 'queued',  -- queued | running | done | error
                pid       INTEGER,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_queue_type_status
                ON task_queue (task_type, status);
        """)
        await db.commit()
    logger.info("✅ QueueStore: БД инициализирована")


class QueueStore:
    """
    Асинхронный персистентный стор очереди задач.

    Использование:
        store = QueueStore()
        await store.enqueue('transcribe', user_id=123, username='lexey')
        pos = await store.queue_position('transcribe', user_id=123)
        await store.set_running('transcribe', user_id=123, pid=4567)
        await store.set_done('transcribe', user_id=123)
    """

    # ── Постановка в очередь ──────────────────────────────────────

    async def enqueue(self, task_type: str, user_id: int, username: str = "") -> int:
        """
        Добавить задачу в очередь.

        Returns:
            Позиция в очереди (1-based). Если уже есть — возвращает текущую позицию.
        """
        now = datetime.utcnow().isoformat()
        async with _get_db() as db:
            # Проверяем, не стоит ли уже
            async with db.execute(
                "SELECT id FROM task_queue WHERE task_type=? AND user_id=? AND status IN ('queued','running')",
                (task_type, user_id),
            ) as cur:
                row = await cur.fetchone()
            if row:
                return await self.queue_position(task_type, user_id)

            await db.execute(
                "INSERT INTO task_queue (task_type, user_id, username, status, created_at, updated_at) "
                "VALUES (?, ?, ?, 'queued', ?, ?)",
                (task_type, user_id, username, now, now),
            )
            await db.commit()
        return await self.queue_position(task_type, user_id)

    # ── Статус и позиция ─────────────────────────────────────────

    async def queue_position(self, task_type: str, user_id: int) -> int:
        """Позиция в очереди (1-based). 0 если не в очереди."""
        async with _get_db() as db:
            async with db.execute(
                """
                SELECT COUNT(*) as pos FROM task_queue
                WHERE task_type=? AND status='queued'
                  AND id <= (
                      SELECT id FROM task_queue
                      WHERE task_type=? AND user_id=? AND status='queued'
                      ORDER BY id LIMIT 1
                  )
                """,
                (task_type, task_type, user_id),
            ) as cur:
                row = await cur.fetchone()
        return row["pos"] if row else 0

    async def is_running(self, task_type: str) -> bool:
        """Есть ли уже запущенная задача этого типа?"""
        async with _get_db() as db:
            async with db.execute(
                "SELECT id FROM task_queue WHERE task_type=? AND status='running' LIMIT 1",
                (task_type,),
            ) as cur:
                return await cur.fetchone() is not None

    async def get_status(self, task_type: str, user_id: int) -> dict:
        """Статус конкретного пользователя для типа задачи."""
        async with _get_db() as db:
            async with db.execute(
                "SELECT status, pid FROM task_queue "
                "WHERE task_type=? AND user_id=? AND status IN ('queued','running') "
                "ORDER BY id LIMIT 1",
                (task_type, user_id),
            ) as cur:
                row = await cur.fetchone()

        if not row:
            return {"status": "idle"}

        if row["status"] == "running":
            return {"status": "running", "pid": row["pid"]}

        pos = await self.queue_position(task_type, user_id)
        return {"status": "queued", "position": pos}

    # ── Управление состоянием ─────────────────────────────────────

    async def set_running(self, task_type: str, user_id: int, pid: int = 0) -> None:
        """Пометить задачу как запущенную."""
        now = datetime.utcnow().isoformat()
        async with _get_db() as db:
            await db.execute(
                "UPDATE task_queue SET status='running', pid=?, updated_at=? "
                "WHERE task_type=? AND user_id=? AND status='queued' "
                "ORDER BY id LIMIT 1",
                (pid, now, task_type, user_id),
            )
            await db.commit()

    async def set_done(self, task_type: str, user_id: int) -> None:
        """Завершить задачу (удаляем из активных)."""
        now = datetime.utcnow().isoformat()
        async with _get_db() as db:
            await db.execute(
                "UPDATE task_queue SET status='done', updated_at=? "
                "WHERE task_type=? AND user_id=? AND status='running'",
                (now, task_type, user_id),
            )
            await db.commit()

    async def set_error(self, task_type: str, user_id: int) -> None:
        """Отметить задачу как упавшую."""
        now = datetime.utcnow().isoformat()
        async with _get_db() as db:
            await db.execute(
                "UPDATE task_queue SET status='error', updated_at=? "
                "WHERE task_type=? AND user_id=? AND status='running'",
                (now, task_type, user_id),
            )
            await db.commit()

    # ── Очистка ───────────────────────────────────────────────────

    async def cleanup_stale(self, task_type: Optional[str] = None) -> int:
        """
        Удалить завершённые/упавшие записи старше 24 часов.

        Returns:
            Количество удалённых строк.
        """
        async with _get_db() as db:
            if task_type:
                cur = await db.execute(
                    "DELETE FROM task_queue WHERE task_type=? AND status IN ('done','error') "
                    "AND updated_at < datetime('now', '-1 day')",
                    (task_type,),
                )
            else:
                cur = await db.execute(
                    "DELETE FROM task_queue WHERE status IN ('done','error') "
                    "AND updated_at < datetime('now', '-1 day')"
                )
            await db.commit()
        count = cur.rowcount
        if count:
            logger.debug(f"QueueStore: удалено {count} устаревших записей")
        return count


# Глобальный синглтон — импортировать отсюда
queue_store = QueueStore()
