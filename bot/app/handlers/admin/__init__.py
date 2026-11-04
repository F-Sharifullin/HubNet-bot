from aiogram import Router

from bot.app.handlers.admin.broadcast import router as broadcast_router
from bot.app.handlers.admin.panel import router as panel_router
from bot.app.handlers.admin.promo import router as promo_router
from bot.app.handlers.admin.stats import router as stats_router
from bot.app.handlers.admin.support import router as support_router
from bot.app.handlers.admin.users import router as users_router

router = Router()

router.include_router(panel_router)
router.include_router(promo_router)
router.include_router(support_router)
router.include_router(broadcast_router)
router.include_router(stats_router)
router.include_router(users_router)

__all__ = ["router"]