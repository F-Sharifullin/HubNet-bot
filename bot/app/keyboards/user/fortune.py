from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

fortune_luck = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="🎰 Испытать удачу", callback_data="wheel_spin")]
])


def claim() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎁 Забрать приз", callback_data="wheel_claim")]
    ])


def activate() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔑 Активировать", callback_data="wheel_activate")]
    ])