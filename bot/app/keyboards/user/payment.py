from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from bot.config import PRIVACY_POLICY_URL, USER_AGREEMENT_URL

pay_menu = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="💳 Банковская карта", callback_data="pay")],
    [
        InlineKeyboardButton(text="🏦 СБП", callback_data="pay_rollypay"),
        InlineKeyboardButton(text="⭐️ Telegram Stars", callback_data="pay_stars")
    ],
    [InlineKeyboardButton(text="📄 Документы", callback_data="documents")]
])

documents_menu = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="📄 Политика конфиденциальности", url=PRIVACY_POLICY_URL)],
    [InlineKeyboardButton(text="📜 Пользовательское соглашение", url=USER_AGREEMENT_URL)],
])


#Rollypay
def topup_rollypay(amounts: list[int]) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text=f"{a}₽", callback_data=f"rollypay_topup_{a}")
            for a in amounts
        ]
    ])

def rollypay_pay(pay_url: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💳 Перейти к оплате", url=pay_url)]
    ])


def tribute_topup(amounts: list[int]) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text=f"{a}₽", callback_data=f"topup_{a}")
        for a in amounts
    ]])

def tribute_pay(pay_url: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💳 Перейти к оплате", url=pay_url)]
    ])