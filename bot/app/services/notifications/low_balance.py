import logging

from aiogram import Bot
from aiogram.exceptions import TelegramAPIError, TelegramForbiddenError

from bot.app.keyboards.user import balance_menu

logger = logging.getLogger(__name__)

STAGE_TEXTS = {
    1: (
        "⚠️ <b>Баланс скоро закончится.</b>\n\n"
        "Рекомендуем пополнить баланс заранее, чтобы не потерять доступ.\n\n"
        "👭 Пригласите друзей в наш сервис и получите 100₽ на баланс "
        "за каждого друга. Ваши друзья получат 150₽ на баланс!"
    ),
    2: (
        "❗️ <b>Осталось примерно {days} дня!</b>\n\n"
        "Баланс подходит к концу — пополните сейчас, чтобы VPN не отключился.\n\n"
        "👭 Пригласите друзей в наш сервис и получите 100₽ на баланс "
        "за каждого друга. Ваши друзья получат 150₽ на баланс!"
    ),
    3: (
        "‼️ <b>VPN отключится уже сегодня.</b>\n\n"
        "Срок действия вашего баланса подходит к концу.\n\n"
        "💳 Пополните баланс прямо сейчас, чтобы избежать отключения VPN.\n"
        '<blockquote>'
        "Нажмите кнопку «Пополнить баланс» и перейдите по ссылке для оплаты."
        '</blockquote>\n\n'
        "👭 Пригласите друзей в наш сервис и получите 100₽ на баланс "
        "за каждого друга. Ваши друзья получат 150₽ на баланс!"
    ),
}


async def notify_low_balance_stage(bot: Bot, telegram_id: int, stage: int, days_left: int) -> bool:
    text = STAGE_TEXTS[stage].format(days=days_left)
    try:
        await bot.send_message(
            chat_id=telegram_id,
            text=text,
            parse_mode="HTML",
            reply_markup=balance_menu
        )
        logger.info(
            "Уведомление (этап %s) отправлено пользователю %s",
            stage,
            telegram_id,
        )
        return True

    except TelegramForbiddenError:
        logger.warning(
            "Бот не может отправить сообщение пользователю %s",
            telegram_id,
        )
        return False

    except TelegramAPIError:
        logger.exception(
            "Ошибка Telegram API при отправке уведомления пользователю %s",
            telegram_id,
        )
        return False