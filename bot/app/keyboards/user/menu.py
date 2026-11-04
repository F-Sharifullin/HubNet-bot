from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

main_menu = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="🗝 Мои устройства 📱💻", callback_data='my_devices')],
    [InlineKeyboardButton(text="💰 Пополнить баланс", callback_data='balance')],
    [
        InlineKeyboardButton(text="💎 Тарифы", callback_data='tariffs_open'),
        InlineKeyboardButton(text="🎁 Бонусы", callback_data='bonus_open'),
    ],
    [InlineKeyboardButton(text="💬 Поддержка",callback_data='support')]
])


# ПОКА НЕ ОБРАБАТЫВАЕТСЯ...
home_button = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="🏠 Главное меню", callback_data='menu')]
])


balance_menu = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="💰 Пополнить баланс", callback_data='balance')],
    [
        InlineKeyboardButton(text="💎 Тарифы", callback_data='tariffs_open'),
        InlineKeyboardButton(text="🎁 Бонусы", callback_data='bonus_open'),
    ]
])