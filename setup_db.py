import asyncio
from database.models import init_db, AsyncSessionLocal, Admin, CustomEmoji, Channel, Post
import os
from dotenv import load_dotenv

load_dotenv()

async def setup():
    await init_db()
    async with AsyncSessionLocal() as session:
        owner_id = int(os.getenv("OWNER_ID", 0))
        if owner_id:
            from sqlalchemy import select
            res = await session.execute(select(Admin).where(Admin.user_id == owner_id))
            if not res.scalar_one_or_none():
                session.add(Admin(user_id=owner_id, is_owner=True))

        # Add a sample emoji
        sample_emojis = ["5368324170671202286"]
        for eid in sample_emojis:
            res = await session.execute(select(CustomEmoji).where(CustomEmoji.custom_emoji_id == eid))
            if not res.scalar_one_or_none():
                session.add(CustomEmoji(custom_emoji_id=eid))

        # Add a sample post for WebApp testing
        res = await session.execute(select(Post).where(Post.id == 1))
        if not res.scalar_one_or_none():
            session.add(Post(id=1, creator_id=owner_id, text="اختبار المنشور"))

        await session.commit()
    print("Setup complete.")

if __name__ == "__main__":
    asyncio.run(setup())
