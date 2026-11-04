import hashlib
import hmac
import json
import logging
import time
import uuid

from aiogram import Bot, F, Router
from aiogram.types import CallbackQuery
from aiohttp import web

from bot.app.database import add_balance_and_enable_if_needed, get_user
from bot.app.database.tariffs import TARIFFS
from bot.app.keyboards.user import (
    home_button,
    rollypay_pay,
    topup_rollypay,
)
from bot.app.services.notifications import notify_admin_payment
from bot.app.services.rollypay import rollypay
from bot.config import ROLLYPAY_SIGNING_SECRET, ROLLYPAY_WEBHOOK_PATH

router = Router()
logger = logging.getLogger(__name__)


MONTH_OPTIONS = (1, 2, 3)


def topup_amounts(tariff_key) -> list[int]:
    """Суммы пополнения для тарифа: 1, 2, 3 месяца."""
    tariff = TARIFFS.get(tariff_key)
    if tariff is None:
        return []
    price = int(tariff.monthly_price)
    return [price * m for m in MONTH_OPTIONS]


SIGNATURE_MAX_AGE = 300  # 5 минут — защита от replay


@router.callback_query(F.data == "pay_rollypay")
async def pay_rollypay_menu(callback: CallbackQuery):
    await callback.answer()

    user = await get_user(callback.from_user.id)
    tariff = TARIFFS.get(user["tariff"])
    amounts = topup_amounts(user["tariff"])

    if tariff is None or not amounts:
        await callback.message.answer("Сначала выберите тариф в разделе «Тарифы».")
        return

    text = (
        f"<b>Тариф: {tariff.title} — {int(tariff.monthly_price)}₽/мес.</b>\n\n"
        "Пополнение баланса является однократной операцией (не подписка). "
        "Мы не имеем доступа к вашим личным и платежным данным.\n\n"
        "В случае возникновения проблем обращайтесь в чат поддержки.\n\n"
        f"<b>Ваш баланс: {user['balance']}₽.</b>\n\n"
        "Выберите сумму для пополнения баланса:"
    )
    await callback.message.answer(
        text, reply_markup=topup_rollypay(amounts), parse_mode="HTML"
    )


@router.callback_query(F.data.startswith("rollypay_topup_"))
async def create_rollypay_payment(callback: CallbackQuery):
    amount = int(callback.data.split("_")[-1])

    user = await get_user(callback.from_user.id)
    if not user or amount not in topup_amounts(user["tariff"]):
        await callback.answer("Неверная сумма", show_alert=True)
        return

    await callback.answer()


    # telegram_id зашит в order_id — из него же будем читать его в вебхуке
    order_id = f"rp_{callback.from_user.id}_{amount}_{uuid.uuid4().hex[:8]}"

    payment = await rollypay.create_payment(
        amount=f"{amount}.00",
        order_id=order_id,
        description=f"Пополнение баланса HubNet на {amount}₽",
    )

    if not payment or not payment.get("pay_url"):
        await callback.message.answer(
            "❌ Не удалось создать платёж. Попробуйте позже или выберите другой способ оплаты."
        )
        return

    text = (
        f"<b>Пополнение на {amount}₽</b>\n\n"
        "Нажмите кнопку ниже — откроется страница оплаты.\n"
        "После оплаты баланс пополнится автоматически."
    )
    await callback.message.answer(
        text, reply_markup=rollypay_pay(payment["pay_url"]), parse_mode="HTML"
    )


# ====================== Вебхук ======================

def _verify_signature(body: bytes, timestamp: str, signature: str) -> bool:
    if not timestamp or not signature:
        return False

    try:
        if abs(time.time() - int(timestamp)) > SIGNATURE_MAX_AGE:
            logger.warning("RollyPay: вебхук с устаревшим timestamp %s", timestamp)
            return False
    except ValueError:
        return False

    expected = hmac.new(
        key=ROLLYPAY_SIGNING_SECRET.encode(),
        msg=f"{timestamp}.".encode() + body,
        digestmod=hashlib.sha256,
    ).hexdigest()

    return hmac.compare_digest(expected, signature)


def _parse_telegram_id(order_id: str) -> int | None:
    """order_id формата rp_{telegram_id}_{amount}_{suffix}"""
    try:
        parts = order_id.split("_")
        if parts[0] != "rp":
            return None
        return int(parts[1])
    except (IndexError, ValueError):
        return None


async def rollypay_webhook_handler(request: web.Request) -> web.Response:
    body = await request.read()

    signature = request.headers.get("X-Signature", "")
    timestamp = request.headers.get("X-Timestamp", "")

    if not _verify_signature(body, timestamp, signature):
        logger.warning("RollyPay: неверная подпись вебхука")
        return web.Response(status=403, text="Invalid signature")

    try:
        data = json.loads(body)
    except Exception:
        return web.Response(status=400, text="Bad JSON")

    logger.info("RollyPay webhook: %s", json.dumps(data, ensure_ascii=False))

    event_type = data.get("event_type")
    status = data.get("status")

    # refund_request.completed дублирует payment.refunded — их не обрабатываем,
    # интересует только успешная оплата
    if event_type != "payment.paid" or status != "paid":
        return web.Response(status=200, text="ok")

    order_id = data.get("order_id", "")
    payment_id = data.get("payment_id")
    telegram_id = _parse_telegram_id(order_id)

    if not telegram_id:
        logger.warning("RollyPay: не удалось извлечь telegram_id из order_id=%s", order_id)
        return web.Response(status=200, text="ok")

    # Доп. проверка статуса через API — на случай подделки/устаревшего колбэка
    if payment_id:
        payment = await rollypay.get_payment(payment_id)
        if not payment or payment.get("status") != "paid":
            logger.warning("RollyPay: платёж %s не подтверждён при проверке через API", payment_id)
            return web.Response(status=200, text="ok")

    try:
        rubles = int(float(data.get("amount", 0)))
    except (TypeError, ValueError):
        rubles = 0

    if rubles <= 0:
        return web.Response(status=200, text="ok")

    was_activated = await add_balance_and_enable_if_needed(telegram_id, rubles)
    user = await get_user(telegram_id)

    bot: Bot = request.app["bot"]

    await notify_admin_payment(
        bot=request.app["bot"],
        telegram_id=telegram_id,
        amount=rubles,
        method="RollyPay (СБП)",
        username=user["username"] if user else None,
        name=user["name"] if user else None,
    )

    try:
        await bot.send_message(
            chat_id=telegram_id,
            text=(
                f"✅ Получен платёж {rubles}₽,\n"
                f"Ваш баланс: {user['balance']}₽.\n"
                "Спасибо, что остаётесь с нами!"
            ),
        )
        if was_activated:
            await bot.send_message(
                chat_id=telegram_id,
                text=(
                    "<b>🎉 Аккаунт успешно активирован!</b>\n"
                    "Вы можете использовать VPN на ваших устройствах!"
                    '<blockquote>'
                    "Управляйте подпиской и устройствами в разделе «<b>Главное меню</b>»."
                    '</blockquote>'
                ),
                reply_markup=home_button,
            )
    except Exception as e:
        logger.error("RollyPay: не удалось уведомить пользователя %s: %s", telegram_id, e)

    return web.Response(status=200, text="ok")


def register_rollypay_webhook(app: web.Application):
    """Вызвать при создании aiohttp-приложения в main.py"""
    app.router.add_post(ROLLYPAY_WEBHOOK_PATH, rollypay_webhook_handler)