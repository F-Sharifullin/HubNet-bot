import asyncio
import logging
import urllib.parse
from collections import defaultdict

from aiogram import F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import CallbackQuery, LinkPreviewOptions

from bot.app.database import (
    delete_subscription,
    get_subscription,
    get_user,
    get_user_subscriptions,
)
from bot.app.database.tariffs import TARIFFS
from bot.app.keyboards.user import (
    apps_keyboard,
    balance_menu,
    change_tariff,
    confirm_delete,
    device_button,
    devices_list,
    execute_replace,
    platform_choice,
    subscription_device,
    tariff_downgrade,
)
from bot.app.services import cheaper_tariff_for, x3ui
from bot.config import SUB_PATH, SUB_PORT, SUB_URL

router = Router()
logger = logging.getLogger(__name__)
_user_locks: dict[int, asyncio.Lock] = defaultdict(asyncio.Lock)


async def check_can_add_device(callback: CallbackQuery) -> bool:
    user = await get_user(callback.from_user.id)
    if not user or user["balance"] <= 0:
        await callback.answer(
            "❌ Баланс 0 ₽.\n\nСоздание новых устройств невозможно. Пополните баланс!",
            show_alert=True
        )
        return False

    tariff = TARIFFS[user["tariff"]]
    if user["devices"] >= tariff.max_keys:
        await callback.answer()
        if user["tariff"] == "PREMIUM":
            await callback.message.answer(
                f"❌ Максимум тарифа PREMIUM — {tariff.max_keys} устройств.\n\n"
                "Удалите ненужное устройство в разделе «Мои устройства».",
                show_alert=True
            )
        else:
            await callback.message.answer(
                f"⚠️ Достигнут лимит устройств.\n\n"
                f"На тарифе <b>{tariff.title}</b> доступно до {tariff.max_keys} устройств.\n\n"
                "Чтобы подключить ещё одно, смените тариф или удалите ненужное устройство.",
                reply_markup=change_tariff,
                parse_mode="HTML",
            )
        return False

    await callback.answer()
    return True


# Ссылки на приложения по типу устройства
DEVICE_LINKS = {
    "android": {
        "happ": "https://play.google.com/store/apps/details?id=com.happproxy",
        "incy": "https://play.google.com/store/apps/details?id=llc.itdev.incy",
    },
    "ios": {
        "happ": "https://apps.apple.com/ru/app/happ-proxy-utility-plus/id6746188973",
        "incy": "https://apps.apple.com/us/app/incy/id6756943388",
    },
    "windows": {
        "happ": "https://github.com/Happ-proxy/happ-desktop/releases/latest/download/setup-Happ.x64.exe",
        "incy": "https://github.com/INCY-DEV/incy-platforms/releases/download/desktop-v3.3.4/incy-windows-setup.exe"
    },
}

STORE_NAME = {
    "android": "Google Play",
    "ios": "App Store",
    "windows": "PC",
}


def _build_new_device_text(device: str, sub_link: str) -> str:
    """Формирует текст с инструкцией при создании нового устройства."""
    links = DEVICE_LINKS[device]
    store_name = STORE_NAME[device]

    if device == "ios":
        apps = (
            f"• <a href='{links['happ']}'>Happ</a> (сейчас может быть недоступно в {store_name})\n"
            f"• <a href='{links['incy']}'>INCY</a> (доступно в {store_name})"
        )

    elif device == "windows":
        apps = (
            f"• <a href='{links['happ']}'>Happ</a> (GitHub)\n"
            f"• <a href='{links['incy']}'>INCY</a> (GitHub)"
        )

    else:  # device == "android"
        apps = (
            f"• <a href='{links['happ']}'>Happ</a> (доступно в {store_name})\n"
            f"• <a href='{links['incy']}'>INCY</a> (доступно в {store_name})"
        )

    key_clean = sub_link.lstrip("<").rstrip(">")
    key = f"<pre>{key_clean}</pre>\n\n"

    return (
        "1️⃣ Установите одно из приложений\n"
        f"{apps}\n"
        "2️⃣ Нажмите на кнопку своего приложения ниже (<b>Happ</b> или <b>INCY</b>), чтобы автоматически добавить VPN.\n"
        "<blockquote expandable>"
        "Если кнопка не работает, скопируйте ключ вручную и вставьте его в приложении "
        "через раздел «Вставить из буфера обмена».\n"
        "</blockquote>"
        "3️⃣ Разрешите приложению добавить конфигурацию VPN.\n\n"
        "❗️Количество подключаемых устройств зависит от вашего тарифа. "
        "Если достигнут лимит, удалите ненужное устройство или выберите другой тариф.\n\n"
        f"🔑 Ваш ключ:️{key}"        
    )

