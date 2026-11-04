import asyncio
import logging

from aiogram import F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import CommandStart
from aiogram.types import CallbackQuery, Message

from bot.app.database import (
    create_user,
    get_days_left,
    get_user,
    one_bonus,
    referral_bonus,
)
from bot.app.database.tariffs import TARIFFS
from bot.app.keyboards.user import home_button, main_menu, platform_choice, start

router = Router()
logger = logging.getLogger(__name__)


def _devices_word(n: int) -> str:
    if n % 10 == 1 and n % 100 != 11:
        return "устройство"
    if 2 <= n % 10 <= 4 and not 12 <= n % 100 <= 14:
        return "устройства"
    return "устройств"


@router.message(CommandStart())
async def smd_start(message: Message):

    args = message.text.split()

    referrer_id = None
    if len(args) > 1:
        try:
            referrer_id = int(args[1])
        except ValueError:
            referrer_id = None

    user = await get_user(message.from_user.id)

    if not user:
        await create_user(
            telegram_id=message.from_user.id,
            username=message.from_user.username,
            name=message.from_user.full_name,
            referrer_id=referrer_id if referrer_id != message.from_user.id else None
        )

        text=(
            f"Привет, <b>{message.from_user.first_name}</b>!\n\n"
            "Подключите VPN бесплатно! Дарим вам 150₽ на баланс.\n\n"
            "🚀 Высокая скорость\n"
            "🌐 Доступ ко всем сайтам\n"
            "💳 Оплата картами РФ🇷🇺 и СБП\n"
            "💰 Самая низкая цена на рынке!\n\n"
            "Стоимость 150₽/мес за 2 устройства.\n"
            '<blockquote>'
            "💡 Тарифный план можно изменить в любое время в разделе «Тарифы»."
            '</blockquote>\n\n'
            "👭 Пригласите друзей в наш сервис и получите 100₽ на баланс за каждого друга. "
            "Ваши друзья получат 150₽ на баланс!\n\n"
            "⬇️Жмите кнопку⬇️"
            )
        await message.answer(text, reply_markup=start, parse_mode='HTML')

    else:
        
        balance = user['balance']
        status = "аккаунт активен" if balance > 0 else "аккаунт неактивен"
        days_left = await get_days_left(message.from_user.id, balance)

        if days_left is not None:
            days_text = f"(~{days_left} дней)"
        else:
            days_text = "(нет активных устройств)"

        tariff = TARIFFS[user['tariff']] or "Тариф не выбран"
        devices_count = user['devices']
        free = max(tariff.max_keys - devices_count, 0)

        text = (
            f"Рады видеть вас снова, <b>{message.from_user.first_name or 'Пользователь'}</b>!\n\n"
            f"<b>Ваш баланс: {balance}₽</b> {days_text}, {status}\n"
            f"<b>Тариф: {tariff.title} — {int(tariff.monthly_price)}₽/мес.</b>\n"
            f"├ Устройства: {devices_count}/{tariff.max_keys} подключено\n"
            f"╰ Доступно: {free} {_devices_word(free)}\n\n"
            "Настройки можно скачать повторно в разделе «<b>Мои устройства</b>», "
            "а тариф изменить в разделе «<b>Тарифы</b>».\n\n"
            "👭 Пригласите друзей в наш сервис и получите 100₽ на баланс "
            "за каждого друга. Ваши друзья получат 150₽ на баланс!\n"
        )
        await message.answer(text, reply_markup=main_menu, parse_mode='HTML')


@router.callback_query(F.data == 'connect_vpn')
async def connect_vpn(callback: CallbackQuery):

    user = await get_user(callback.from_user.id)

    if not user:
        await callback.answer("Нажмите /start", show_alert=True)
        return

    if user['bonus']:
        await callback.answer("✅ Вы уже получали бонус ранее", show_alert=True)
        return
    
    await callback.answer() # ОСТАВИЛ ТУТ
    await one_bonus(callback.from_user.id)

    if user['referrer_id']:
        referrer_id = user['referrer_id']

        was_activated = await referral_bonus(referrer_id)

        ref_user = await get_user(referrer_id)
        new_balance = int(ref_user["balance"]) if ref_user else 0

        try:
            await callback.bot.send_message(
                referrer_id,
                f"🎉 Ваш друг принял приглашение, вам добавлено 100₽ на баланс!\n"
                f"Текущий баланс: {new_balance}₽"
            )
        except TelegramBadRequest as e:
            logger.warning("Не удалось уведомить реферера %s: %s", referrer_id, e)

        if was_activated:
            await asyncio.sleep(2)
            try:
                text = (
                    "<b>🎉 Аккаунт успешно активирован!</b>\n"
                    "Вы можете использовать VPN на ваших устройствах!"
                    '<blockquote>'
                    "Управляйте подпиской и устройствами в разделе «<b>Главное меню</b>»."
                    '</blockquote>'
                )

                await callback.bot.send_message(
                    referrer_id,
                    text,
                    parse_mode='HTML',
                    reply_markup=home_button
                )
                
            except TelegramBadRequest as e:
                logger.warning("Не удалось уведомить реферера %s об активации: %s", referrer_id, e)

    text = (
        "🎉 Поздравляем! Вы активировали аккаунт HubNet, 150₽ у вас на балансе!\n\n"
        "Теперь давайте настроим ваш VPN. Выберите тип вашего устройства:"
    )
    await callback.message.answer(text, reply_markup=platform_choice)
