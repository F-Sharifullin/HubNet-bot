import asyncio

from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.redis import RedisStorage
from aiohttp import web

from bot.app.database import resync_all_expiry  # чтоб старые ключи обновили строки
from bot.app.database.connection import close_pool, init_pool
from bot.app.handlers import router
from bot.app.handlers.user import register_rollypay_webhook, register_tribute_webhook
from bot.app.services import x3ui
from bot.app.tasks import start_scheduler
from bot.config import (
    BOT_TOKEN,
    REDIS_HOST,
    REDIS_PORT,
    TRIBUTE_WEBHOOK_HOST,
    TRIBUTE_WEBHOOK_PORT,
)

bot = Bot(token=BOT_TOKEN)
storage = RedisStorage.from_url(f"redis://{REDIS_HOST}:{REDIS_PORT}")
dp = Dispatcher(storage=storage)


async def main():
    await init_pool()
    dp.include_router(router)
    scheduler = start_scheduler(bot)
     
    # Webhook
    app = web.Application()
    app["bot"] = bot
    register_rollypay_webhook(app)
    register_tribute_webhook(app)
    
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, TRIBUTE_WEBHOOK_HOST, TRIBUTE_WEBHOOK_PORT)
    await site.start()

    asyncio.create_task(resync_all_expiry()) # после 1 запуска УДАЛИТЬ

    print("✅ Бот запущен")

    try:
        await bot.delete_webhook(drop_pending_updates=True)
        await dp.start_polling(bot)
    finally:
        scheduler.shutdown()
        await runner.cleanup()
        await close_pool()
        await x3ui.close()
        await bot.session.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("🛑 Бот остановлен")