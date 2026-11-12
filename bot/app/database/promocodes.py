import logging
from datetime import datetime, timezone

from bot.app.database import enable_user_subscriptions, get_connection, get_transaction

logger = logging.getLogger(__name__)

# Разрешать ли активацию промокода до получения стартового бонуса (users.bonus = TRUE).
# True — защита от мультиаккаунтов: сначала нужно активировать аккаунт.
PROMO_REQUIRE_BONUS = False

# ─── Пользователь ───────────────────────────────────────────────────────────

async def activate_promocode(telegram_id: int, code: str) -> dict:
    """
    Активирует промокод. Всё выполняется в одной транзакции, строка промокода
    блокируется (FOR UPDATE), поэтому лимит активаций не превысить гонкой.

    Возвращает dict со status:
      ok / not_found / disabled / expired / limit / already / no_user / no_bonus
    При ok дополнительно: amount, balance, was_activated.
    """
    code = code.strip().upper()

    async with get_transaction() as conn:
        promo = await conn.fetchrow(
            "SELECT * FROM promocodes WHERE code = $1 FOR UPDATE", code
        )
        if not promo:
            return {"status": "not_found"}
        if not promo["is_active"]:
            return {"status": "disabled"}
        if promo["expires_at"] and promo["expires_at"] < datetime.now(timezone.utc):
            return {"status": "expired"}
        if promo["max_uses"] > 0 and promo["used_count"] >= promo["max_uses"]:
            return {"status": "limit"}

        user = await conn.fetchrow(
            "SELECT bonus FROM users WHERE telegram_id = $1", telegram_id
        )
        if not user:
            return {"status": "no_user"}
        if PROMO_REQUIRE_BONUS and not user["bonus"]:
            return {"status": "no_bonus"}

        already = await conn.fetchval(
            "SELECT 1 FROM promo_activations WHERE promo_id = $1 AND telegram_id = $2",
            promo["id"], telegram_id,
        )
        if already:
            return {"status": "already"}

        # Начисление — тот же SQL, что в add_balance_and_enable_if_needed,
        # но на соединении транзакции (иначе начисление и запись активации
        # не будут атомарными).
        
        row = await conn.fetchrow(
            """
            UPDATE users
            SET balance = balance + $1::numeric,
                low_balance = 0,
                last_topup = NOW()
            WHERE telegram_id = $2
            RETURNING balance, (balance - $1::numeric) = 0 AS was_zero
            """,
            promo["amount"], telegram_id,
        )

        await conn.execute(
            "INSERT INTO promo_activations (promo_id, telegram_id) VALUES ($1, $2)",
            promo["id"], telegram_id,
        )
        await conn.execute(
            "UPDATE promocodes SET used_count = used_count + 1 WHERE id = $1",
            promo["id"],
        )

    # Транзакция закоммичена. Обращения к панели — уже вне неё,
    # чтобы не держать блокировку строки промокода на время HTTP-запросов.
    was_zero = bool(row["was_zero"])
    try:
        await enable_user_subscriptions(telegram_id)
    except Exception:
        logger.exception("Не удалось синхронизировать панель для %s после промокода", telegram_id)

    logger.info(
        "Промокод %s активирован пользователем %s (+%s₽)",
        code, telegram_id, promo["amount"],
    )
    return {
        "status": "ok",
        "amount": promo["amount"],
        "balance": row["balance"],
        "was_activated": was_zero,
    }

# ─── Админ ──────────────────────────────────────────────────────────────────

async def promocode_exists(code: str) -> bool:
    async with get_connection() as conn:
        return bool(await conn.fetchval(
            "SELECT 1 FROM promocodes WHERE code = $1", code.strip().upper()
        ))

async def create_promocode(
    code: str,
    amount: int,
    max_uses: int = 0,
    expires_at: datetime | None = None,
) -> bool:
    """Создаёт промокод. False — если такой код уже существует."""
    async with get_connection() as conn:
        new_id = await conn.fetchval(
            """
            INSERT INTO promocodes (code, amount, max_uses, expires_at)
            VALUES ($1, $2, $3, $4)
            ON CONFLICT (code) DO NOTHING
            RETURNING id
            """,
            code.strip().upper(), amount, max_uses, expires_at,
        )
    if new_id is not None:
        logger.info("Создан промокод %s (%s₽, лимит=%s, до=%s)", code, amount, max_uses, expires_at)
    return new_id is not None

async def get_promocodes_page(limit: int, offset: int) -> tuple[list[dict], int]:
    async with get_connection() as conn:
        total = await conn.fetchval("SELECT COUNT(*) FROM promocodes")
        rows = await conn.fetch(
            """
            SELECT id, code, amount, max_uses, used_count, expires_at, is_active, created_at
            FROM promocodes
            ORDER BY created_at DESC, id DESC
            LIMIT $1 OFFSET $2
            """,
            limit, offset,
        )
    return [dict(r) for r in rows], total

async def get_promocode(promo_id: int) -> dict | None:
    async with get_connection() as conn:
        row = await conn.fetchrow("SELECT * FROM promocodes WHERE id = $1", promo_id)
    return dict(row) if row else None

async def toggle_promocode(promo_id: int) -> bool | None:
    """Переключает is_active. Возвращает новое значение или None, если не найден."""
    async with get_connection() as conn:
        return await conn.fetchval(
            "UPDATE promocodes SET is_active = NOT is_active WHERE id = $1 RETURNING is_active",
            promo_id,
        )

async def delete_promocode(promo_id: int) -> bool:
    """Удаляет промокод (активации удалятся каскадом)."""
    async with get_connection() as conn:
        result = await conn.execute("DELETE FROM promocodes WHERE id = $1", promo_id)
    return result == "DELETE 1"