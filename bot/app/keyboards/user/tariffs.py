from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

_TARIFF_BUTTONS = (
    ("START", "🟢 START"),
    ("STANDARD", "🔵 STANDARD"),
    ("PREMIUM", "🟣 PREMIUM"),
)


def plan_tariffs(ctx: str = "chg", current: str | None = None) -> InlineKeyboardMarkup:
    rows = []
    buttons = []

    for key, label in _TARIFF_BUTTONS:
        text = f"{label} (Текущий тариф)" if key == current else label

        buttons.append(
            InlineKeyboardButton(
                text=text,
                callback_data=f"tariff_pick:{key}:{ctx}"
            )
        )

    if current:
        buttons.sort(key=lambda button: button.callback_data.split(":")[1] != current)

    rows.append([buttons[0]])
    rows.append(buttons[1:])

    rows.append([
        InlineKeyboardButton(
            text="🚪 Выйти",
            callback_data="tariff_cancel"
        )
    ])

    return InlineKeyboardMarkup(inline_keyboard=rows)


change_tariff = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="🔄 Сменить тариф", callback_data="change_tariff")]
])


def tariff_downgrade(cheaper) -> InlineKeyboardMarkup:
    """Предложение перейти на более дешёвый тариф после удаления устройства."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text=f"⬇️ Перейти на {cheaper.title} — {int(cheaper.monthly_price)}₽/мес",
            callback_data=f"tariff_pick:{cheaper.name}:chg",
        )],
        [InlineKeyboardButton(text="Остаться на текущем", callback_data="tariff_cancel")],
    ])