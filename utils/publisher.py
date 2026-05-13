import json
from aiogram import Bot
from aiogram.types import MessageEntity
from database.models import AsyncSessionLocal, Post, Channel
from sqlalchemy import select
import logging

async def publish_post(bot: Bot, post_id: int):
    async with AsyncSessionLocal() as session:
        # Fetch post
        result = await session.execute(select(Post).where(Post.id == post_id))
        post = result.scalar_one_or_none()
        if not post:
            logging.error(f"Post {post_id} not found")
            return False

        # Use post.channel_id if specified, otherwise fallback to first active channel
        target_channel_id = post.channel_id
        if target_channel_id:
            channel_result = await session.execute(select(Channel).where(Channel.channel_id == target_channel_id))
            channel = channel_result.scalar_one_or_none()
        else:
            channel_result = await session.execute(select(Channel).where(Channel.is_active == True))
            channel = channel_result.scalar_one_or_none()

        if not channel:
            logging.error(f"No target channel found for post {post_id}")
            return False

        # Parse entities
        entities = []
        if post.entities_json:
            entities_data = json.loads(post.entities_json)
            for ent in entities_data:
                entities.append(MessageEntity(
                    type=ent['type'],
                    offset=ent['offset'],
                    length=ent['length'],
                    custom_emoji_id=ent.get('custom_emoji_id')
                ))

        try:
            if post.media_type == "photo":
                await bot.send_photo(
                    chat_id=channel.channel_id,
                    photo=post.media_file_id,
                    caption=post.text,
                    caption_entities=entities
                )
            elif post.media_type == "video":
                await bot.send_video(
                    chat_id=channel.channel_id,
                    video=post.media_file_id,
                    caption=post.text,
                    caption_entities=entities
                )
            else:
                await bot.send_message(
                    chat_id=channel.channel_id,
                    text=post.text,
                    entities=entities
                )

            post.is_published = True
            await session.commit()
            return True
        except Exception as e:
            logging.error(f"Failed to publish post: {e}")
            return False
