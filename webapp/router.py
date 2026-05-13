from fastapi import FastAPI, Request, Depends, HTTPException, Header
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from database.models import AsyncSessionLocal, Post, CustomEmoji, Admin, Channel
from sqlalchemy import select, update
from utils.publisher import publish_post
from utils.auth import validate_init_data, get_user_id_from_init_data
from utils.emoji_loader import scan_emojis
from aiogram import Bot
import json
import os
import datetime
import logging

app = FastAPI()
app.mount("/static", StaticFiles(directory="webapp/static"), name="static")
templates = Jinja2Templates(directory="webapp/templates")

# Lazy bot initialization
_bot = None

def get_bot():
    global _bot
    if _bot is None:
        token = os.getenv("BOT_TOKEN")
        if not token:
            logging.error("BOT_TOKEN is missing in environment variables")
            return None
        _bot = Bot(token=token)
    return _bot

async def get_db():
    async with AsyncSessionLocal() as db:
        yield db

@app.get("/", response_class=HTMLResponse)
async def index(request: Request, post_id: int = None, db=Depends(get_db)):
    post_data = None
    if post_id:
        try:
            result = await db.execute(select(Post).where(Post.id == int(post_id)))
            post_data = result.scalar_one_or_none()
        except Exception as e:
            logging.error(f"Error fetching post {post_id}: {e}")

    emoji_groups_full = scan_emojis()
    # Optimization: Send only metadata (name + preview) initially
    emoji_groups_meta = {}
    for name, data in emoji_groups_full.items():
        emoji_groups_meta[name] = {
            "preview": data.get("preview", "✨"),
            "count": len(data.get("emojis", []))
        }

    return templates.TemplateResponse(
        request,
        "index.html",
        {
            "post": post_data,
            "emoji_groups": emoji_groups_meta
        }
    )

@app.get("/api/emojis/{group_name}")
async def get_group_emojis(group_name: str):
    emoji_groups = scan_emojis()
    group = emoji_groups.get(group_name)
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")
    return group["emojis"]

@app.get("/api/channels")
async def get_channels(db=Depends(get_db)):
    result = await db.execute(select(Channel).where(Channel.is_active == True))
    channels = result.scalars().all()

    bot = get_bot()
    channel_list = []
    for ch in channels:
        photo_url = None
        try:
            if bot:
                chat = await bot.get_chat(ch.channel_id)
                if chat.photo:
                    # We can't directly give a file_id to the browser.
                    # We need a proxy route to fetch the photo or use a placeholder.
                    # For now, let's just return the info and we'll handle photo via another API.
                    photo_url = f"/api/channel_photo/{ch.channel_id}"
        except Exception as e:
            logging.error(f"Error fetching chat photo for {ch.channel_id}: {e}")

        channel_list.append({
            "id": ch.channel_id,
            "title": ch.title,
            "photo": photo_url
        })
    return channel_list

@app.get("/api/channel_photo/{channel_id}")
async def get_channel_photo(channel_id: int):
    bot = get_bot()
    if not bot:
        raise HTTPException(status_code=500, detail="Bot not configured")
    try:
        chat = await bot.get_chat(channel_id)
        if not chat.photo:
            raise HTTPException(status_code=404, detail="No photo")

        file = await bot.get_file(chat.photo.small_file_id)
        # Download file to a buffer and return it
        from io import BytesIO
        from fastapi.responses import Response

        dest = BytesIO()
        await bot.download_file(file.file_path, dest)
        return Response(content=dest.getvalue(), media_type="image/jpeg")
    except Exception as e:
        logging.error(f"Error downloading photo: {e}")
        raise HTTPException(status_code=404, detail="Photo not found")

@app.post("/save_post")
async def save_post(data: dict, db=Depends(get_db)):
    post_id = data.get("post_id")
    text = data.get("text")
    entities = data.get("entities", [])
    scheduled_at = data.get("scheduled_at")
    channel_id = data.get("channel_id")

    dt_scheduled = None
    if scheduled_at:
        try:
            dt_scheduled = datetime.datetime.fromisoformat(scheduled_at)
        except: pass

    update_vals = {
        "text": text,
        "entities_json": json.dumps(entities),
        "scheduled_at": dt_scheduled
    }
    if channel_id:
        update_vals["channel_id"] = int(channel_id)

    q = update(Post).where(Post.id == post_id).values(**update_vals)
    await db.execute(q)
    await db.commit()
    return {"status": "success"}

@app.post("/publish_now")
async def publish_now_api(data: dict, db=Depends(get_db)):
    post_id = data.get("post_id")
    bot = get_bot()
    if not bot:
        return {"status": "error", "message": "Bot token not configured"}

    success = await publish_post(bot, int(post_id))
    if success:
        return {"status": "success"}
    return {"status": "error", "message": "فشل النشر"}
