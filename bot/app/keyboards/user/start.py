from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

start = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text='🎉Подключить VPN🎉', callback_data='connect_vpn')]
])


def connect_vpn(happ_link: str):
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🚀 Подключить VPN", url=happ_link)]
        ]
    )
    return keyboard


def apps_keyboard(happ_link: str, incy_link: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="Happ", url=happ_link),
                InlineKeyboardButton(text="INCY", url=incy_link),
            ]
        ]
    )