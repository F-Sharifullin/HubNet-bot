from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

support_cancel = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="🚪Выйти", callback_data='cancel')]
])