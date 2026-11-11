import asyncio
import logging
import random
import string
from datetime import datetime, timedelta, timezone

from aiogram import F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery

from bot.app.database.connection import get_connection
from bot.app.database.tariffs import TARIFFS
from bot.app.database.users import add_balance_and_enable_if_needed, get_user
from bot.app.keyboards.user import activate, claim, fortune_luck

logger = logging.getLogger(__name__)
router = Router()

# ⚠️ ТЕСТОВЫЙ РЕЖИМ: кулдаун "раз в месяц" отключён.
# Перед продакшеном — поставить False.
TEST_MODE_NO_COOLDOWN = False


class WheelFSM(StatesGroup):
    waiting_claim = State()
    waiting_activate = State()


# ====================== Призы ======================
# Легенда эмодзи:
# 🎁 — дни VPN бесплатно
# 💰 — пополнение счёта (баланс)
# 🔄 — доп. попытка (крутить ещё раз)
# 0️⃣ — без приза

SECTORS = [
    {"pos": 0, "emoji": "🎁", "key": "free_month",   "full": "Месяц VPN бесплатно",       "type": "free_days", "value": 30, "weight": 5},
    {"pos": 1, "emoji": "🎁", "key": "free_week",    "full": "7 дней VPN бесплатно",      "type": "free_days", "value": 7,  "weight": 15},
    {"pos": 2, "emoji": "💰", "key": "bonus_10",     "full": "Бонус 10₽ на баланс",       "type": "balance",   "value": 10, "weight": 20}, 
    {"pos": 3, "emoji": "💰", "key": "bonus_20",     "full": "Бонус 20₽ на баланс",       "type": "balance",   "value": 20, "weight": 15},
    {"pos": 4, "emoji": "💰", "key": "bonus_50",     "full": "Бонус 50₽ на баланс",       "type": "balance",   "value": 50, "weight": 8},
    {"pos": 5, "emoji": "🔄", "key": "respin",       "full": "Дополнительная попытка!",   "type": "respin",    "value": None, "weight": 7},
    {"pos": 6, "emoji": "0️⃣", "key": "empty_1",      "full": "Увы, в этот раз без приза", "type": "none",      "value": None, "weight": 15},
    {"pos": 7, "emoji": "0️⃣", "key": "empty_2",      "full": "Увы, в этот раз без приза", "type": "none",      "value": None, "weight": 10},
    {"pos": 8, "emoji": "0️⃣", "key": "empty_3",      "full": "Увы, в этот раз без приза", "type": "none",      "value": None, "weight": 5},
]
# Сумма weight = 100

SPIN_COOLDOWN_DAYS = 30


# ====================== Промо-ключ ======================

def generate_promo_key() -> str:
    """Генерирует ключ вида KEY-XXXX-XXXX."""
    alphabet = string.ascii_uppercase + string.digits
    part1 = "".join(random.choices(alphabet, k=4))
    part2 = "".join(random.choices(alphabet, k=4))
    return f"KEY-{part1}-{part2} "


def _strikethrough(text: str) -> str:
    """Зачёркивает текст через unicode-комбинирующий символ (работает даже внутри <pre>,
    так как обычные HTML-теги форматирования внутри <pre>/<code> Telegram игнорирует)."""
    return "".join(ch + "\u0336" for ch in text)


# ====================== Рендер прогресс-бара (чисто зелёный, без намёков) ======================

def _subtitle_for(percent: int) -> str:
    if percent < 100:
        return "Загрузка..."
    else:
        return "Загрузка завершена!"


def render_loading_bar(percent: int) -> str:
    """Обычная зелёная полоса загрузки, без эмодзи-подсказок о призе."""
    filled = percent // 10
    empty = 10 - filled
    bar = "🟩" * filled + "⬜" * empty
    return f"<b>СЛОТ УДАЧИ</b>\n\n{bar} {percent}%\n{_subtitle_for(percent)}"


def render_prize_with_key(prize: dict, promo_key: str) -> str:
    return (
        "🎉 <b>Поздравляем! Вам выпал приз</b>\n\n"
        f"{prize['emoji']} {prize['full']}\n"
        "<blockquote expandable>"
        "ℹ️ Как активировать:\n"
        "1. Нажмите кнопку «Активировать» ниже\n"
        "2. Приз автоматически зачислится на ваш аккаунт\n"
        "</blockquote>\n"
        "🔑 Промо-ключ:\n"
        f"<pre>{promo_key}</pre>\n\n"
        "👇 Нажмите «Активировать», чтобы зачислить приз"
    )


