import logging

from aiogram import Bot, F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message

from bot.app.database.connection import get_connection
from bot.app.handlers.admin.panel import is_admin
from bot.app.keyboards.admin import (
    reply_ticket,
    ticket_answer,
    ticket_view,
    tickets_list,
    tickets_menu,
)
from bot.app.utils import to_local
from bot.config import ADMIN_USERNAME

router = Router()
logger = logging.getLogger(__name__)


class AdminReplyFSM(StatesGroup):
    waiting_reply = State()


PAGE_SIZE = 3


async def _show_ticket_list(call: CallbackQuery, text: str, kb):
    """Безопасно показывает текстовый список тикетов, учитывая что текущее
    сообщение могло быть фото (тогда edit_text не сработает)."""
    if call.message.photo:
        try:
            await call.message.delete()
        except Exception:
            pass
        await call.message.answer(text, reply_markup=kb, parse_mode="HTML")
    else:
        try:
            await call.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
        except Exception:
            await call.message.answer(text, reply_markup=kb, parse_mode="HTML")


# ─── Кнопка "📩 Тикеты" в админке ───────────────────────────────────────────

TICKETS_MENU_TEXT = (
    "📩 <b>Тикеты поддержки</b>\n\n"
    "Здесь вы можете управлять всеми обращениями пользователей.\n\n"
    "Выберите нужный раздел:"
)


@router.message(F.text == "📩 Тикеты")
async def menu(message: Message):
    if not is_admin(message.from_user.id):
        return

    await message.delete()

    await message.answer(
        TICKETS_MENU_TEXT,
        reply_markup=tickets_menu(),
        parse_mode="HTML"
    )


