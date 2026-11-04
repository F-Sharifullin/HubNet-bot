import asyncio
import logging
from contextlib import asynccontextmanager

import asyncpg

from bot.config import DB_HOST, DB_NAME, DB_PASSWORD, DB_PORT, DB_USER

logger = logging.getLogger(__name__)

pool: asyncpg.Pool | None = None
_lock = asyncio.Lock()


async def init_pool() -> None:
    """Инициализирует пул соединений. Потокобезопасен."""
    global pool

    if pool is not None:
        return

    async with _lock:
        if pool is not None:  # double-checked locking
            return

        try:
            pool = await asyncpg.create_pool(
                host=DB_HOST,
                port=DB_PORT,
                database=DB_NAME,
                user=DB_USER,
                password=DB_PASSWORD,
                min_size=5,
                max_size=50,
                timeout=10,                    # таймаут подключения к серверу
                command_timeout=30,            # таймаут выполнения запроса
                max_inactive_connection_lifetime=300,
            )
            logger.info(
                "✅ PostgreSQL pool инициализирован (min=%d, max=%d, %s:%s/%s)",
                pool.get_min_size(), pool.get_max_size(), DB_HOST, DB_PORT, DB_NAME
            )
        except Exception as e:
            logger.exception("❌ Ошибка инициализации PostgreSQL pool")
            raise RuntimeError("Не удалось создать пул соединений") from e


def get_pool() -> asyncpg.Pool:
    """Возвращает пул соединений."""
    if pool is None:
        raise RuntimeError(
            "Пул соединений не инициализирован. Сначала вызовите await init_pool()."
        )
    return pool


@asynccontextmanager
async def get_connection(timeout: float = 10.0):
    """
    Контекстный менеджер для получения соединения.
    """
    async with get_pool().acquire(timeout=timeout) as connection:
        yield connection


@asynccontextmanager
async def get_transaction(timeout: float = 10.0):
    """
    Контекстный менеджер для транзакции (автоматический rollback при ошибке).
    """
    async with get_pool().acquire(timeout=timeout) as connection:
        async with connection.transaction():
            yield connection


async def close_pool() -> None:
    """Закрывает пул соединений."""
    global pool
    async with _lock:
        if pool is None:
            logger.warning("⚠️ Попытка закрыть неинициализированный pool")
            return

        try:
            await pool.close()
            logger.info("✅ PostgreSQL pool успешно закрыт")
        except Exception:
            logger.exception("❌ Ошибка при закрытии PostgreSQL pool")
        finally:
            pool = None