def render_activated(prize: dict, promo_key: str) -> str:
    struck_key = _strikethrough(promo_key)
    return (
        "✅ <b>Промо-ключ активирован!</b>\n\n"
        f"{prize['emoji']} Приз: {prize['full']}\n"
        "<blockquote expandable>"
        "ℹ️ Приз зачислен на ваш аккаунт автоматически.\n"
        "Ключ одноразовый — он уже использован и повторной активации не подлежит."
        "</blockquote>\n"
        f"🔑 Промо-ключ:\n"
        f"<pre>{struck_key}</pre>\n\n"
        "Спасибо что выбираете нас! 🎉"
    )


def render_no_prize(prize: dict) -> str:
    return (
        "<b>СЛОТ УДАЧИ</b>\n\n"
        f"😔 <b>{prize['full']}</b>\n\n"
        "Попробуйте в следующем месяце — удача переменчива!"
    )


def render_respin(prize: dict) -> str:
    return (
        "<b>СЛОТ УДАЧИ</b>\n\n"
        f"🔄 <b>{prize['full']}</b>\n\n"
        "Нажмите «Испытать удачу» ещё раз — бонусная попытка от нас!"
    )


def pick_prize() -> dict:
    weights = [s["weight"] for s in SECTORS]
    return random.choices(SECTORS, weights=weights, k=1)[0]


# ====================== БД: кулдаун и статус ======================

async def get_wheel_status(telegram_id: int) -> tuple[bool, str | None]:
    """Возвращает (можно_крутить, дата_след_попытки_если_нет).
    Кулдаун считается по последней НЕ-respin записи в fortune_spins —
    respin даёт немедленную доп. попытку и не блокирует следующий месяц."""
    async with get_connection() as conn:
        last_spin = await conn.fetchval(
            """
            SELECT created_at FROM fortune
            WHERE telegram_id = $1 AND prize_key != 'respin'
            ORDER BY created_at DESC LIMIT 1
            """,
            telegram_id
        )
    if last_spin is None:
        return True, None
    next_available = last_spin + timedelta(days=SPIN_COOLDOWN_DAYS)
    if next_available <= datetime.now(timezone.utc):
        return True, None
    return False, next_available.strftime("%d.%m.%Y")


async def apply_wheel_prize(telegram_id: int, prize: dict):
    if prize["type"] == "balance":
        await add_balance_and_enable_if_needed(telegram_id, prize["value"])
    elif prize["type"] == "free_days":
        user = await get_user(telegram_id)
        rubles = round(TARIFFS[user["tariff"]].daily_price * prize["value"])
        await add_balance_and_enable_if_needed(telegram_id, rubles)

