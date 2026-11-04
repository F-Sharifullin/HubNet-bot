import logging

from aiogram import F, Router
from aiogram.types import Message

from bot.app.database.admin import get_stats
from bot.app.keyboards.admin import stats_search
from bot.config import ADMIN_ID

router = Router()
logger = logging.getLogger(__name__)

def is_admin(user_id: int) -> bool:
    return str(user_id) == str(ADMIN_ID)

@router.message(F.text == "📊 Статистика")
async def admin_stats(message: Message):
    if not is_admin(message.from_user.id):
        return
    await message.delete()
    s = await get_stats()
    text = (
        "<b>Статистика пользователей</b>\n\n"
        "👤 <b>Пользователи</b>\n"
        f"├ Всего: {s['total_users']}\n"
        f"├ Активных: {s['active_users']}\n"
        f"╰  Отключено: {s['disabled_users']}\n\n"
        "📊 <b>Прирост</b>\n"
        f"├ Новые за 7 дней: {s['new_7d']}\n"
        f"╰  По рефералке: {s['from_referral']}\n\n"
        f"📱 Устройств в системе: {s['total_devices']}"
    )
    await message.answer(text, reply_markup=stats_search(), parse_mode="HTML")