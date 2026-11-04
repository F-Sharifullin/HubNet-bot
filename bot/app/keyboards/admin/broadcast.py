from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

broadcast_audience = InlineKeyboardMarkup(inline_keyboard=[
    [
        InlineKeyboardButton(text="👥 Всем", callback_data="broadcast_target_all"),
        InlineKeyboardButton(text="📵 Отключённым", callback_data="broadcast_target_disabled")
    ],
    [InlineKeyboardButton(text="🚪 Выйти", callback_data="broadcast_exit")],
])

broadcast_confirm = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="✅ Отправить", callback_data="broadcast_confirm")],
    [InlineKeyboardButton(text="✏️ Редактировать", callback_data="broadcast_edit")],
    [InlineKeyboardButton(text="❌ Отмена", callback_data="broadcast_cancel")],
])