import logging

import pytz
from aiogram import Bot
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from bot.app.database import (
    charge_all_users,
    get_users_for_low_balance_notify,
    set_low_balance_stage,
)
from bot.app.services import notify_low_balance_stage

logger = logging.getLogger(__name__)

moscow_tz = pytz.timezone("Europe/Moscow")


async def _charge_wrapper(bot: Bot):
    logger.info("🔄 Запуск списания средств")
    try:
        await charge_all_users(bot=bot)
        logger.info("✅ Списание завершено")
    except Exception:
        logger.exception("❌ Ошибка при списании средств")


async def _low_balance_notify(bot: Bot):
    logger.info("🔔 Проверка приближающегося окончания подписки")
    try:
        users = await get_users_for_low_balance_notify()
        for telegram_id, stage, days_left in users:
            sent = await notify_low_balance_stage(bot, telegram_id, stage, days_left)
            if sent:
                await set_low_balance_stage(telegram_id, stage)
        logger.info("✅ Уведомлено пользователей: %s", len(users))
    except Exception:
        logger.exception("❌ Ошибка при уведомлении об окончании подписки")


def start_scheduler(bot: Bot) -> AsyncIOScheduler:
    scheduler = AsyncIOScheduler(timezone=moscow_tz)

    # Списание каждый день в 00:00 по Москве
    scheduler.add_job(
        _charge_wrapper,
        CronTrigger(hour=0, minute=0, timezone=moscow_tz),
        args=[bot],
        id="charge_all_users",
        replace_existing=True,
        misfire_grace_time=3600,
    )

    # Уведомление о низком балансе каждый день
    scheduler.add_job(
        _low_balance_notify,
        trigger="cron",
        hour=18,
        minute=0,
        kwargs={"bot": bot}
    )

    scheduler.start()
    return scheduler