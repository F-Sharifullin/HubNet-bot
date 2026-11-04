from aiogram import F, Router
from aiogram.types import CallbackQuery

router = Router()


@router.callback_query(F.data == "pay_stars")
async def pay_stars(callback: CallbackQuery):
    await callback.answer("⚠️ Раздел в разработке", show_alert=True)
    

