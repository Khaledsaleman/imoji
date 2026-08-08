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

def get_webapp_url():
    url = os.getenv("WEBAPP_URL")
    if not url or "your-webapp-url.com" in url:
        return None
    return url

async def check_bot_health(bot: Bot, webapp_url: str):
    consecutive_failures = 0
    while True:
        try:
            await asyncio.sleep(120)  # Check every 2 minutes
            logger.info("Running background bot health check...")

            # Check Telegram API connectivity
            me = await bot.get_me()
            consecutive_failures = 0  # Reset on success
            logger.info(f"Telegram API check successful. Bot @{me.username} is responsive.")

            # In Webhook mode, verify that the webhook is set correctly
            if webapp_url:
                expected_url = f"{webapp_url.rstrip('/')}/webhook/bot"
                webhook_info = await bot.get_webhook_info()

                if webhook_info.url != expected_url:
                    logger.warning(
                        f"Webhook mismatch or deactivated! Expected: {expected_url}, Found: {webhook_info.url}. "
                        "Re-registering webhook..."
                    )
                    await bot.set_webhook(url=expected_url, drop_pending_updates=False)
                    logger.info("Webhook successfully restored/re-registered.")
                else:
                    logger.info("Webhook configuration verified and active.")

        except Exception as e:
            consecutive_failures += 1
            logger.error(
                f"Bot health check failed (consecutive failures: {consecutive_failures}/5): {e}",
                exc_info=True
            )
            if consecutive_failures >= 5:
                logger.critical("Too many consecutive Telegram API failures. Exiting process to trigger Render restart...")
                sys.exit(1)

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

        # Share bot and dispatcher with FastAPI app
        app.state.bot = bot
        app.state.dp = dp

        start_scheduler(bot)
        logger.info("Scheduler started.")

        webapp_url = get_webapp_url()

        # Start the background health check task
        asyncio.create_task(check_bot_health(bot, webapp_url))

        if webapp_url:
            webhook_url = f"{webapp_url.rstrip('/')}/webhook/bot"
            logger.info(f"Bot will run in WEBHOOK mode. Setting webhook to: {webhook_url}")
            try:
                await bot.set_webhook(url=webhook_url, drop_pending_updates=True)
                logger.info("Webhook successfully set on startup. Dispatcher will process updates received via FastAPI.")
            except Exception as e:
                logger.error(f"Failed to set webhook on startup: {e}", exc_info=True)

            # Keep the run_bot task alive in webhook mode
            while True:
                await asyncio.sleep(3600)
        else:
            logger.info("Bot will run in POLLING mode (no WEBAPP_URL configured).")
            while True:
                try:
                    await bot.delete_webhook(drop_pending_updates=True)
                    logger.info("Starting polling loop...")
                    await dp.start_polling(bot)
                    logger.warning("Polling finished normally. Restarting polling in 5 seconds...")
                except Exception as e:
                    logger.error(f"Polling crashed with error: {e}. Restarting polling in 5 seconds...", exc_info=True)
                await asyncio.sleep(5)
    except Exception as e:
        logger.error(f"Error starting bot: {e}", exc_info=True)
        sys.exit(1)

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
