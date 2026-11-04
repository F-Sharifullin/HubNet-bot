from bot.app.database.connection import get_connection


async def get_stats() -> dict:
    async with get_connection() as conn:
        row = await conn.fetchrow(
            """
            SELECT
                COUNT(*)                                            AS total_users,
                COUNT(*) FILTER (WHERE balance > 0)                AS active_users,
                COUNT(*) FILTER (WHERE balance <= 0)               AS disabled_users,
                COUNT(*) FILTER (WHERE created >= NOW() - INTERVAL '7 days') AS new_7d,
                COUNT(*) FILTER (WHERE referrer_id IS NOT NULL)    AS from_referral
            FROM users
            """
        )
        devices = await conn.fetchval("SELECT COUNT(*) FROM subscriptions")
        return {**dict(row), "total_devices": devices}


async def find_user_by_query(query: str) -> int | None:
    """Ищет telegram_id по ID или по remark устройства."""
    query = query.strip().removeprefix("@")

    async with get_connection() as conn:
        # 1. Поиск по telegram_id (если запрос — число)
        if query.isdigit():
            row = await conn.fetchrow(
                "SELECT telegram_id FROM users WHERE telegram_id = $1",
                int(query),
            )
            if row:
                return row["telegram_id"]

        # 2. Поиск по username (регистронезависимо)
        row = await conn.fetchrow(
            "SELECT telegram_id FROM users WHERE username ILIKE $1",
            query
        )
        if row:
            return row["telegram_id"]

        # 3. Поиск по remark устройства
        row = await conn.fetchrow(
            "SELECT telegram_id FROM subscriptions WHERE remark = $1",
            query,
        )
        if row:
            return row["telegram_id"]

        return None


async def get_user_card_data(telegram_id: int) -> dict | None:
    """Данные пользователя + количество устройств и рефералов."""
    async with get_connection() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM users WHERE telegram_id = $1", telegram_id
        )
        if not row:
            return None

        device_count = await conn.fetchval(
            "SELECT COUNT(*) FROM subscriptions WHERE telegram_id = $1",
            telegram_id,
        )
        referrals = await conn.fetchval(
            "SELECT COUNT(*) FROM users WHERE referrer_id = $1",
            telegram_id,
        )

    return {**dict(row), "device_count": device_count, "referrals": referrals}