import logging

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from bot.app.keyboards.admin.menu import admin
from bot.config import ADMIN_ID

router = Router()
logger = logging.getLogger(__name__)

def is_admin(user_id: int) -> bool:
    return str(user_id) == str(ADMIN_ID)

@router.message(Command("admin"))
async def cmd_admin(message: Message):
    if not is_admin(message.from_user.id):
        return

    text = (
        "🛠 <b>Панель администратора</b>\n"
        "Доступ к панели управления открыт.\n"
        "Выберите раздел:"
    )

    await message.answer(
        text,
        reply_markup=admin,
        parse_mode="HTML"
    )