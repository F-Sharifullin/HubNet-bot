import hashlib
import hmac
import json
import logging
from html import escape

from aiogram import Bot, F, Router
from aiogram.types import CallbackQuery
from aiohttp import web

from bot.app.database import add_balance_and_enable_if_needed, get_user
from bot.app.database.tariffs import TARIFFS
from bot.app.handlers.user.rollypay import topup_amounts
from bot.app.keyboards.user import home_button, tribute_pay, tribute_topup
from bot.config import TRIBUTE_API_KEY, TRIBUTE_LINKS, TRIBUTE_WEBHOOK_PATH

logger = logging.getLogger(__name__)
router = Router()


# ====================== Кнопки оплаты ======================

@router.callback_query(F.data == "pay")  # callback_data кнопки Tribute в pay_menu
async def pay_tribute_menu(callback: CallbackQuery):
    await callback.answer()

    user = await get_user(callback.from_user.id)
    if not user:
        await callback.message.answer("Нажмите /start")
        return

    tariff = TARIFFS.get(user["tariff"])
    all_amounts = topup_amounts(user["tariff"])
    amounts = [a for a in all_amounts if TRIBUTE_LINKS.get(a)]

    missing = [a for a in all_amounts if a not in amounts]
    if missing:
        logger.warning("Tribute: нет ссылок для сумм %s (тариф %s)", missing, user["tariff"])

    if tariff is None or not amounts:
        await callback.message.answer("Этот способ оплаты для вашего тарифа пока недоступен.")
        return

    text = (
        f"<b>Тариф: {escape(str(tariff.title))} — {int(tariff.monthly_price)}₽/мес.</b>\n\n"
        "Пополнение баланса является однократной операцией (не подписка). "
        "Мы не имеем доступа к вашим личным и платежным данным.\n\n"
        "В случае возникновения проблем обращайтесь в чат поддержки.\n\n"
        f"<b>Ваш баланс: {user['balance']}₽.</b>\n\n"
        "Выберите сумму для пополнения баланса:"
    )
    await callback.message.answer(text, reply_markup=tribute_topup(amounts), parse_mode="HTML")


@router.callback_query(F.data.startswith("topup_"))
async def create_tribute_payment(callback: CallbackQuery):
    try:
        amount = int(callback.data.split("_")[1])
    except (IndexError, ValueError):
        await callback.answer("Неверная сумма", show_alert=True)
        return

    user = await get_user(callback.from_user.id)
    pay_url = TRIBUTE_LINKS.get(amount)

    if not user or amount not in topup_amounts(user["tariff"]) or not pay_url:
        await callback.answer("Неверная сумма или ссылка не настроена", show_alert=True)
        return

    await callback.answer()

    text = (
        f"<b>Пополнение на {amount}₽</b>\n\n"
        "Нажмите кнопку ниже, откроется страница оплаты.\n"
        "После оплаты баланс пополнится автоматически."
    )
    await callback.message.answer(
    text, reply_markup=tribute_pay(pay_url), parse_mode="HTML"
)


# ====================== Вебхук ======================

def verify_tribute_signature(body: bytes, signature: str) -> bool:
    if not signature:
        return False
    expected = hmac.new(
        key=TRIBUTE_API_KEY.encode(),
        msg=body,
        digestmod=hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(expected, signature)


async def tribute_webhook_handler(request: web.Request) -> web.Response:
    body = await request.read()

    signature = request.headers.get("Trbt-Signature", "")
    if not verify_tribute_signature(body, signature):
        logger.warning("Tribute: неверная подпись вебхука")
        return web.Response(status=403, text="Invalid signature")

    try:
        data = json.loads(body)
    except Exception:
        return web.Response(status=400, text="Bad JSON")

    logger.info("Tribute webhook: %s", json.dumps(data, ensure_ascii=False))

    if data.get("name") != "new_digital_product":
        return web.Response(status=200, text="ok")

    payload = data.get("payload", {})
    telegram_id = payload.get("telegram_user_id")

    try:
        rubles = int(payload.get("amount", 0)) // 100  # копейки -> рубли
    except (TypeError, ValueError):
        rubles = 0

    if not telegram_id or rubles <= 0:
        logger.warning("Tribute: некорректный payload: %s", payload)
        return web.Response(status=200, text="ok")

    telegram_id = int(telegram_id)
    was_activated = await add_balance_and_enable_if_needed(telegram_id, rubles)
    user = await get_user(telegram_id)

    bot: Bot = request.app["bot"]
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
                parse_mode="HTML",
                reply_markup=home_button,
            )
    except Exception as e:
        logger.error("Tribute: не удалось уведомить пользователя %s: %s", telegram_id, e)

    return web.Response(status=200, text="ok")


def register_tribute_webhook(app: web.Application):
    app.router.add_post(TRIBUTE_WEBHOOK_PATH, tribute_webhook_handler)








