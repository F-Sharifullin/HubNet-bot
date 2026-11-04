from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder


# Кнопка "Ответить" для админа когда приходит от пользователя
def reply_ticket(ticket_id: int, user_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(
            text="✉️ Ответить",
            callback_data=f"reply_ticket:{ticket_id}:{user_id}"
        )
    ]])


def tickets_menu() -> InlineKeyboardMarkup:
    """Меню раздела '📩 Тикеты' — выбор открытых/отвеченных."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="⚠️ Открытые", callback_data="tickets_open"),
            InlineKeyboardButton(text="✅ Отвеченные", callback_data="tickets_answered:0"),
        ],
        [InlineKeyboardButton(text="🚪 Выйти", callback_data="tickets_exit")]
    ])


def tickets_list(buttons_data: list[tuple[int, str, str]], page: int, total: int,
                             page_size: int) -> InlineKeyboardMarkup:
    """
    Список отвеченных тикетов с пагинацией.
    buttons_data: список (ticket_id, username, date_str)
    """
    buttons = []
    for ticket_id, username, date_str in buttons_data:
        buttons.append([
            InlineKeyboardButton(
                text=f"#{ticket_id} — {username} — {date_str}",
                callback_data=f"ticket_view:{ticket_id}:{page}"
            )
        ])

    nav = []
    offset = page * page_size
    if page > 0:
        nav.append(InlineKeyboardButton(text="⬅️", callback_data=f"tickets_answered:{page - 1}"))
    else:
        nav.append(InlineKeyboardButton(text="🔙 Назад", callback_data="tickets_back"))
    if offset + page_size < total:
        nav.append(InlineKeyboardButton(text="➡️", callback_data=f"tickets_answered:{page + 1}"))
    if nav:
        buttons.append(nav)

    return InlineKeyboardMarkup(inline_keyboard=buttons)


def ticket_view(ticket_id: int, user_id: int, back_page: int = 0) -> InlineKeyboardMarkup:
    """Кнопки для просмотра конкретного тикета — Ответить / Назад к списку."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✉️ Написать сообщение", callback_data=f"reply_ticket:{ticket_id}:{user_id}")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data=f"tickets_answered:{back_page}")],
    ])


def ticket_answer(admin_username: str) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="👤 Написать Администратору", url=f"https://t.me/{admin_username}")
    return kb.as_markup()