import logging

from aiogram import F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import CallbackQuery

from bot.app.database import get_user, set_tariff
from bot.app.database.tariffs import TARIFFS
from bot.app.handlers.user.start import _devices_word
from bot.app.keyboards.user import main_menu, plan_tariffs

router = Router()
logger = logging.getLogger(__name__)


@router.callback_query(F.data.in_({'tariffs_open', 'change_tariff'}))
async def tariff(callback: CallbackQuery):
    await callback.answer()

    user = await get_user(callback.from_user.id)
    if not user:
        return

    text = (
        "Выберите тариф, который подходит именно вам.\n\n"
        "🟢 <b>START</b> — 150₽ / мес\n"
        "├ Макс. устройств: 2\n"
        "╰ Трафик: без ограничений\n\n"
        "🔵 <b>STANDARD</b> — 250₽ / мес\n"
        "├ Макс. устройств: 4\n"
        "╰ Трафик: без ограничений\n\n"
        "🟣 <b>PREMIUM</b> — 350₽ / мес\n"
        "├ Макс. устройств: 6\n"
        "╰ Трафик: без ограничений\n\n"
        "Вы можете сменить тариф в любой момент."
    )
    await callback.message.answer(text, reply_markup=plan_tariffs('chg', user['tariff']), parse_mode='HTML')


@router.callback_query(F.data == 'tariff_cancel')
async def tariff_cancel(callback: CallbackQuery):
    await callback.answer()
    try:
        await callback.message.delete()
    except TelegramBadRequest:
        pass


@router.callback_query(F.data.startswith("tariff_pick:"))
async def pick_tariff(callback: CallbackQuery):
    _, name, _ctx = callback.data.split(":")

    if name not in TARIFFS:
        await callback.answer("❌ Неизвестный тариф", show_alert=True)
        return
    

    user = await get_user(callback.from_user.id)
    
    if name == user['tariff']:
        await callback.answer("✅ Этот тариф уже выбран", show_alert=True)
        return


    balance = user['balance']

    if balance <= 0:
        await callback.answer(
            "⚠️ Недостаточно средств.\n\n"
            "Для смены тарифа необходимо пополнить баланс.",
            show_alert=True,
        )
        return


    tariff = TARIFFS[name]

    if user["devices"] > tariff.max_keys:
        await callback.answer(
            f"❌ На тарифе {tariff.title} доступно устройств: {tariff.max_keys}, "
            f"а у вас {user['devices']}.\n\n"
            "Удалите лишние в разделе «Мои устройства» и попробуйте снова.",
            show_alert=True,
        )
        return

    await set_tariff(callback.from_user.id, name)
    await callback.answer("✅ Тариф успешно изменён", show_alert=True)

    logger.info(
        "Пользователь %s сменил тариф %s → %s",
        callback.from_user.id,
        user["tariff"],
        name,
    )

    try:
        await callback.message.delete()
    except TelegramBadRequest:
        pass


    used = user["devices"]
    free = max(tariff.max_keys - used, 0)

    text = (
        "✅ <b>Вы успешно сменили тариф!</b>\n\n"
        f"Ваш новый тариф — <b>{tariff.title}</b>\n"
        f"├ Стоимость: {int(tariff.monthly_price)}₽/мес.\n"
        f"├ Устройства: {used}/{tariff.max_keys} подключено\n"
        f"╰ Доступно: {free} {_devices_word(free)}\n\n"
        "👭 Пригласите друзей в наш сервис и получите 100₽ на баланс "
        "за каждого друга. Ваши друзья получат 150₽ на баланс!\n"
        '<blockquote>'
        "Найти подробности можно в разделе «Бонусы»" # ИЗМЕНЕНИЕ...
        '</blockquote>'
    )

    await callback.message.answer(text, reply_markup=main_menu, parse_mode='HTML')