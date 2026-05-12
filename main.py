import asyncio
import os
import logging
import uvicorn
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from bot.handlers import router
from bot.middlewares import AuthMiddleware
from database.models import init_db
from utils.scheduler import start_scheduler
from webapp.router import app
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=logging.INFO)

async def run_bot():
    await init_db()
    bot = Bot(token=os.getenv("BOT_TOKEN"))
    dp = Dispatcher(storage=MemoryStorage())

    dp.message.middleware(AuthMiddleware())
    dp.callback_query.middleware(AuthMiddleware())
    dp.include_router(router)

    start_scheduler(bot)

    logging.info("Bot started...")
    await dp.start_polling(bot)

async def run_app():
    config = uvicorn.Config(app, host="0.0.0.0", port=8000, log_level="info")
    server = uvicorn.Server(config)
    await server.serve()

async def main():
    # Run both bot and webapp concurrently
    await asyncio.gather(
        run_bot(),
        run_app()
    )

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logging.info("System stopped.")