def _build_subscription_text(device: str, remark: str, sub_link: str) -> str:
    """Формирует текст с инструкцией для существующей подписки."""
    links = DEVICE_LINKS[device]
    store_name = STORE_NAME[device]

    if device == "ios":
        apps = (
            f"• <a href='{links['happ']}'>Happ</a> (сейчас может быть недоступно в {store_name})\n"
            f"• <a href='{links['incy']}'>INCY</a> (доступно в {store_name})"
        )
    elif device == "windows":
        apps = (
            f"• <a href='{links['happ']}'>Happ</a> (GitHub)\n"
            f"• <a href='{links['incy']}'>INCY</a> (GitHub)"
        )
    else:  # device == "android"
        apps = (
            f"• <a href='{links['happ']}'>Happ</a> (доступно в {store_name})\n"
            f"• <a href='{links['incy']}'>INCY</a> (доступно в {store_name})"
        )

    return (
        f"<b>{remark}</b>\n\n"
        "📌 Инструкции по установке:\n"
        "<blockquote expandable>"
        "1️⃣ Установите одно из приложений\n"
        f"{apps}\n"
        "2️⃣ Выберите своё приложение внизу (<b>Happ</b> или <b>INCY</b>), чтобы автоматически добавить VPN.\n"
        "Если кнопка не работает, скопируйте ключ и вставьте его в приложении "
        "через раздел «Вставить из буфера обмена».\n"
        "3️⃣ Разрешите конфигурацию VPN.\n"
        "</blockquote>\n"
        "🔑 Ваш ключ:\n"
        f"<pre>{sub_link}</pre>\n\n"
    )

async def _create_and_send_device(callback: CallbackQuery, device: str):
    """Общая логика создания нового устройства для любой платформы."""
    user_id = callback.from_user.id
    lock = _user_locks[user_id]

    if lock.locked():
        await callback.answer("⏳ Устройство уже создаётся, подождите несколько секунд", show_alert=True)
        return

    async with lock:
        # Проверка лимита внутри лока. При отказе показывает плашку сама
        if not await check_can_add_device(callback):
            return

        try:
            await callback.answer()
        except TelegramBadRequest as e:
            logger.warning("Не удалось ответить на callback: %s", e)


        sub_link = await x3ui.add_client(callback.from_user.id, device)

    if not sub_link:
        await callback.message.answer("❌ Ошибка создания ключа. Попробуйте позже.")
        return

    encoded = urllib.parse.quote(sub_link, safe="")

    happ_link = f"https://r.stun.su/?to=happ://add/{encoded}"
    incy_link = f"https://r.stun.su/?to=incy://add/{encoded}"

    keyboard = apps_keyboard(happ_link, incy_link)
    text = _build_new_device_text(device, sub_link)

    for attempt in range(1, 4):
            try:
                await callback.message.answer(
                    text,
                    parse_mode="HTML",
                    reply_markup=keyboard,
                    link_preview_options=LinkPreviewOptions(is_disabled=True),
                )
                break
            except Exception as e:
                logger.warning("Отправка ключа, попытка %s/3 не удалась: %s", attempt, e)
                await asyncio.sleep(2)


# ====================== МОИ УСТРОЙСТВА ======================
@router.callback_query(F.data == "my_devices")
async def my_devices(callback: CallbackQuery):
    await callback.answer()

    user = await get_user(callback.from_user.id)
    if not user or user["balance"] <= 0:
        tariff = TARIFFS[user['tariff']] or "Тариф не выбран"
        text = (
            "❌ <b>К сожалению, ваш баланс исчерпан.</b>\n\n"
            "Сервис приостановлен.\n\n"
            "Чтобы продолжить использовать сервис, пополните баланс, "
            "нажав кнопку <b>«Пополнить баланс»</b> и пройдя по ссылке.\n\n"
            f"Напоминаем, Ваш текущий тариф:\n"
            f"<b>{tariff.title} — {int(tariff.monthly_price)}₽/мес.</b>\n\n"
            "👭 Пригласите друзей в наш сервис и получите 100₽ на баланс за каждого друга. "
            "Ваши друзья получат 150₽ на баланс!"
        )
        await callback.message.answer(text, reply_markup=balance_menu, parse_mode="HTML")
        return

    subs = await get_user_subscriptions(callback.from_user.id)
    if not subs:
        text = (
            "У вас пока нет устройств.\n\n"
            "Нажмите кнопку ниже, чтобы добавить новое устройство."
        )
        await callback.message.answer(text, reply_markup=device_button)
        return

    text = (
        "Внимание! Количество устройств ограничено вашим тарифом.\n\n"
        "❌ Достигли лимита? Удалите ненужное устройство или смените тариф.\n\n"
        "📱💻 Нажмите на идентификатор устройства в списке, чтобы получить настройки."
    )
    await callback.message.answer(text, reply_markup=devices_list(subs), parse_mode="HTML")


