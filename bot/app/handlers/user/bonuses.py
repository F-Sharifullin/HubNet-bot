from aiogram import F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import CallbackQuery

from bot.app.keyboards.user import bonus_menu

router = Router()


@router.callback_query(F.data == 'bonus_cancel')
async def bonus_cancel(callback: CallbackQuery):
    await callback.answer()
    try:
        await callback.message.delete()
    except TelegramBadRequest:
        pass


@router.callback_query(F.data == 'bonus_open')
async def bonuses(callback: CallbackQuery):
    await callback.answer()

    text = (
        "Приглашайте друзей, вводите промокоды и выигрывайте призы!\n\n"
        "<b>👥 Пригласить друга</b>"
        '<blockquote>'
        "— Поделитесь ссылкой и получите 100 ₽ за каждого нового пользователя."
        '</blockquote>\n'
        "<b>🎟️ Активация промокода</b>\n"
        '<blockquote>'
        "— Введите специальный код, чтобы получить бонус или подарок."
        '</blockquote>\n'
        "<b>🎰 Бонус месяца</b>"
        '<blockquote>'
        "— Испытывайте удачу и выигрывайте бесплатные дни доступа или деньги на баланс."
        '</blockquote>\n'
    )
    await callback.message.answer(text, reply_markup=bonus_menu, parse_mode='HTML')