import html
import logging
from datetime import datetime

import pytz
from aiogram import Bot

from bot.config import ADMIN_ID

logger = logging.getLogger(__name__)

local_tz = pytz.timezone("Asia/Yekaterinburg")


async def notify_admin_payment(
    bot: Bot,
    telegram_id: int,
    amount: int,
    method: str,
    username: str | None = None,
    name: str | None = None,
) -> bool:
    """Отправляет админу мини-чек о поступившем платеже."""
    user_display = f"@{html.escape(username)}" if username else "без username"
    name_display = html.escape(name) if name else "Без имени"
    now = datetime.now(local_tz).strftime("%d.%m.%Y %H:%M")

    text = (
        "🧾 <b>Новый платёж</b>\n"
        "▫️▫️▫️▫️▫️▫️▫️▫️▫️▫️\n"
        f"💰  <b>{amount} ₽</b>\n"
        f"🏦  {method}\n\n"
        f"👤  {name_display}\n"
        f"🔗  {user_display}\n"
        f"🆔  <code>{telegram_id}</code>\n"
        "▫️▫️▫️▫️▫️▫️▫️▫️▫️▫️\n"
        f"🕒  {now}"
    )

    try:
        await bot.send_message(ADMIN_ID, text, parse_mode="HTML")
        return True
    except Exception as e:
        logger.error("Не удалось отправить админу уведомление о платеже: %s", e)
        return False