# ====================== ДОБАВЛЕНИЕ УСТРОЙСТВА ======================
@router.callback_query(F.data == "devices")
async def devices(callback: CallbackQuery):
    if not await check_can_add_device(callback):
        return
    await callback.message.answer(
        "⚙ Давайте добавим новое устройство.\n"
        "Выберите тип вашего устройства:",
        reply_markup=platform_choice,
    )


@router.callback_query(F.data == "android")
async def android_device(callback: CallbackQuery):
    await _create_and_send_device(callback, "android")


@router.callback_query(F.data == "ios")
async def ios_device(callback: CallbackQuery):
    await _create_and_send_device(callback, "ios")


@router.callback_query(F.data == "windows")
async def windows_device(callback: CallbackQuery):
    await _create_and_send_device(callback, "windows")


# ====================== НАЖАТИЕ НА КНОПКУ ПОДПИСКИ ======================
@router.callback_query(F.data.startswith("get_sub_"))
async def get_subscription_config(callback: CallbackQuery):
    sub_id = callback.data.split("_")[2]

    user = await get_user(callback.from_user.id)
    if not user or user["balance"] <= 0:
        await callback.answer(
            "❌ Ваш баланс 0 ₽\n\n"
            "Ключ отключён.\n"
            "Пополните баланс, чтобы включить устройства.",
            show_alert=True,
        )
        return

    sub_data = await get_subscription(sub_id)
    if not sub_data:
        await callback.answer("❌ Ключ не найден", show_alert=True)
        return

    subs = await get_user_subscriptions(callback.from_user.id)
    if not any(s["sub_id"] == sub_id for s in subs):
        await callback.answer("❌ Нет доступа к этой подписке", show_alert=True)
        return

    device = sub_data["device"]
    remark = sub_data["remark"]

    if device not in DEVICE_LINKS:
        await callback.answer("❌ Неизвестный тип устройства", show_alert=True)
        return

    await callback.answer()

    sub_link = f"{SUB_URL}:{SUB_PORT}{SUB_PATH}{sub_id}"
    
    text = _build_subscription_text(device, remark, sub_link)

    await callback.message.answer(
        text,
        parse_mode="HTML",
        reply_markup=subscription_device(sub_id),
        link_preview_options=LinkPreviewOptions(is_disabled=True),
    )


@router.callback_query(F.data == "cancel_settings")
async def cancel_sett(callback: CallbackQuery):
    await callback.answer()
    await callback.message.delete()


# ====================== УДАЛЕНИЕ ======================
@router.callback_query(F.data.startswith("delete_sub_"))
async def request_delete(callback: CallbackQuery):
    sub_id = callback.data.split("_")[2]

    sub_data = await get_subscription(sub_id)
    if not sub_data:
        await callback.answer("❌ Устройство не найдена", show_alert=True)
        return

    subs = await get_user_subscriptions(callback.from_user.id)
    if not any(s["sub_id"] == sub_id for s in subs):
        await callback.answer("❌ Нет доступа к этой подписке", show_alert=True)
        return

    remark = sub_data["remark"]
    text = (
        f"⚠️ <b>Вы уверены?</b>\n\n"
        f"Вы действительно хотите удалить устройство: <b>{remark}</b>?\n"
        f"Это действие нельзя отменить!"
    )
    await callback.answer()
    await callback.message.answer(text, parse_mode="HTML", reply_markup=confirm_delete(sub_id))


@router.callback_query(F.data.startswith("confirm_delete_"))
async def confirm_delete_devices(callback: CallbackQuery):
    await callback.answer()
    sub_id = callback.data.split("_")[-1]

    sub_data = await get_subscription(sub_id)
    if not sub_data:
        await callback.message.answer("❌ Подписка не найдена.")
        return

    subs = await get_user_subscriptions(callback.from_user.id)
    if not any(s["sub_id"] == sub_id for s in subs):
        await callback.message.answer("❌ Нет доступа к этой подписке.")
        return

    deleted_panel = await x3ui.delete_client(sub_data["uuid"], sub_data["remark"])
    remark = sub_data["remark"]

    if deleted_panel:
        await delete_subscription(sub_id)
        await callback.message.delete()
        await callback.message.answer(
            f"✅ Устройство: <b>{remark}</b> успешно удалено!\n\n"
            "Обновите список в «Мои устройства».",
            parse_mode="HTML",
        )
    else:
        logger.error("Не удалось удалить клиента %s из панели", sub_data["uuid"])
        await callback.message.answer(
            "❌ Ошибка удаления. Попробуйте позже или обратитесь в поддержку."
        )

    user = await get_user(callback.from_user.id)
    cheaper = cheaper_tariff_for(user["tariff"], user["devices"]) if user else None
    if cheaper:
        await asyncio.sleep(1)
        await callback.message.answer(
            f"💡 У вас осталось устройств: <b>{user['devices']}</b>. "
            f"Хватит тарифа <b>{cheaper.title}</b>. Перейти?",
            reply_markup=tariff_downgrade(cheaper), parse_mode="HTML",
        )


@router.callback_query(F.data == "cancel_delete")
async def cancel_delete(callback: CallbackQuery):
    await callback.answer("❌ Действие отменено", show_alert=True)
    await callback.message.delete()


# ====================== ЗАМЕНА УСТРОЙСТВА ======================
@router.callback_query(F.data.startswith("replace_sub_"))
async def request_replace(callback: CallbackQuery):
    sub_id = callback.data.split("_")[-1]

    sub_data = await get_subscription(sub_id)
    if not sub_data:
        await callback.answer("❌ Подписка не найдена", show_alert=True)
        return

    subs = await get_user_subscriptions(callback.from_user.id)
    if not any(s["sub_id"] == sub_id for s in subs):
        await callback.answer("❌ Нет доступа к этой подписке", show_alert=True)
        return

    text = (
        f"⚠️ <b>Вы уверены?</b>\n\n"
        f"Вы действительно хотите заменить устройство: <b>{sub_data['remark']}</b>?\n\n"
        "Будет выдан новый ключ, а старый перестанет работать. "
        "Вам придётся заново настроить VPN на этом устройстве."
    )
    await callback.answer()
    await callback.message.answer(text, parse_mode="HTML", reply_markup=execute_replace(sub_id))

@router.callback_query(F.data.startswith("confirm_replace_"))
async def confirm_replace(callback: CallbackQuery):
    await callback.answer()
    sub_id = callback.data.split("_")[-1]

    sub_data = await get_subscription(sub_id)
    if not sub_data:
        await callback.message.answer("❌ Подписка не найдена.")
        return

    subs = await get_user_subscriptions(callback.from_user.id)
    if not any(s["sub_id"] == sub_id for s in subs):
        await callback.message.answer("❌ Нет доступа к этой подписке.")
        return

    new_link = await x3ui.add_client(callback.from_user.id, sub_data["device"])
    if not new_link:
        await callback.message.answer("❌ Ошибка создания нового устройства. Попробуйте позже.")
        return

    deleted = await x3ui.delete_client(sub_data["uuid"], sub_data["remark"])
    if deleted:
        await delete_subscription(sub_id)
    else:
        logger.error(
            "Не удалось удалить старый клиент %s из панели при замене",
            sub_data["uuid"],
        )

    try:
        await callback.message.delete() 
    except TelegramBadRequest as e:
        logger.debug("Не удалось удалить сообщение подтверждения: %s", e)

    encoded = urllib.parse.quote(new_link, safe="")
    happ_link = f"https://r.stun.su/?to=happ://add/{encoded}"
    incy_link = f"https://r.stun.su/?to=incy://add/{encoded}"

    keyboard = apps_keyboard(happ_link, incy_link)
    key_clean = new_link.lstrip("<").rstrip(">")
    key = f"<pre>{key_clean}</pre>\n\n"

    await callback.message.answer(
        "✅ <b>Устройство успешно заменено!</b>\n\n"
        f"Вам выдан новый ключ:\n{key}"
        "⬇️ Нажмите на кнопку своего приложения (<b>Happ</b> или <b>INCY</b>), чтобы автоматически добавить VPN.",
        parse_mode="HTML",
        reply_markup=keyboard,
    )

@router.callback_query(F.data == "cancel_replace")
async def cancel_replace(callback: CallbackQuery):
    await callback.answer("❌ Действие отменено", show_alert=True)
    await callback.message.delete()


@router.callback_query(F.data == "tv")
async def tv_android(callback: CallbackQuery):
    await callback.answer("⚠️ Раздел в разработке", show_alert=True)