async def save_fortune_spin(telegram_id: int, promo_key: str, prize: dict) -> int:
    """Записывает приз в историю сразу после показа. Возвращает id записи."""
    async with get_connection() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO fortune (telegram_id, promo_key, prize_key, prize_full)
            VALUES ($1, $2, $3, $4)
            RETURNING id
            """,
            telegram_id, promo_key, prize["key"], prize["full"]
        )
    return row["id"]


async def mark_fortune_spin_activated(spin_id: int) -> None:
    """Отмечает запись как активированную — вызывается в момент реального зачисления приза."""
    async with get_connection() as conn:
        await conn.execute(
            "UPDATE fortune SET activated = TRUE, activated_at = NOW() WHERE id = $1",
            spin_id
        )

async def get_latest_fortune_spin(telegram_id: int) -> dict | None:
    """Возвращает последнюю прокрутку колеса фортуны для карточки пользователя в админке."""
    async with get_connection() as conn:
        row = await conn.fetchrow(
            """
            SELECT prize_full, activated, created_at, activated_at
            FROM fortune
            WHERE telegram_id = $1
            ORDER BY created_at DESC
            LIMIT 1
            """,
            telegram_id
        )
    return dict(row) if row else None

# ====================== Анимация загрузки ======================

async def _animate_loading(message):
    """Заполняет полосу по одному квадратику (0, 10, 20 ... 100), медленно.
    Полоса чисто зелёная — никаких намёков на приз."""
    for percent in range(0, 101, 10):  # 11 кадров
        try:
            await message.edit_text(render_loading_bar(percent), parse_mode="HTML")
        except TelegramBadRequest:
            pass  # "message is not modified" — игнорируем
        await asyncio.sleep(1.0)


# ====================== Хендлеры ======================

WHEEL_INTRO_TEXT = (
    "<b>Ежемесячный приз</b>\n\n"
    "Раз в месяц вы можете испытать удачу и получить один из призов:\n"
    "<blockquote expandable>"
    "👑 1 месяц VPN бесплатно\n"
    "🎁 7 дней VPN бесплатно\n"
    "💰 10₽ / 20₽ или 50₽ на баланс\n"
    "🔄 Дополнительная попытка\n"
    "0️⃣ Без приза"
    "</blockquote>\n\n"
    "Попытка обновляется автоматически раз в месяц 🔁\n\n"
)


@router.callback_query(F.data == "monthly_bonus")
async def wheel_open(callback: CallbackQuery):
    if TEST_MODE_NO_COOLDOWN:
        await callback.answer()
        text = WHEEL_INTRO_TEXT + "🧪 Тестовый режим: крутите сколько угодно раз!"
        await callback.message.answer(text, reply_markup=fortune_luck, parse_mode="HTML")
        return

    can_spin, next_available_str = await get_wheel_status(callback.from_user.id)

    if not can_spin:
        # Всплывающее уведомление вместо нового сообщения в чат
        await callback.answer(
            f"🎰 Попытка уже использована!\n\n❗️Напоминаем: испытать удачу можно 1 раз в месяц.\nСледующая попытка: {next_available_str}",
            show_alert=True,
        )
        return

    await callback.answer()
    await callback.message.answer(WHEEL_INTRO_TEXT, reply_markup=fortune_luck, parse_mode="HTML")

@router.callback_query(F.data == "wheel_spin")
async def wheel_spin(callback: CallbackQuery, state: FSMContext):
    telegram_id = callback.from_user.id

    if not TEST_MODE_NO_COOLDOWN:
        can_spin, next_available_str = await get_wheel_status(telegram_id)
        if not can_spin:
            await callback.answer(
                f"🎰 Попытка уже использована!\n\n❗️Напоминаем: испытать удачу можно 1 раз в месяц.\nСледующая попытка: {next_available_str}",
                show_alert=True,
            )
            return

    await callback.answer()

    prize = pick_prize()
    promo_key = generate_promo_key()

    msg = await callback.message.answer(render_loading_bar(0), parse_mode="HTML")
    await _animate_loading(msg)

    # Записываем в историю сразу после того, как приз определён (activated=FALSE по умолчанию)
    spin_id = await save_fortune_spin(telegram_id, promo_key, prize)

    await state.set_state(WheelFSM.waiting_claim)
    await state.update_data(prize_key=prize["key"], promo_key=promo_key, spin_id=spin_id)

    # Ветвление по типу приза сразу после загрузки
    if prize["type"] == "none":
        await state.clear()
        await msg.edit_text(render_no_prize(prize), parse_mode="HTML")
        logger.info("Пользователь %s: без приза (%s)", telegram_id, prize["key"])
        return

    if prize["type"] == "respin":
        await state.clear()
        # Кулдаун НЕ ставится — respin исключён из get_wheel_status
        await msg.edit_text(render_respin(prize), reply_markup=fortune_luck, parse_mode="HTML")
        logger.info("Пользователь %s: доп. попытка (%s)", telegram_id, prize["key"])
        return

    # free_days / balance — обычный сценарий с ключом
    await msg.edit_reply_markup(reply_markup=claim())


@router.callback_query(F.data == "wheel_claim", WheelFSM.waiting_claim)
async def wheel_claim(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    prize_key = data.get("prize_key")
    promo_key = data.get("promo_key")
    prize = next((s for s in SECTORS if s["key"] == prize_key), None)

    if prize is None or promo_key is None:
        await state.clear()
        await callback.answer("❌ Ошибка. Попробуйте прокрутить заново.", show_alert=True)
        return

    await state.set_state(WheelFSM.waiting_activate)
    # prize_key, promo_key, spin_id уже в state с предыдущего шага — обновлять не нужно

    await callback.answer()
    await callback.message.edit_text(
        render_prize_with_key(prize, promo_key),
        reply_markup=activate(),
        parse_mode="HTML",
    )


@router.callback_query(F.data == "wheel_activate", WheelFSM.waiting_activate)
async def wheel_activate(callback: CallbackQuery, state: FSMContext):
    telegram_id = callback.from_user.id

    data = await state.get_data()
    prize_key = data.get("prize_key")
    promo_key = data.get("promo_key")
    spin_id = data.get("spin_id")
    prize = next((s for s in SECTORS if s["key"] == prize_key), None)

    await state.clear()

    if prize is None or promo_key is None:
        await callback.answer("❌ Ошибка. Попробуйте прокрутить заново.", show_alert=True)
        return

    await apply_wheel_prize(telegram_id, prize)

    if spin_id is not None:
        await mark_fortune_spin_activated(spin_id)

    await callback.answer("✅ Промо-ключ активирован!", show_alert=True)

    await callback.message.edit_text(
        render_activated(prize, promo_key),
        parse_mode="HTML",
    )

    logger.info(
        "Пользователь %s активировал промо-ключ %s (приз=%s, тест-режим=%s)",
        telegram_id, promo_key, prize["key"], TEST_MODE_NO_COOLDOWN
    )