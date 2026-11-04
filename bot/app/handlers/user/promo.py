import asyncio
import logging
import re

from aiogram import F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message

from bot.app.database import get_days_left
from bot.app.database.cache import (
    PROMO_MAX_FAILS,
    add_promo_fail,
    is_promo_blocked,
    reset_promo_fails,
)
from bot.app.database.promocodes import activate_promocode
from bot.app.keyboards.user import home_button, promo_cancel

router = Router()
logger = logging.getLogger(__name__)
 
CODE_RE = re.compile(r"^[A-Z0-9]{4,20}$")
 
class PromoEnterFSM(StatesGroup):
    waiting_code = State()


@router.callback_query(F.data == "cancel")
async def cancel(callback: CallbackQuery):
    await callback.answer()
    await callback.message.delete()


PROMPT_TEXT = (
    "<b>🎟️ Активация промокода</b>\n\n"
    "Введите промокод, чтобы получить дополнительные дни подписки.\n"
    '<blockquote>'
    "Отправьте промокод одним сообщением."
    '</blockquote>'
)
 
BLOCKED_TEXT = "🚫 Слишком много неверных попыток. Попробуйте через 10 минут."
 
ERROR_TEXTS = {
    "not_found": "❌ Такого промокода не существует. Проверьте написание и попробуйте ещё раз.",
    "already":   "⚠️ Вы уже активировали этот промокод.",
    "expired":   "⌛️ Срок действия промокода закончился.",
    "limit":     "⚠️ Промокод достиг лимита активаций.",
    "disabled":  "❌ Промокод недоступен.",
    "no_bonus":  (
        "⚠️ Сначала активируйте аккаунт: нажмите «Подключить VPN» в /start "
        "и получите стартовый бонус. После этого сможете использовать промокод."
    ),
    "no_user":   "❌ Пользователь не найден. Нажмите /start и попробуйте снова.",
}
 
# ─── Пользователь нажал «🎁 Промокод» ──────────────────────────────────────
 
@router.callback_query(F.data == "promo")
async def promo_start(call: CallbackQuery, state: FSMContext):
    await call.answer()
 
    if await is_promo_blocked(call.from_user.id):
        await call.message.answer(BLOCKED_TEXT)
        return
 
    await state.set_state(PromoEnterFSM.waiting_code)
    await call.message.answer(PROMPT_TEXT, reply_markup=promo_cancel, parse_mode="HTML")
 
@router.callback_query(F.data == "cancel")
async def cancel_promo(call: CallbackQuery, state: FSMContext):
    await state.clear()
    await call.answer("🚪Выйти")
    try:
        await call.message.delete()
    except TelegramBadRequest:
        pass
 
# ─── Пользователь отправил код ─────────────────────────────────────────────
 
@router.message(PromoEnterFSM.waiting_code)
async def promo_receive(message: Message, state: FSMContext):
    user_id = message.from_user.id
 
    if not message.text:
        await message.answer("Отправьте промокод текстом.")
        return
 
    # Если пользователь нажал команду (например /start) — выходим из режима ввода
    if message.text.startswith("/"):
        await state.clear()
        await message.answer("Ввод промокода отменён.")
        return
 
    if await is_promo_blocked(user_id):
        await state.clear()
        await message.answer(BLOCKED_TEXT)
        return
 
    code = message.text.strip().upper()
 
    # Неверный формат — считаем как неверную попытку, в БД не ходим
    if not CODE_RE.match(code):
        result = {"status": "not_found"}
    else:
        result = await activate_promocode(user_id, code)
 
    status = result["status"]
 
    # ── Успех ──
    if status == "ok":
        await state.clear()
        await reset_promo_fails(user_id)
 
        balance = result["balance"]
        days_left = await get_days_left(user_id, balance)
        days_text = f"(~{days_left} дней)" if days_left is not None else "(нет активных устройств)"
 
        await message.answer(
            f"✅ <b>Промокод активирован!</b>\n\n"
            f"На баланс зачислено {result['amount']}₽.\n"
            f"Ваш баланс: {balance}₽ {days_text}",
            parse_mode="HTML",
        )
 
        if result["was_activated"]:
            await asyncio.sleep(2)
            await message.answer(
                "🎉 Ваш аккаунт успешно активирован!\n"
                "Вы можете использовать VPN на ваших устройствах!",
                reply_markup=home_button,
            )
        return
 
    # ── Ошибки ──
    if status == "not_found":
        fails = await add_promo_fail(user_id)
        if fails >= PROMO_MAX_FAILS:
            await state.clear()
            await message.answer(BLOCKED_TEXT)
            logger.warning("Пользователь %s заблокирован на ввод промокодов (перебор)", user_id)
            return
 
    await message.answer(
        ERROR_TEXTS.get(status, "❌ Не удалось активировать промокод."),
    )
    # Состояние не сбрасываем — можно попробовать ещё раз или нажать «Отмена»