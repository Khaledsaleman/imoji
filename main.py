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

async def start_services():
    await init_db()

    bot = Bot(token=os.getenv("BOT_TOKEN"))
    dp = Dispatcher(storage=MemoryStorage())

    dp.message.middleware(AuthMiddleware())
    dp.callback_query.middleware(AuthMiddleware())
    dp.include_router(router)

    start_scheduler(bot)

    logging.info("Bot & Scheduler starting...")

    # Start bot polling as a background task
    asyncio.create_task(dp.start_polling(bot))

    # The WebApp (FastAPI) will be run by uvicorn/gunicorn in production
    # but here we keep it as an option for local testing.
    port = int(os.getenv("PORT", 8000))
    config = uvicorn.Config(app, host="0.0.0.0", port=port, log_level="info")
    server = uvicorn.Server(config)
    await server.serve()

if __name__ == "__main__":
    try:
        asyncio.run(start_services())
    except (KeyboardInterrupt, SystemExit):
        logging.info("System stopped.")
