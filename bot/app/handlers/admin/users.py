import html
import logging

from aiogram import Bot, F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message

from bot.app.database import (
    add_balance_and_enable_if_needed,
    delete_subscription,
    find_user_by_query,
    get_days_left,
    get_subscription,
    get_user,
    get_user_card_data,
    get_user_subscriptions,
)
from bot.app.database.tariffs import TARIFFS
from bot.app.handlers.admin.panel import is_admin
from bot.app.handlers.user.fortune import get_latest_fortune_spin
from bot.app.keyboards.admin import (
    admin_device_menu,
    admin_devices,
    search_cancel,
    user_card,
)
from bot.app.services.panel import x3ui
from bot.app.utils import to_local
from bot.config import SUB_PATH, SUB_PORT, SUB_URL

router = Router()
logger = logging.getLogger(__name__)


class AdminUserSearchFSM(StatesGroup):
    waiting_query = State()


class AdminTopupFSM(StatesGroup):
    waiting_amount = State()


class AdminMessageFSM(StatesGroup):
    waiting_text = State()


DEVICE_NAMES = {
    "android": "📱 Android",
    "ios": "📱 IOS",
    "computer": "💻 Компьютер",
}


# ====================== КАРТОЧКА ПОЛЬЗОВАТЕЛЯ ======================
async def build_user_card(telegram_id: int) -> str | None:
    data = await get_user_card_data(telegram_id)
    user = await get_user(telegram_id)
    if not data or not user:
        return None

    tariff = TARIFFS[user["tariff"]]
    used = data["device_count"]
    balance = user["balance"]

    username = f"@{data['username']}" if data["username"] else "без username"
    name = html.escape(data["name"] or "Без имени")

    days_left = None
    if used:
        days_left = await get_days_left(telegram_id, balance)
    days_text = str(days_left) if days_left is not None else "—"

    over_limit = " ⚠️ превышен лимит" if used > tariff.max_keys else ""

    referrer_text = str(data["referrer_id"]) if data["referrer_id"] else "—"
    created = to_local(data["created"])
    last_topup = to_local(data["last_topup"])
    status = "Активен ✅" if balance > 0 else "Отключён ❌"

    # Последняя прокрутка колеса фортуны
    spin = await get_latest_fortune_spin(telegram_id)
    if spin is None:
        fortune_text = "🎁 Бонуса: нет"
    elif spin["activated"]:
        fortune_text = (
            f"🎁 Бонус: {spin['prize_full']}\n"
            f" ╰ ✅ Активирован"
        )
    else:
        fortune_text = (
            f"🎁 Бонус: {spin['prize_full']}\n"
            f" ╰ ⏳ Не активирован"
        )

    return (
        f"👤 {name}\n\n"
        f"🆔 ID: {data['telegram_id']}\n"
        f"👤 Username: {username}\n\n"
        f"💰 Баланс: {balance:.0f} ₽\n"
        f"📅 Дней осталось: {days_text}\n"
        f"📦 Тариф: {tariff.title} — {tariff.monthly_price:.0f} ₽/мес\n"
        f"🔢 Устройств: {used}/{tariff.max_keys}{over_limit}\n\n"
        f"👥 Реферер: {referrer_text}\n"
        f"📈 Привёл рефералов: {data['referrals']}\n\n"
        f"🕒 Зарегистрирован: {created}\n"
        f"💳 Последнее пополнение: {last_topup}\n\n"
        f"{fortune_text}\n\n"
        f"📌 Статус: {status}"
    )


async def show_user_card(callback: CallbackQuery, telegram_id: int, edit: bool = False):
    text = await build_user_card(telegram_id)
    if not text:
        await callback.answer("❌ Пользователь не найден.", show_alert=True)
        return

    if edit:
        try:
            await callback.message.edit_text(text, reply_markup=user_card(telegram_id), parse_mode="HTML")
            return
        except TelegramBadRequest:
            pass

    await callback.message.answer(text, reply_markup=user_card(telegram_id), parse_mode="HTML")


