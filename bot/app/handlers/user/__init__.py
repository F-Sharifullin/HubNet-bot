from aiogram import Router

from bot.app.handlers.user.balance import router as balance_router
from bot.app.handlers.user.bonuses import router as bonuses_router
from bot.app.handlers.user.devices import router as devices_router
from bot.app.handlers.user.fortune import router as fortune_router
from bot.app.handlers.user.promo import router as promo_router
from bot.app.handlers.user.referral import router as referral_router
from bot.app.handlers.user.rollypay import register_rollypay_webhook
from bot.app.handlers.user.rollypay import router as rollypay_router
from bot.app.handlers.user.stars import router as stars_router
from bot.app.handlers.user.start import router as start_router
from bot.app.handlers.user.support import router as support_router
from bot.app.handlers.user.tariffs import router as tariffs_router
from bot.app.handlers.user.tribute import register_tribute_webhook
from bot.app.handlers.user.tribute import router as tribute_router

router = Router()

router.include_router(start_router)
router.include_router(tariffs_router)
router.include_router(bonuses_router)
router.include_router(referral_router)
router.include_router(devices_router)
router.include_router(support_router)
router.include_router(promo_router)
router.include_router(fortune_router)
router.include_router(balance_router)
router.include_router(rollypay_router)
router.include_router(tribute_router)
router.include_router(stars_router)

__all__ = ["register_rollypay_webhook", "register_tribute_webhook", "router"]