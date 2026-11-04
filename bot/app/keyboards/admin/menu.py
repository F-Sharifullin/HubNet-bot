from aiogram.types import (
    KeyboardButton,
    ReplyKeyboardMarkup,
)

admin = ReplyKeyboardMarkup(
    keyboard=[
        [
            KeyboardButton(text="📩 Тикеты"),
            KeyboardButton(text="📢 Рассылка")
        ],
        [KeyboardButton(text="📊 Статистика")],
        [
            KeyboardButton(text="💰 Финансы"),
            KeyboardButton(text="🎟 Промокоды")
        ]
    ],
    resize_keyboard=True
)