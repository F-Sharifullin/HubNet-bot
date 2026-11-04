from bot.app.database import get_connection, get_transaction


async def create_subscription(telegram_id: int, device: str, remark: str, sub_id: str, uuid: str):
    async with get_transaction() as conn:
        result = await conn.execute(
            """
            INSERT INTO subscriptions (telegram_id, device, remark, sub_id, uuid)
            VALUES ($1, $2, $3, $4, $5)
            ON CONFLICT (remark) DO NOTHING
            """,
            telegram_id, device, remark, sub_id, uuid
        )
        if result == "INSERT 0 1":
            await conn.execute("UPDATE users SET devices = devices + 1 WHERE telegram_id = $1", telegram_id)


async def get_user_subscriptions(telegram_id: int):
    async with get_connection() as conn:
        rows = await conn.fetch(
            """
            SELECT remark, sub_id, device
            FROM subscriptions
            WHERE telegram_id = $1
            ORDER BY created DESC
            """,
            telegram_id
        )
        return [dict(row) for row in rows]


async def get_subscription(sub_id: str):
    async with get_connection() as conn:
        row = await conn.fetchrow(
            """
            SELECT uuid, remark, device
            FROM subscriptions
            WHERE sub_id = $1
            """,
            sub_id
        )
        return dict(row) if row else None


async def delete_subscription(sub_id: str):
    async with get_transaction() as conn:
        row = await conn.fetchrow(
            "DELETE FROM subscriptions WHERE sub_id = $1 RETURNING telegram_id", sub_id
        )
        if row:
            await conn.execute(
                "UPDATE users SET devices = GREATEST(devices - 1, 0) WHERE telegram_id = $1",
                row["telegram_id"]
            )


async def get_user_clients(telegram_id: int):
    async with get_connection() as conn:
        rows = await conn.fetch(
            """
            SELECT uuid, remark, sub_id
            FROM subscriptions
            WHERE telegram_id = $1
            """,
            telegram_id
        )
        return [dict(row) for row in rows]