# ====================== ПОИСК ПОЛЬЗОВАТЕЛЯ ======================
@router.callback_query(F.data == "admin_search_user")
async def search_user_start(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        return
    await callback.answer()
    await state.set_state(AdminUserSearchFSM.waiting_query)
    await state.update_data(session_message_ids=[])
    await callback.message.answer(
        "🔍 Введите Telegram ID, username пользователя или remark устройства:",
        reply_markup=search_cancel()
    )


@router.message(AdminUserSearchFSM.waiting_query)
async def search_user_receive(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    # состояние НЕ сбрасываем — ждём следующий ID/remark, пока не нажмут «Отмена»
    # на самом первом сообщении с запросом (там кнопка «Отмена» уже висит)

    data = await state.get_data()
    session_ids = data.get("session_message_ids", [])
    session_ids.append(message.message_id)  # твоё введённое сообщение

    telegram_id = await find_user_by_query(message.text)
    if not telegram_id:
        notice = await message.answer("❌ Пользователь не найден.")
        session_ids.append(notice.message_id)
        await state.update_data(session_message_ids=session_ids)
        return

    text = await build_user_card(telegram_id)
    if not text:
        notice = await message.answer("❌ Пользователь не найден.")
        session_ids.append(notice.message_id)
        await state.update_data(session_message_ids=session_ids)
        return
    
    card = await message.answer(text, reply_markup=user_card(telegram_id), parse_mode="HTML")
    session_ids.append(card.message_id)
    await state.update_data(session_message_ids=session_ids)


@router.callback_query(F.data == "adm_search_cancel")
async def search_user_cancel(callback: CallbackQuery, state: FSMContext, bot: Bot):
    if not is_admin(callback.from_user.id):
        return

    data = await state.get_data()
    session_ids = data.get("session_message_ids", [])
    chat_id = callback.message.chat.id

    await state.clear()
    await callback.answer("Отменено")

    for msg_id in session_ids:
        try:
            await bot.delete_message(chat_id, msg_id)
        except TelegramBadRequest:
            pass

    try:
        await callback.message.delete()
    except TelegramBadRequest:
        pass


# ====================== УСТРОЙСТВА (для админа) ======================
@router.callback_query(F.data.startswith("adm_devs:"))
async def devices(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        return

    telegram_id = int(callback.data.split(":")[1])
    subs = await get_user_subscriptions(telegram_id)

    if not subs:
        await callback.answer("У пользователя нет устройств", show_alert=True)
        return

    await callback.answer()
    try:
        await callback.message.edit_text(
            "📱 Устройства пользователя:",
            reply_markup=admin_devices(subs, telegram_id),
        )
    except TelegramBadRequest:
        msg = await callback.message.answer(
            "📱 Устройства пользователя:",
            reply_markup=admin_devices(subs, telegram_id),
        )
        data = await state.get_data()
        session_ids = data.get("session_message_ids", [])
        session_ids.append(msg.message_id)
        await state.update_data(session_message_ids=session_ids)


def build_admin_device_text(sub: dict, sub_id: str) -> str:
    """Формирует текст карточки устройства для админа — с ключом, как видит клиент."""
    device_name = DEVICE_NAMES.get(sub["device"], sub["device"])
    sub_link = f"{SUB_URL}:{SUB_PORT}{SUB_PATH}{sub_id}"

    return (
        f"<b>{sub['remark']}</b>\n"
        f"Тип устройства: {device_name}\n\n"
        "Ключ пользователя:\n"
        f"<pre>{sub_link}</pre>"
    )


@router.callback_query(F.data.startswith("adm_device:"))
async def device_menu(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        return

    _, sub_id, telegram_id = callback.data.split(":")
    telegram_id = int(telegram_id)
    sub = await get_subscription(sub_id)

    if not sub:
        await callback.answer("❌ Устройство не найдено", show_alert=True)
        return

    await callback.answer()
    text = build_admin_device_text(sub, sub_id)

    try:
        await callback.message.edit_text(
            text,
            reply_markup=admin_device_menu(sub_id, telegram_id),
            parse_mode="HTML",
        )
    except TelegramBadRequest:
        msg = await callback.message.answer(
            text,
            reply_markup=admin_device_menu(sub_id, telegram_id),
            parse_mode="HTML",
        )
        data = await state.get_data()
        session_ids = data.get("session_message_ids", [])
        session_ids.append(msg.message_id)
        await state.update_data(session_message_ids=session_ids)


# УДАЛЕНИЕ ПОДПИСКИ
@router.callback_query(F.data.startswith("adm_dev_del:"))
async def admin_device_delete(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        return

    _, sub_id, telegram_id_str = callback.data.split(":")
    telegram_id = int(telegram_id_str)

    sub = await get_subscription(sub_id)
    if sub:
        deleted = await x3ui.delete_client(sub["uuid"], sub["remark"])
        if deleted:
            await delete_subscription(sub_id)
        else:
            await callback.answer("❌ Ошибка удаления в панели. Попробуйте позже", show_alert=True)
            return

    await callback.answer("✅ Устройство удалено.")

    subs = await get_user_subscriptions(telegram_id)
    if subs:
        try:
            await callback.message.edit_text(
                "📱 Устройства пользователя:",
                reply_markup=admin_devices(subs, telegram_id),
            )
        except TelegramBadRequest:
            msg = await callback.message.answer(
                "📱 Устройства пользователя:",
                reply_markup=admin_devices(subs, telegram_id),
            )
            data = await state.get_data()
            session_ids = data.get("session_message_ids", [])
            session_ids.append(msg.message_id)
            await state.update_data(session_message_ids=session_ids)
    else:
        await show_user_card(callback, telegram_id, edit=True)


# ОТКЛЮЧЕНИЕ ПОДПИСКИ
@router.callback_query(F.data.startswith("adm_dev_off:"))
async def admin_device_disable(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        return

    _, sub_id, telegram_id = callback.data.split(":")
    telegram_id = int(telegram_id)
    sub = await get_subscription(sub_id)

    if not sub:
        await callback.answer("❌ Устройство не найдено.", show_alert=True)
        return

    ok = await x3ui.disable_client(sub["uuid"], sub["remark"], sub_id)
    if not ok:
        await callback.answer("❌ Ошибка отключения в панели.", show_alert=True)
        return

    await callback.answer("🔌 Устройство отключено.")
    text = build_admin_device_text(sub, sub_id)
    try:
        await callback.message.edit_text(
            text,
            reply_markup=admin_device_menu(sub_id, telegram_id),
            parse_mode="HTML",
        )
    except TelegramBadRequest as e:
        if "message is not modified" in str(e):
            pass
        else:
            msg = await callback.message.answer(
                text,
                reply_markup=admin_device_menu(sub_id, telegram_id),
                parse_mode="HTML",
            )
            data = await state.get_data()
            session_ids = data.get("session_message_ids", [])
            session_ids.append(msg.message_id)
            await state.update_data(session_message_ids=session_ids)


# КНОПКА НАЗАД
@router.callback_query(F.data.startswith("adm_user_back:"))
async def admin_user_back(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        return
    telegram_id = int(callback.data.split(":")[1])
    await callback.answer()
    await show_user_card(callback, telegram_id, edit=True)


# ====================== ПОПОЛНЕНИЕ ======================
@router.callback_query(F.data.startswith("adm_topup:"))
async def admin_topup_start(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        return
    telegram_id = int(callback.data.split(":")[1])

    data = await state.get_data()
    session_ids = data.get("session_message_ids", [])

    await state.set_state(AdminTopupFSM.waiting_amount)
    await callback.answer()

    prompt = await callback.message.answer("💰 Введите сумму пополнения в рублях (целое число):")
    session_ids.append(prompt.message_id)

    await state.update_data(telegram_id=telegram_id, session_message_ids=session_ids)


@router.message(AdminTopupFSM.waiting_amount)
async def admin_topup_receive(message: Message, state: FSMContext, bot: Bot):
    if not is_admin(message.from_user.id):
        return

    data = await state.get_data()
    session_ids = data.get("session_message_ids", [])
    session_ids.append(message.message_id)

    try:
        amount = int(message.text.strip())
        if amount <= 0:
            raise ValueError
    except ValueError:
        notice = await message.answer("❌ Введите целое положительное число.")
        session_ids.append(notice.message_id)
        await state.update_data(session_message_ids=session_ids)
        return

    telegram_id = data["telegram_id"]
    await add_balance_and_enable_if_needed(telegram_id, amount)
    user = await get_user(telegram_id)
    new_balance = user["balance"] if user else amount

    try:
        await bot.send_message(
            telegram_id,
            f"💰 Администратор пополнил ваш баланс на {amount} ₽\n"
            f"Текущий баланс: {new_balance:.0f} ₽",
        )
    except Exception as e:
        logger.warning("Не удалось уведомить пользователя %s о пополнении: %s", telegram_id, e)

    confirm = await message.answer(
        f"✅ Баланс успешно пополнен!\n"
        f"├ Пользователь: {telegram_id}\n"
        f"├ Сумма: +{amount} ₽\n"
        f"╰ Текущий баланс: {new_balance:.0f} ₽",
        parse_mode="HTML",
    )
    session_ids.append(confirm.message_id)

    await state.set_state(AdminUserSearchFSM.waiting_query)
    await state.update_data(session_message_ids=session_ids)


# ====================== СООБЩЕНИЕ ПОЛЬЗОВАТЕЛЮ ======================

@router.callback_query(F.data.startswith("adm_msg:"))
async def admin_message_start(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        return
    telegram_id = int(callback.data.split(":")[1])

    data = await state.get_data()
    session_ids = data.get("session_message_ids", [])

    await state.set_state(AdminMessageFSM.waiting_text)
    await callback.answer()

    prompt = await callback.message.answer("✉️ Введите текст сообщения для отправки пользователю:")
    session_ids.append(prompt.message_id)

    await state.update_data(telegram_id=telegram_id, session_message_ids=session_ids)


@router.message(AdminMessageFSM.waiting_text)
async def admin_message_send(message: Message, state: FSMContext, bot: Bot):
    if not is_admin(message.from_user.id):
        return

    data = await state.get_data()
    session_ids = data.get("session_message_ids", [])
    session_ids.append(message.message_id)
    telegram_id = data["telegram_id"]

    try:
        await bot.send_message(telegram_id, message.text)
        text = (
            "✅ Сообщение отправлено!\n"
            f"├ Получатель: {telegram_id}\n"
            "╰ Статус: доставлено."
        )
    except Exception as e:
        logger.warning("Не удалось отправить сообщение пользователю %s: %s", telegram_id, e)
        text = (
            "❌ Сообщение не отправлено!\n"
            f"├ Получатель: {telegram_id}\n"
            "╰ Статус: пользователь недоступен."
        )

    confirm = await message.answer(text)
    session_ids.append(confirm.message_id)

    await state.set_state(AdminUserSearchFSM.waiting_query)
    await state.update_data(session_message_ids=session_ids)