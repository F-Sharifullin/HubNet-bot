from aiogram import Router

from bot.app.handlers.admin import router as admin_router
from bot.app.handlers.user import router as user_router

router = Router()

router.include_router(admin_router)
router.include_router(user_router)

__all__ = ["router"]