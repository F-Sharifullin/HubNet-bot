import asyncio
import logging
from decimal import Decimal

from aiogram import Bot

from bot.app.database import get_connection, get_user_clients
from bot.app.database.tariffs import TARIFFS
from bot.app.services import x3ui
from bot.app.services.tariffs import calc_expiry_ms

logger = logging.getLogger(__name__)


async def get_user(user_id: int):
    async with get_connection() as conn:
        return await conn.fetchrow("SELECT * FROM users WHERE telegram_id=$1", user_id)


async def create_user(telegram_id: int, username: str = None, name: str = None, referrer_id: int = None):
    async with get_connection() as conn:
        await conn.execute(
            """
            INSERT INTO users (telegram_id, username, name, balance, bonus, referrer_id)
            VALUES ($1, $2, $3, 0, FALSE, $4)
            ON CONFLICT (telegram_id) DO NOTHING
            """,
            telegram_id, username, name, referrer_id
        )


async def one_bonus(telegram_id: int) -> bool:
    async with get_connection() as conn:
        result = await conn.execute(
            "UPDATE users SET balance = balance + 150, bonus = TRUE "
            "WHERE telegram_id = $1 AND bonus = FALSE",
            telegram_id
        )
    return result == "UPDATE 1"


async def sync_user_clients(telegram_id: int, enable: bool | None = None):
    """Приводит ключи в панели к состоянию в БД: включён/выключен и срок по балансу."""
    user = await get_user(telegram_id)
    clients = await get_user_clients(telegram_id)
    if not user or not clients:
        return

    if enable is None:
        enable = user["balance"] > 0
    expiry_ms = calc_expiry_ms(user["balance"], user["tariff"]) if enable else 0

    results = await asyncio.gather(
        *(x3ui.set_client_enable(cl["uuid"], cl["remark"], cl["sub_id"], enable, expiry_ms)
          for cl in clients),
        return_exceptions=True,
    )
    for cl, res in zip(clients, results):
        if isinstance(res, Exception) or res is False:
            logger.error("Не удалось обновить клиента %s (user %s): %s",
                         cl["uuid"], telegram_id, res)


async def disable_user_subscriptions(telegram_id: int):
    await sync_user_clients(telegram_id, enable=False)


async def enable_user_subscriptions(telegram_id: int):
    await sync_user_clients(telegram_id, enable=True)


async def charge_all_users(bot: Bot):
    """Ежедневное списание по тарифу. Защита от двойного списания по last_charge."""
    async with get_connection() as conn:
        rows = await conn.fetch(
            """
            UPDATE users u
            SET balance = GREATEST(
                    u.balance - CASE u.tariff
                        WHEN 'START'    THEN $1::numeric
                        WHEN 'STANDARD' THEN $2::numeric
                        ELSE $3::numeric
                    END, 0),
                last_charge = NOW()
            WHERE u.devices > 0
              AND u.balance > 0
              AND (u.last_charge IS NULL OR u.last_charge < NOW() - INTERVAL '20 hours')
            RETURNING u.telegram_id, u.balance AS balance_after
            """,
            TARIFFS["START"].daily_price,
            TARIFFS["STANDARD"].daily_price,
            TARIFFS["PREMIUM"].daily_price,
        )

    sem = asyncio.Semaphore(5)

    async def _sync(row):
        async with sem:
            await sync_user_clients(row["telegram_id"], enable=row["balance_after"] > 0)

    await asyncio.gather(*(_sync(r) for r in rows), return_exceptions=True)


async def get_days_left(telegram_id: int, balance, tariff_name: str | None = None, user=None) -> int | None:
    user = user or await get_user(telegram_id)
    if not user or user["devices"] == 0:
        return None
    tariff = TARIFFS[tariff_name or user["tariff"]]
    return int(Decimal(str(balance)) // tariff.daily_price)


async def can_add_device(telegram_id: int) -> bool:
    user = await get_user(telegram_id)
    return bool(user) and user["devices"] < TARIFFS[user["tariff"]].max_keys


async def set_tariff(telegram_id: int, tariff: str) -> bool:
    if tariff not in TARIFFS:
        return False
    async with get_connection() as conn:
        result = await conn.execute(
            "UPDATE users SET tariff = $1, low_balance = 0 WHERE telegram_id = $2",
            tariff, telegram_id
        )
    ok = result == "UPDATE 1"
    if ok:
        await sync_user_clients(telegram_id)
    return ok


async def add_balance(telegram_id: int, rubles: int):
    async with get_connection() as conn:
        await conn.execute(
            "UPDATE users SET balance = balance + $1::numeric, low_balance = 0, last_topup = NOW() "
            "WHERE telegram_id = $2",
            Decimal(rubles), telegram_id
        )
    await sync_user_clients(telegram_id)


async def add_balance_and_enable_if_needed(telegram_id: int, rubles: int) -> bool:
    async with get_connection() as conn:
        row = await conn.fetchrow(
            """
            UPDATE users
            SET balance = balance + $1::numeric, low_balance = 0, last_topup = NOW()
            WHERE telegram_id = $2
            RETURNING (balance - $1::numeric) = 0 AS was_zero
            """,
            Decimal(rubles), telegram_id
        )
    if not row:
        return False
    await sync_user_clients(telegram_id)
    return row["was_zero"]

async def referral_bonus(referrer_id: int) -> bool:
    return await add_balance_and_enable_if_needed(referrer_id, 100)


async def get_users_for_low_balance_notify():
    async with get_connection() as conn:
        rows = await conn.fetch(
            "SELECT telegram_id, low_balance, balance, tariff FROM users WHERE balance > 0 AND devices > 0"
        )
    result = []
    for row in rows:
        days_left = int(Decimal(str(row["balance"])) // TARIFFS[row["tariff"]].daily_price)
        stage = row["low_balance"]
        if days_left <= 1 and stage < 3:
            result.append((row["telegram_id"], 3, days_left))
        elif days_left <= 3 and stage < 2:
            result.append((row["telegram_id"], 2, days_left))
        elif days_left <= 5 and stage < 1:
            result.append((row["telegram_id"], 1, days_left))
    return result


async def set_low_balance_stage(telegram_id: int, stage: int):
    async with get_connection() as conn:
        await conn.execute("UPDATE users SET low_balance = $1 WHERE telegram_id = $2", stage, telegram_id)


async def resync_all_expiry():
    async with get_connection() as conn:
        rows = await conn.fetch("SELECT telegram_id FROM users WHERE devices > 0")
    sem = asyncio.Semaphore(5)

    async def _one(uid):
        async with sem:
            await sync_user_clients(uid)

    await asyncio.gather(*(_one(r["telegram_id"]) for r in rows), return_exceptions=True)