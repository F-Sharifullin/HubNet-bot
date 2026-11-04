import asyncio

from aiogram import Bot, Dispatcher
from aiohttp import web

from bot.app.database import resync_all_expiry  # чтоб старые ключи обновили строки
from bot.app.database.connection import close_pool, init_pool
from bot.app.handlers import router
from bot.app.handlers.user import register_rollypay_webhook, register_tribute_webhook
from bot.config import BOT_TOKEN

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()


async def main():
    await init_pool()
     
    # Webhook
    app = web.Application()
    app["bot"] = bot
    register_rollypay_webhook(app)
    register_tribute_webhook(app)
    try:
        asyncio.create_task(resync_all_expiry()) # после 1 запуска УДАЛИТЬ
        dp.include_router(router)
        await bot.delete_webhook(drop_pending_updates=True)
        await dp.start_polling(bot)
    finally:
        await close_pool()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass