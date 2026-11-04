import logging
import re
import secrets
from datetime import datetime, time

import pytz
from aiogram import F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message

from bot.app.database.promocodes import (
    create_promocode,
    delete_promocode,
    get_promocode,
    get_promocodes_page,
    promocode_exists,
    toggle_promocode,
)
from bot.app.handlers.admin.panel import is_admin
from bot.app.keyboards.admin import (
    promo_card,
    promo_confirm,
    promo_create_code,
    promo_delete_confirm,
    promo_list,
    promo_menu,
)

router = Router()
logger = logging.getLogger(__name__)


MOSCOW = pytz.timezone("Europe/Moscow")
PAGE_SIZE = 5
MAX_AMOUNT = 10000
CODE_RE = re.compile(r"^[A-Z0-9]{4,20}$")
ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"  # без похожих символов (0/O, 1/I)

class PromoCreateFSM(StatesGroup):
    code = State()
    amount = State()
    max_uses = State()
    expires = State()
    confirm = State()

MENU_TEXT = (
    "🎟 <b>Промокоды</b>\n\n"
    "Управляйте промокодами: создавайте новые и следите за активациями."
)

# ─── Вспомогательные ───────────────────────────────────────────────────────

def _fmt_expires(dt) -> str:
    return dt.astimezone(MOSCOW).strftime("%d.%m.%Y") if dt else "бессрочно"

def _fmt_limit(max_uses: int) -> str:
    return f"{max_uses} активаций" if max_uses > 0 else "без лимита"

def _status(p: dict) -> tuple[str, str]:
    """(эмодзи, текст статуса)"""
    if not p["is_active"]:
        return "⛔️", "Отключён ⛔️"
    if p["expires_at"] and p["expires_at"] < datetime.now(pytz.utc):
        return "⌛️", "Истёк ⌛️"
    if p["max_uses"] > 0 and p["used_count"] >= p["max_uses"]:
        return "🔴", "Лимит исчерпан 🔴"
    return "✅", "Активен ✅"

def _generate_code(length: int = 8) -> str:
    return "".join(secrets.choice(ALPHABET) for _ in range(length))

def _list_items(rows: list[dict]) -> list[tuple[int, str]]:
    items = []
    for p in rows:
        emoji, _ = _status(p)
        limit = p["max_uses"] if p["max_uses"] > 0 else "∞"
        items.append((p["id"], f"{p['code']} — {p['used_count']}/{limit} — {emoji}"))
    return items

async def _show(call: CallbackQuery, text: str, kb):
    """Редактирует сообщение, а если нельзя — отправляет новое."""
    try:
        await call.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    except TelegramBadRequest:
        await call.message.answer(text, reply_markup=kb, parse_mode="HTML")

# ─── Меню ──────────────────────────────────────────────────────────────────

@router.message(F.text == "🎟 Промокоды")
async def menu(message: Message):
    if not is_admin(message.from_user.id):
        return
    await message.delete()
    await message.answer(MENU_TEXT, reply_markup=promo_menu(), parse_mode="HTML")

@router.callback_query(F.data == "apromo_exit")
async def promo_exit(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        return
    await call.answer()
    try:
        await call.message.delete()
    except TelegramBadRequest:
        pass

@router.callback_query(F.data == "apromo_back")
async def promo_back(call: CallbackQuery, state: FSMContext):
    """Назад в меню промокодов (с первого шага создания и с первой страницы списка)."""
    if not is_admin(call.from_user.id):
        return
    await state.clear()  # выходим из режима ввода, иначе бот продолжит ждать код
    await call.answer()
    await _show(call, MENU_TEXT, promo_menu())

# ─── Создание: шаг 1 — код ─────────────────────────────────────────────────

@router.callback_query(F.data == "apromo_create")
async def create_start(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id):
        return
    await call.answer()
    await state.set_state(PromoCreateFSM.code)
    await _show(
        call,
        "➕ <b>Новый промокод</b>\n\n"
        "Введите промокод (4–20 символов) "
        "или нажмите «🎲 Сгенерировать».",
        promo_create_code(),
    )

async def _ask_amount(target: Message, state: FSMContext, code: str):
    await state.update_data(code=code)
    await state.set_state(PromoCreateFSM.amount)
    await target.answer(
        f"Код: <code>{code}</code>\n\n"
        "Сколько рублей начислять за активацию?",
        parse_mode="HTML"
    )

@router.callback_query(F.data == "apromo_gen", PromoCreateFSM.code)
async def create_generate(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id):
        return
    await call.answer()

    code = _generate_code()
    for _ in range(10):
        if not await promocode_exists(code):
            break
        code = _generate_code()
    else:
        await call.message.answer("❌ Не удалось сгенерировать уникальный код, попробуйте ещё раз.")
        return

    await _ask_amount(call.message, state, code)

@router.message(PromoCreateFSM.code)
async def create_code(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    code = (message.text or "").strip().upper()

    if not CODE_RE.match(code):
        await message.answer(
            "❌ Код должен состоять из латинских букв и цифр, длина 4–20 символов. Попробуйте ещё раз.",
        )
        return
    if await promocode_exists(code):
        await message.answer(
            "❌ Такой промокод уже существует. Введите другой.",
        )
        return

    await _ask_amount(message, state, code)

# ─── Шаг 2 — сумма ─────────────────────────────────────────────────────────

@router.message(PromoCreateFSM.amount)
async def create_amount(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    text = (message.text or "").strip()

    if not text.isdigit() or not (1 <= int(text) <= MAX_AMOUNT):
        await message.answer(
            f"❌ Введите целое число от 1 до {MAX_AMOUNT}.",
        )
        return

    await state.update_data(amount=int(text))
    await state.set_state(PromoCreateFSM.max_uses)
    await message.answer(
        "Сколько раз можно активировать? Отправьте число или <code>0</code> — без лимита.",
        parse_mode="HTML",
    )

# ─── Шаг 3 — лимит ─────────────────────────────────────────────────────────

@router.message(PromoCreateFSM.max_uses)
async def create_max_uses(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    text = (message.text or "").strip()

    if not text.isdigit() or int(text) > 1_000_000:
        await message.answer(
            "❌ Введите целое число (0 — без лимита).",
        )
        return

    await state.update_data(max_uses=int(text))
    await state.set_state(PromoCreateFSM.expires)
    await message.answer(
        "До какой даты действует? Формат <code>ДД.ММ.ГГГГ</code> или <code>0</code> — бессрочно.",
        parse_mode="HTML",
    )

# ─── Шаг 4 — срок ──────────────────────────────────────────────────────────

@router.message(PromoCreateFSM.expires)
async def create_expires(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    text = (message.text or "").strip()

    expires_iso = None
    if text != "0":
        try:
            day = datetime.strptime(text, "%d.%m.%Y").date()
        except ValueError:
            await message.answer(
                "❌ Неверный формат. Введите дату как <code>ДД.ММ.ГГГГ</code> или <code>0</code>.",
                parse_mode="HTML",
            )
            return

        if day < datetime.now(MOSCOW).date():
            await message.answer(
                "❌ Эта дата уже прошла. Введите будущую дату или <code>0</code>.",
                parse_mode="HTML",
            )
            return

        # Действует до конца указанного дня по Москве
        expires_iso = MOSCOW.localize(datetime.combine(day, time(23, 59, 59))).isoformat()

    await state.update_data(expires=expires_iso)
    await state.set_state(PromoCreateFSM.confirm)

    data = await state.get_data()
    expires_dt = datetime.fromisoformat(expires_iso) if expires_iso else None

    await message.answer(
        "🎟 <b>Новый промокод</b>\n\n"
        f"Код: <code>{data['code']}</code>\n"
        f"Сумма: {data['amount']}₽\n"
        f"Лимит: {_fmt_limit(data['max_uses'])}\n"
        f"Действует до: {_fmt_expires(expires_dt)}",
        reply_markup=promo_confirm(),
        parse_mode="HTML",
    )

# ─── Подтверждение / отмена ────────────────────────────────────────────────

@router.callback_query(F.data == "apromo_confirm", PromoCreateFSM.confirm)
async def create_confirm(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id):
        return
    data = await state.get_data()
    await state.clear()

    expires_dt = datetime.fromisoformat(data["expires"]) if data.get("expires") else None
    created = await create_promocode(
        code=data["code"],
        amount=data["amount"],
        max_uses=data["max_uses"],
        expires_at=expires_dt,
    )

    if created:
        await call.answer("Создано ✅")
        await _show(call, f"✅ Промокод <code>{data['code']}</code> создан!", None)
    else:
        await call.answer()
        await _show(call, "❌ Промокод с таким кодом уже существует.", None)

@router.callback_query(F.data == "apromo_cancel")
async def create_cancel(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id):
        return
    await state.clear()
    await call.answer()
    await call.message.answer("🚫 Создание промокода прервано.")
    try:
        await call.message.delete()
    except TelegramBadRequest:
        pass

# ─── Список ────────────────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("apromo_list:"))
async def promocode_list(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        return

    page = int(call.data.split(":")[1])
    rows, total = await get_promocodes_page(PAGE_SIZE, page * PAGE_SIZE)

    if not rows:
        await call.answer("Промокодов пока нет", show_alert=True)
        return

    await call.answer()
    await _show(
        call,
        f"📋 <b>Промокоды ({total})</b>\n\nВыберите промокод:",
        promo_list(_list_items(rows), page, total, PAGE_SIZE),
    )

# ─── Карточка ──────────────────────────────────────────────────────────────

async def _render_card(call: CallbackQuery, promo_id: int, page: int):
    p = await get_promocode(promo_id)
    if not p:
        await call.answer("❌ Промокод не найден", show_alert=True)
        return

    _, status_text = _status(p)
    limit = p["max_uses"] if p["max_uses"] > 0 else "∞"
    created = p["created_at"].astimezone(MOSCOW).strftime("%d.%m.%Y")

    text = (
        f"🎟 <b>{p['code']}</b>\n\n"
        f"💰 Сумма: {p['amount']}₽\n"
        f"👥 Активаций: {p['used_count']} из {limit}\n"
        f"📅 Создан: {created}\n"
        f"⌛️ Действует до: {_fmt_expires(p['expires_at'])}\n"
        f"📌 Статус: {status_text}"
    )
    await _show(call, text, promo_card(p["id"], p["is_active"], page))

@router.callback_query(F.data.startswith("apromo_view:"))
async def promo_view(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        return
    await call.answer()
    _, promo_id, page = call.data.split(":")
    await _render_card(call, int(promo_id), int(page))

@router.callback_query(F.data.startswith("apromo_toggle:"))
async def promo_toggle(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        return
    _, promo_id, page = call.data.split(":")

    new_state = await toggle_promocode(int(promo_id))
    if new_state is None:
        await call.answer("❌ Промокод не найден", show_alert=True)
        return

    logger.info("Админ %s: промокод id=%s is_active=%s", call.from_user.id, promo_id, new_state)
    await call.answer("Включён ✅" if new_state else "Отключён ⛔️")
    await _render_card(call, int(promo_id), int(page))

# ─── Удаление ──────────────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("apromo_del:"))
async def promo_delete_ask(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        return
    _, promo_id, page = call.data.split(":")

    p = await get_promocode(int(promo_id))
    if not p:
        await call.answer("❌ Промокод не найден", show_alert=True)
        return

    await call.answer()
    await _show(
        call,
        f"⚠️ <b>Удалить промокод {p['code']}?</b>\n\n"
        "Вместе с ним удалится история активаций. Это действие нельзя отменить!",
        promo_delete_confirm(p["id"], int(page)),
    )

@router.callback_query(F.data.startswith("apromo_delok:"))
async def promo_delete(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        return
    _, promo_id, page = call.data.split(":")

    deleted = await delete_promocode(int(promo_id))
    if not deleted:
        await call.answer("❌ Промокод не найден", show_alert=True)
        return

    logger.info("Админ %s удалил промокод id=%s", call.from_user.id, promo_id)
    await call.answer("Удалено 🗑")

    # Возвращаемся к списку; если на странице больше ничего нет — на предыдущую или в меню
    page = int(page)
    rows, total = await get_promocodes_page(PAGE_SIZE, page * PAGE_SIZE)
    if not rows and page > 0:
        page -= 1
        rows, total = await get_promocodes_page(PAGE_SIZE, page * PAGE_SIZE)

    if not rows:
        await _show(call, MENU_TEXT, promo_menu())
        return

    await _show(
        call,
        f"📋 <b>Промокоды ({total})</b>\n\n"
        "Здесь вы можете управлять всеми промокодами.\n\n"
        "Выберите промокод:",
        promo_list(_list_items(rows), page, total, PAGE_SIZE),
    )