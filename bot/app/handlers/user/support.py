import logging

from aiogram import Bot, F, Router
from aiogram.exceptions import TelegramAPIError, TelegramBadRequest
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message

from bot.app.database import get_connection
from bot.app.keyboards.admin import reply_ticket
from bot.app.keyboards.user import support_cancel
from bot.config import ADMIN_ID

router = Router()
logger = logging.getLogger(__name__)


class SupportFSM(StatesGroup):
    waiting_message = State()


@router.callback_query(F.data == "support")
async def support_start(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.set_state(SupportFSM.waiting_message)

    text = (
        "🆘 <b>Поддержка</b>\n\n"
        "Опишите вашу проблему — мы ответим в ближайшее время.\n"
        "<blockquote>"
        "Если у вас есть предложение по улучшению бота или идея новой функции — пишите, мы обязательно их рассмотрим."
        "</blockquote>\n\n"
        "<i>Можно прикрепить 1 скриншот.</i>"
    )

    await callback.message.answer(text, parse_mode="HTML", reply_markup=support_cancel)


@router.callback_query(F.data == "cancel")
async def cancel_support(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.answer()
    try:
        await callback.message.delete()
    except TelegramBadRequest:
        pass


# ─── Юзер написал проблему ─────────────────────────────────────────────────

@router.message(SupportFSM.waiting_message)
async def support_receive(message: Message, state: FSMContext, bot: Bot):
    await state.clear()

    user = message.from_user
    photo_id = message.photo[-1].file_id if message.photo else None

    # Получаем баланс юзера
    async with get_connection() as conn:
        row = await conn.fetchrow(
            "SELECT balance FROM users WHERE telegram_id = $1", user.id
        )
        balance = row["balance"] if row else 0

        # Сохраняем тикет
        ticket = await conn.fetchrow(
            """
            INSERT INTO support (user_id, message, photo_id)
            VALUES ($1, $2, $3)
            RETURNING id
            """,
            user.id,
            message.text or message.caption or "[медиа без текста]",
            photo_id,
        )
        ticket_id = ticket["id"]

    logger.info(f"Создан тикет #{ticket_id} от user_id={user.id} (@{user.username})")

    # Подтверждение юзеру
    await message.answer(
        f"✅ <b>Обращение #{ticket_id} принято</b>\n\n"
        "Наша команда уже получила ваше сообщение и занимается решением вопроса.\n"
        "Ожидайте ответ в ближайшее время.",
        parse_mode="HTML"
    )

    username_part = f"@{user.username}" if user.username else "без username"
    admin_text = (
        f"🆘 <b>Новый тикет #{ticket_id}</b>\n"
        f"👤 {user.full_name} {username_part}\n"
        f"💰 Баланс: {balance} ₽\n\n"
        f"💬 {message.text or message.caption or '[медиа]'}"
    )

    # Если прислал фото — пересылаем фото
    try:
        if photo_id:
            await bot.send_photo(
                ADMIN_ID,
                photo=photo_id,
                caption=admin_text,
                reply_markup=reply_ticket(ticket_id, user.id),
                parse_mode="HTML"
            )
        else:
            await bot.send_message(
                ADMIN_ID,
                admin_text,
                reply_markup=reply_ticket(ticket_id, user.id),
                parse_mode="HTML"
            )
        logger.info(f"Тикет #{ticket_id} отправлен админу")
    except TelegramAPIError as e:
        logger.error(f"Не удалось отправить тикет #{ticket_id} админу: {e}")