@router.callback_query(F.data == "tickets_exit")
async def tickets_exit(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        return

    await callback.message.delete()
    await callback.answer()


@router.callback_query(F.data == "tickets_back")
async def tickets_back(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        return
    await _show_ticket_list(callback, TICKETS_MENU_TEXT, tickets_menu())
    await callback.answer()


# ─── Открытые тикеты (каждый отдельным сообщением — их обычно мало) ────────

@router.callback_query(F.data == "tickets_open")
async def tickets_open(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        return

    async with get_connection() as conn:
        rows = await conn.fetch(
            """
            SELECT t.id, t.user_id, t.message, t.created_at, t.photo_id, u.username, u.balance
            FROM support t
            LEFT JOIN users u ON u.telegram_id = t.user_id
            WHERE t.status = 'open'
            ORDER BY t.created_at DESC
            """
        )

    if not rows:
        await call.answer("✅ Открытых тикетов нет", show_alert=True)
        return

    await call.answer()

    for row in rows:
        username = f"@{row['username']}" if row['username'] else "без username"
        date = to_local(row['created_at'])
        balance = row["balance"] if row["balance"] is not None else 0

        text = (
            f"🆘 <b>Тикет #{row['id']}</b> — {date}\n"
            f"👤 {username}\n"
            f"💰 Баланс: {balance} ₽\n\n"
            f"💬 {row['message']}"
        )

        kb = reply_ticket(row['id'], row['user_id'])

        if row['photo_id']:
            await call.message.answer_photo(
                photo=row['photo_id'],
                caption=text,
                reply_markup=kb,
                parse_mode="HTML"
            )
        else:
            await call.message.answer(
                text,
                reply_markup=kb,
                parse_mode="HTML"
            )


# ─── Отвеченные тикеты — список с кнопками + пагинация ─────────────────────

@router.callback_query(F.data.startswith("tickets_answered:"))
async def tickets_answered(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        return

    page = int(call.data.split(":")[1])
    offset = page * PAGE_SIZE

    async with get_connection() as conn:
        total = await conn.fetchval(
            "SELECT COUNT(*) FROM support WHERE status = 'answered'"
        )
        rows = await conn.fetch(
            """
            SELECT t.id, t.user_id, t.created_at, u.username
            FROM support t
            LEFT JOIN users u ON u.telegram_id = t.user_id
            WHERE t.status = 'answered'
            ORDER BY t.created_at DESC
            LIMIT $1 OFFSET $2
            """,
            PAGE_SIZE, offset
        )

    if not rows:
        await call.answer("📭 Отвеченных тикетов нет", show_alert=True)
        return

    await call.answer()

    buttons_data = [
        (
            row['id'],
            f"@{row['username']}" if row['username'] else "без username",
            to_local(row['created_at']) #row['created_at'].strftime("%d.%m %H:%M")
        )
        for row in rows
    ]

    text = (
        f"✅ <b>Отвеченные тикеты ({total})</b>\n\n"
        "Здесь хранятся обработанные обращения. "
        "Можете вернуться к ним при необходимости.\n\n"
        "Выберите тикет:"
    )

    kb = tickets_list(buttons_data, page, total, PAGE_SIZE)
    await _show_ticket_list(call, text, kb)

# ─── Просмотр конкретного тикета ───────────────────────────────────────────

@router.callback_query(F.data.startswith("ticket_view:"))
async def view(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        return

    await call.answer()

    parts = call.data.split(":")
    ticket_id = int(parts[1])
    back_page = int(parts[2]) if len(parts) > 2 else 0

    async with get_connection() as conn:
        row = await conn.fetchrow(
            """
            SELECT t.id, t.user_id, t.message, t.created_at, t.status, t.reply, t.photo_id, u.username, u.balance
            FROM support t
            LEFT JOIN users u ON u.telegram_id = t.user_id
            WHERE t.id = $1
            """,
            ticket_id
        )

    if not row:
        await call.answer("❌ Тикет не найден", show_alert=True)
        return

    balance = row["balance"] if row["balance"] is not None else 0
    username = f"@{row['username']}" if row['username'] else "без username"
    date = to_local(row['created_at']) 
    status = "✅ Отвечен" if row['status'] == 'answered' else "⚠️ Открыт"
    reply_part = f"\n\n📩 <b>Ответ админа:</b>\n{row['reply']}" if row['reply'] else ""

    text = (
        f"<b>Тикет #{row['id']}</b>\n"
        f"👤 {username}\n"
        f"💰 Баланс: {balance} ₽\n"
        f"📅 {date}\n"
        f"{status}\n\n"
        f"💬 {row['message']}"
        f"{reply_part}"
    )

    kb = ticket_view(row['id'], row['user_id'], back_page)

    if row['photo_id']:
        # Сообщение с фото нельзя отредактировать в текстовое — удаляем и шлём заново
        try:
            await call.message.delete()
        except Exception:
            pass
        await call.message.answer_photo(
            photo=row['photo_id'],
            caption=text,
            reply_markup=kb,
            parse_mode="HTML"
        )
    else:
        await _show_ticket_list(call, text, kb)


# ─── Админ нажал "Ответить" ─────────────────────────────────────────────────

@router.callback_query(F.data.startswith("reply_ticket:"))
async def admin_reply_start(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id):
        return

    _, ticket_id, user_id = call.data.split(":")
    await state.update_data(
        ticket_id=int(ticket_id),
        user_id=int(user_id),
        ticket_message_id=call.message.message_id
    )
    await state.set_state(AdminReplyFSM.waiting_reply)

    await call.answer()
    await call.message.answer(
        f"✏️ Пишите ответ на тикет <b>#{ticket_id}</b>:",
        parse_mode="HTML"
    )


# ─── Админ написал ответ ────────────────────────────────────────────────────

@router.message(AdminReplyFSM.waiting_reply)
async def admin_reply_send(message: Message, state: FSMContext, bot: Bot):
    if not is_admin(message.from_user.id):
        return

    data = await state.get_data()
    await state.clear()

    ticket_id = data["ticket_id"]
    user_id = data["user_id"]
    ticket_message_id = data.get("ticket_message_id")

    answer_text = message.text

    async with get_connection() as conn:
        await conn.execute(
            "UPDATE support SET status = 'answered', reply = $1 WHERE id = $2",
            message.text, ticket_id
        )

    delivered = True
    try:
        await bot.send_message(
            user_id,
            f"📨 <b>Ответ по обращению #{ticket_id}:</b>\n\n{answer_text}\n\n"
            f"<i>Если ответ не решил ваш вопрос — можете написать администратору напрямую.</i>",
            reply_markup=ticket_answer(ADMIN_USERNAME),
            parse_mode="HTML"
        )
    except Exception as e:
        delivered = False
        logger.warning(f"Не удалось доставить ответ по тикету #{ticket_id} юзеру {user_id}: {e}")

    status_line = "— закрыт" if delivered else ""
    error_line = (
        "" if delivered
        else "\n\n⚠️ Ошибка: не удалось доставить (пользователь заблокировал бота или недоступен)"
    )

    if ticket_message_id:
        try:
            await bot.delete_message(message.chat.id, ticket_message_id)
        except Exception:
            pass

    logger.info(f"Админ ответил на тикет #{ticket_id}, доставлено={delivered}")

    await message.answer(
        f"✅ Ответ успешно отправлен\n"
        f"├ Тикет: <b>#{ticket_id}</b> {status_line}\n"
        f"╰ Ошибок: {'0' if delivered else '1'}{error_line}",
        parse_mode="HTML"
    )