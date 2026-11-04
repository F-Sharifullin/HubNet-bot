from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


def stats_search() -> InlineKeyboardMarkup:
    """Кнопка поиска под статистикой."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🔍 Поиск пользователя", callback_data="admin_search_user")]
        ]
    )


def user_card(telegram_id: int) -> InlineKeyboardMarkup:
    """Кнопки под карточкой (заглушки — дальше подключим их логику)."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="✉️ Написать", callback_data=f"adm_msg:{telegram_id}"),
                InlineKeyboardButton(text="📱 Устройства", callback_data=f"adm_devs:{telegram_id}"),

            ],
            [
                InlineKeyboardButton(text="💰 Пополнить", callback_data=f"adm_topup:{telegram_id}"),
            ],
        ]
    )

def search_cancel() -> InlineKeyboardMarkup:
    """Кнопка отмены под запросом ввода ID/remark."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="❌ Отмена", callback_data="adm_search_cancel")]
        ]
    )


def admin_devices(subs: list[dict], telegram_id: int) -> InlineKeyboardMarkup:
    """Список устройств пользователя (для админа)."""
    buttons = []
    for sub in subs:
        buttons.append(
            [
                InlineKeyboardButton(
                    text=f"🗝 {sub['remark']}",
                    callback_data=f"adm_device:{sub['sub_id']}:{telegram_id}",
                )
            ]
        )
    buttons.append(
        [InlineKeyboardButton(text="🔙 Назад", callback_data=f"adm_user_back:{telegram_id}")]
    )
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def admin_device_menu(sub_id: str, telegram_id: int) -> InlineKeyboardMarkup:
    """Меню конкретного устройства пользователя (для админа)."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🗑 Удалить", callback_data=f"adm_dev_del:{sub_id}:{telegram_id}"
                ),
                InlineKeyboardButton(
                    text="🔌 Отключить", callback_data=f"adm_dev_off:{sub_id}:{telegram_id}"
                ),
            ],
            [
                InlineKeyboardButton(
                    text="🔙 Назад", callback_data=f"adm_devs:{telegram_id}"
                )
            ]
        ]
    )