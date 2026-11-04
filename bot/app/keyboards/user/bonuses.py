from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

bonus_menu = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="👥 Пригласить друга", callback_data='referral')],
    [
        InlineKeyboardButton(text="🎟️ Промокод", callback_data='promo'),
        InlineKeyboardButton(text="🎰 Бонус месяца", callback_data='monthly_bonus')
    ],
    [InlineKeyboardButton(text="🚪 Выйти", callback_data='bonus_cancel')]
])


def invite_user(share_url: str):
    return InlineKeyboardMarkup(
        inline_keyboard=[
    [InlineKeyboardButton(text="📤 Поделиться", url=share_url)]
])