from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


def promo_menu() -> InlineKeyboardMarkup:
    """Главное меню раздела «🎟 Промокоды»."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="➕ Создать", callback_data="apromo_create"),
            InlineKeyboardButton(text="📋 Список", callback_data="apromo_list:0"),
        ],
        [InlineKeyboardButton(text="🚪 Выйти", callback_data="apromo_exit")],
    ])

def promo_create_code() -> InlineKeyboardMarkup:
    """Шаг 1 создания: ввод кода или генерация."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎲 Сгенерировать", callback_data="apromo_gen")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="apromo_back")],
    ])

def promo_confirm() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Создать", callback_data="apromo_confirm"),
            InlineKeyboardButton(text="❌ Отмена", callback_data="apromo_cancel"),
        ]
    ])

def promo_list(
    items: list[tuple[int, str]], page: int, total: int, page_size: int
) -> InlineKeyboardMarkup:
    """
    Список промокодов с пагинацией.
    items: список (promo_id, текст_кнопки)
    """
    buttons = [
        [InlineKeyboardButton(text=text, callback_data=f"apromo_view:{promo_id}:{page}")]
        for promo_id, text in items
    ]

    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton(text="⬅️", callback_data=f"apromo_list:{page - 1}"))
    else:
        nav.append(InlineKeyboardButton(text="🔙 Назад", callback_data="apromo_back"))
    if (page + 1) * page_size < total:
        nav.append(InlineKeyboardButton(text="➡️", callback_data=f"apromo_list:{page + 1}"))
    buttons.append(nav)

    return InlineKeyboardMarkup(inline_keyboard=buttons)

def promo_card(promo_id: int, is_active: bool, page: int) -> InlineKeyboardMarkup:
    toggle_text = "⛔️ Отключить" if is_active else "✅ Включить"
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text=toggle_text, callback_data=f"apromo_toggle:{promo_id}:{page}"),
            InlineKeyboardButton(text="🗑 Удалить", callback_data=f"apromo_del:{promo_id}:{page}"),
        ],
        [InlineKeyboardButton(text="🔙 Назад", callback_data=f"apromo_list:{page}")],
    ])

def promo_delete_confirm(promo_id: int, page: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Да, удалить", callback_data=f"apromo_delok:{promo_id}:{page}"),
            InlineKeyboardButton(text="❌ Отмена", callback_data=f"apromo_view:{promo_id}:{page}"),
        ]
    ])