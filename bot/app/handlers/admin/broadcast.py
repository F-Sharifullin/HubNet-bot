import asyncio
import logging

from aiogram import Bot, F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message

from bot.app.database.connection import get_connection
from bot.app.handlers.admin.panel import is_admin
from bot.app.keyboards.admin import broadcast_audience, broadcast_confirm

router = Router()
logger = logging.getLogger(__name__)


class BroadcastFSM(StatesGroup):
    choosing_target = State()
    waiting_message = State()
    confirm = State()

@router.message(F.text == "📢 Рассылка")
async def start_broadcast(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    await message.delete()
    await state.set_state(BroadcastFSM.choosing_target)
    await message.answer(
        "📢 <b>Рассылка</b>\n\n"
        "<b>Всем</b> — отправить всем пользователям бота\n"
        "<b>Отключённым</b> — отправить только тем, у кого баланс 0₽\n",
        reply_markup=broadcast_audience,
        parse_mode="HTML"
    )

@router.callback_query(F.data.in_({"broadcast_target_all", "broadcast_target_disabled"}), BroadcastFSM.choosing_target)
async def choose_target(callback: CallbackQuery, state: FSMContext):
    target = "all" if callback.data == "broadcast_target_all" else "disabled"
    await state.update_data(target=target)
    await state.set_state(BroadcastFSM.waiting_message)

    target_text = "всем пользователям" if target == "all" else "отключённым пользователям"
    await callback.message.edit_text(
        f"📢 <b>Рассылка → {target_text}</b>\n\n"
        "Отправьте сообщение, которое хотите разослать.\n"
        "Поддерживается текст, фото, видео.",
        parse_mode="HTML"
    )
    await callback.answer()


@router.message(BroadcastFSM.waiting_message)
async def receive_message(message: Message, state: FSMContext):
    await state.update_data(message_id=message.message_id, chat_id=message.chat.id)
    await state.set_state(BroadcastFSM.confirm)

    await message.bot.copy_message(
        chat_id=message.chat.id,
        from_chat_id=message.chat.id,
        message_id=message.message_id,
        reply_markup=broadcast_confirm
    )

@router.callback_query(F.data == "broadcast_edit", BroadcastFSM.confirm)
async def edit_message(callback: CallbackQuery, state: FSMContext):
    await state.set_state(BroadcastFSM.waiting_message)
    await callback.message.edit_text(
        "✏️ Напишите новый текст сообщения:",
        parse_mode="HTML"
    )
    await callback.answer()

@router.callback_query(F.data == "broadcast_confirm", BroadcastFSM.confirm)
async def confirm_broadcast(callback: CallbackQuery, state: FSMContext, bot: Bot):
    if not is_admin(callback.from_user.id):
        return
    await callback.answer()

    data = await state.get_data()
    await state.clear()
    # Убираем кнопки, текст остаётся
    await callback.message.edit_reply_markup(reply_markup=None)

    async with get_connection() as conn:
        if data["target"] == "all":
            rows = await conn.fetch("SELECT telegram_id FROM users")
        else:
            rows = await conn.fetch("SELECT telegram_id FROM users WHERE balance <= 0")

    user_ids = [r["telegram_id"] for r in rows]

    msg = await callback.message.answer(f"🚀 Начинаю рассылку для {len(user_ids)} пользователей...")

    success, failed = 0, 0
    for uid in user_ids:
        if uid == callback.from_user.id:  # пропускаем админа
            continue
        try:
            await bot.copy_message(
                chat_id=uid,
                from_chat_id=data["chat_id"],
                message_id=data["message_id"]
            )
            success += 1
        except Exception:
            failed += 1
        await asyncio.sleep(0.05)

    await msg.edit_text(
        f"✅ Рассылка завершена!\n"
        f"├ Отправлено: {success}\n"
        f"╰ Ошибок: {failed}"
    )


@router.callback_query(F.data == "broadcast_exit")
async def exit_broadcast(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.delete()
    await callback.answer()


@router.callback_query(F.data == "broadcast_cancel")
async def cancel_broadcast(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.delete()
    await callback.message.answer("❌ Рассылка отменена.")