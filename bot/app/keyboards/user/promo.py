from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

promo_cancel = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="🚪Выйти", callback_data='cancel')]
])