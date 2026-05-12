import asyncio
import os
import logging
import uvicorn
import sys
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from bot.handlers import router
from bot.middlewares import AuthMiddleware
from database.models import init_db
from utils.scheduler import start_scheduler
from webapp.router import app
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    stream=sys.stdout
)
logger = logging.getLogger(__name__)

async def run_bot():
    token = os.getenv("BOT_TOKEN")
    if not token:
        logger.error("BOT_TOKEN is not set. Bot will not start.")
        return

    try:
        bot = Bot(token=token)
        dp = Dispatcher(storage=MemoryStorage())
        dp.message.middleware(AuthMiddleware())
        dp.callback_query.middleware(AuthMiddleware())
        dp.include_router(router)

        start_scheduler(bot)
        logger.info("Bot and Scheduler started.")
        await dp.start_polling(bot)
    except Exception as e:
        logger.error(f"Error starting bot: {e}")

async def run_app():
    port = int(os.getenv("PORT", 8000))
    logger.info(f"Starting WebApp on port {port}...")
    config = uvicorn.Config(app, host="0.0.0.0", port=port, log_level="info")
    server = uvicorn.Server(config)
    try:
        await server.serve()
    except Exception as e:
        logger.error(f"Error starting WebApp: {e}")
        sys.exit(1)

async def main():
    logger.info("Initializing database...")
    try:
        await init_db()
    except Exception as e:
        logger.error(f"Database initialization failed: {e}")
        sys.exit(1)

    # Use gather to run both services.
    # If one fails, we want to know, but maybe the other can keep running?
    # Usually on Render, if the web port isn't bound, it fails anyway.
    await asyncio.gather(
        run_bot(),
        run_app()
    )

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Interrupted by user.")
    except Exception as e:
        logger.critical(f"Unhandled exception: {e}")
        sys.exit(1)
