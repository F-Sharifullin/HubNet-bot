from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

platform_choice = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="📱 Android", callback_data='android')],
    [InlineKeyboardButton(text="📱 IOS (iPhone, iPad)", callback_data='ios')],
    [InlineKeyboardButton(text="💻 Компьютер (Windows)", callback_data='windows')],
    [InlineKeyboardButton(text="📺 ТВ (Android)", callback_data='tv')]
])


device_button = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="➕ Добавить устройство", callback_data="devices")]
])


def devices_list(subs: list[dict]) -> InlineKeyboardMarkup:
    keyboard_buttons = []
    for sub in subs:
        keyboard_buttons.append([
            InlineKeyboardButton(
                text=f"🗝 {sub['remark']}",  # WH-AND783645
                callback_data=f"get_sub_{sub['sub_id']}"
            )
        ])

    keyboard_buttons.append([
        InlineKeyboardButton(text="➕ Добавить устройство", callback_data="devices")
    ])

    return InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)


def subscription_device(sub_id: str) -> InlineKeyboardMarkup:
    """Клавиатура под конфигурацией: Подключить + Удалить"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🔄 Заменить устр.", callback_data=f"replace_sub_{sub_id}"),
            InlineKeyboardButton(text="🗑 Удалить устр.", callback_data=f"delete_sub_{sub_id}")
        ],
        [InlineKeyboardButton(text="🚪Выйти", callback_data="cancel_settings")]
    ])


def confirm_delete(sub_id: str) -> InlineKeyboardMarkup:
    """Подтверждение удаления"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Да, удалить", callback_data=f"confirm_delete_{sub_id}"),
            InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_delete")
        ]
    ])


def execute_replace(sub_id: str) -> InlineKeyboardMarkup:
    """Подтверждение замены устройства"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Да, заменить", callback_data=f"confirm_replace_{sub_id}"),
            InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_replace")
        ]
    ])