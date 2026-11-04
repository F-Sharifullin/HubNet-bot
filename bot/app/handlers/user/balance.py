from aiogram import F, Router
from aiogram.types import CallbackQuery

from bot.app.database import get_days_left, get_user
from bot.app.keyboards.user import documents_menu, pay_menu

router = Router()


@router.callback_query(F.data == "balance")
async def show_balance(callback: CallbackQuery):
    await callback.answer()

    user = await get_user(callback.from_user.id)
    if not user:
        await callback.message.answer("Нажмите /start")
        return

    balance = user["balance"]
    days_left = await get_days_left(callback.from_user.id, balance)
    status = "аккаунт активен" if balance > 0 else "аккаунт неактивен"

    if days_left is not None:
        days_text = f"(~{days_left} дней)"
    else:
        days_text = "(нет активных устройств)"

    text = (
        f"<b>Ваш баланс: {balance}₽</b> {days_text}, {status}\n\n"
        "<b>Выберите способ платежа:</b>\n\n"
        "Мы рекомендуем платежи через Систему Быстрых Платежей (СБП), "
        "как наиболее удобные и не требующие ввода личных данных.\n\n"
        "Для платежа СБП у вас должно быть установлено приложение вашего банка."
    )
    await callback.message.answer(text, reply_markup=pay_menu, parse_mode="HTML")


@router.callback_query(F.data == "documents")
async def show_documents(callback: CallbackQuery):
    await callback.answer()

    text = (
        "📄 <b>Документы сервиса</b>\n\n"
        "Здесь вы можете ознакомиться с Политикой конфиденциальности "
        "и Пользовательским соглашением.\n\n"
        "Используя бот и совершая оплату, вы подтверждаете согласие с условиями указанных документов."
    )
    await callback.message.answer(text, reply_markup=documents_menu, parse_mode="HTML")