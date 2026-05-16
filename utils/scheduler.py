from apscheduler.schedulers.asyncio import AsyncIOScheduler
from utils.publisher import publish_post
from database.models import AsyncSessionLocal, Post
from sqlalchemy import select
import datetime
from aiogram import Bot

scheduler = AsyncIOScheduler()

async def check_scheduled_posts(bot: Bot):
    async with AsyncSessionLocal() as session:
        now = datetime.datetime.utcnow()
        result = await session.execute(
            select(Post).where(Post.scheduled_at <= now, Post.is_published == False)
        )
        posts = result.scalars().all()
        for post in posts:
            await publish_post(bot, post.id, is_automatic=True)

def start_scheduler(bot: Bot):
    scheduler.add_job(check_scheduled_posts, "interval", minutes=1, args=[bot])
    scheduler.start()
