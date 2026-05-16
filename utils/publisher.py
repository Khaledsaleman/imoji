import json
from aiogram import Bot
from aiogram.types import MessageEntity, InlineKeyboardMarkup, InlineKeyboardButton
from database.models import AsyncSessionLocal, Post, Channel
from sqlalchemy import select, update
import logging

async def perform_copy_to_channel(bot: Bot, post_id: int):
    """Copies a preview message to the target channel to preserve animated emojis."""
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(Post).where(Post.id == post_id))
        post = result.scalar_one_or_none()
        if not post or not post.preview_message_id or not post.preview_chat_id:
            logging.error(f"Preview message not found for post {post_id}")
            return False

        target_channel_id = post.channel_id
        if not target_channel_id:
            channel_result = await session.execute(select(Channel).where(Channel.is_active == True))
            channel = channel_result.scalar_one_or_none()
            if channel:
                target_channel_id = channel.channel_id

        if not target_channel_id:
            logging.error(f"No target channel for post {post_id}")
            return False

        try:
            await bot.copy_message(
                chat_id=target_channel_id,
                from_chat_id=post.preview_chat_id,
                message_id=post.preview_message_id
            )

            # Mark as published
            post.is_published = True
            await session.commit()

            # Update preview message if possible
            try:
                await bot.edit_message_reply_markup(
                    chat_id=post.preview_chat_id,
                    message_id=post.preview_message_id,
                    reply_markup=None
                )
                # Append "Published" to the message text/caption is harder without re-sending entities,
                # but we can at least remove the button or change it.
                await bot.send_message(post.preview_chat_id, "✅ تم النشر في القناة بنجاح", reply_to_message_id=post.preview_message_id)
            except Exception as e:
                logging.error(f"Failed to update preview UI: {e}")

            return True
        except Exception as e:
            logging.error(f"Failed to copy post {post_id}: {e}")
            return False

async def publish_post(bot: Bot, post_id: int, is_automatic: bool = False):
    """Sends a preview of the post to the creator or publishes it directly via copy if automatic."""
    async with AsyncSessionLocal() as session:
        # Fetch post
        result = await session.execute(select(Post).where(Post.id == post_id))
        post = result.scalar_one_or_none()
        if not post:
            logging.error(f"Post {post_id} not found")
            return False

        # Parse entities
        entities = []
        if post.entities_json:
            entities_data = json.loads(post.entities_json)
            entities_data.sort(key=lambda x: x['offset'])
            for ent in entities_data:
                entities.append(MessageEntity(
                    type=ent['type'],
                    offset=ent['offset'],
                    length=ent['length'],
                    custom_emoji_id=str(ent.get('custom_emoji_id')) if ent.get('custom_emoji_id') else None
                ))

        try:
            # Step 1: Send preview to the creator (Private Chat)
            # This is necessary because animated emojis only work when sent as original entities.
            # Once sent here, we can copy_message it to the channel.

            kb = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="📢 تحويل إلى القناة", callback_data=f"publish_to_channel:{post_id}")]
            ])

            msg = None
            if post.media_type == "photo":
                msg = await bot.send_photo(
                    chat_id=post.creator_id,
                    photo=post.media_file_id,
                    caption=post.text,
                    caption_entities=entities,
                    reply_markup=kb
                )
            elif post.media_type == "video":
                msg = await bot.send_video(
                    chat_id=post.creator_id,
                    video=post.media_file_id,
                    caption=post.text,
                    caption_entities=entities,
                    reply_markup=kb
                )
            else:
                msg = await bot.send_message(
                    chat_id=post.creator_id,
                    text=post.text,
                    entities=entities,
                    reply_markup=kb
                )

            if msg:
                post.preview_message_id = msg.message_id
                post.preview_chat_id = msg.chat.id
                await session.commit()

                # Step 2: If automatic (scheduled), copy it immediately
                if is_automatic:
                    return await perform_copy_to_channel(bot, post_id)

                return True
            return False
        except Exception as e:
            logging.error(f"Failed to send preview for post {post_id}: {e}")
            return False
