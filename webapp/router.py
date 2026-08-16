from fastapi import FastAPI, Request, Depends, HTTPException, Header
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from database.models import AsyncSessionLocal, Post, CustomEmoji, Admin, Channel
from sqlalchemy import select, update
from utils.publisher import publish_post
from utils.auth import validate_init_data, get_user_id_from_init_data
from utils.emoji_loader import scan_emojis, get_all_emojis
from aiogram import Bot
from aiogram.types import Update
import json
import os
import datetime
import logging

# Ensure static and templates directories exist using absolute paths to prevent Render errors
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(BASE_DIR)
STATIC_DIR = os.path.join(BASE_DIR, "static")
TEMPLATES_DIR = os.path.join(BASE_DIR, "templates")

os.makedirs(STATIC_DIR, exist_ok=True)
os.makedirs(TEMPLATES_DIR, exist_ok=True)

app = FastAPI()
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
templates = Jinja2Templates(directory=TEMPLATES_DIR)

# Lazy bot initialization
_bot = None

def get_bot():
    bot = getattr(app.state, "bot", None)
    if bot is not None:
        return bot
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

@app.post("/webhook/bot")
async def telegram_webhook(request: Request):
    bot = getattr(app.state, "bot", None)
    dp = getattr(app.state, "dp", None)
    if not bot or not dp:
        logging.error("Webhook received but Bot or Dispatcher not initialized in app.state.")
        raise HTTPException(status_code=503, detail="Bot or Dispatcher not initialized")

    try:
        update_data = await request.json()
        update = Update.model_validate(update_data, context={"bot": bot})
        await dp.feed_update(bot, update)
        return {"status": "ok"}
    except Exception as e:
        logging.error(f"Error handling webhook update: {e}", exc_info=True)
        return {"status": "error", "message": str(e)}

@app.get("/api/health")
async def health_check(db=Depends(get_db)):
    status = {"database": "unknown", "bot_connectivity": "unknown"}

    # 1. Check Database Connectivity
    try:
        from sqlalchemy import text
        await db.execute(text("SELECT 1"))
        status["database"] = "ok"
    except Exception as e:
        status["database"] = f"error: {str(e)}"
        logging.error(f"Health check: Database check failed: {e}", exc_info=True)

    # 2. Check Bot Connectivity
    bot = get_bot()
    if bot:
        try:
            me = await bot.get_me()
            status["bot_connectivity"] = "ok"
            status["bot_username"] = me.username

            # Check webhook details
            url_env = os.getenv("WEBAPP_URL")
            if url_env and "your-webapp-url.com" not in url_env:
                webhook_info = await bot.get_webhook_info()
                status["webhook"] = {
                    "enabled": True,
                    "url": webhook_info.url,
                    "pending_update_count": webhook_info.pending_update_count,
                    "last_error_date": webhook_info.last_error_date,
                    "last_error_message": webhook_info.last_error_message,
                }
            else:
                status["webhook"] = {
                    "enabled": False,
                    "mode": "polling"
                }
        except Exception as e:
            status["bot_connectivity"] = f"error: {str(e)}"
            logging.error(f"Health check: Telegram Bot connectivity failed: {e}", exc_info=True)
    else:
        status["bot_connectivity"] = "not_configured"

    # If database is down or bot has error (and is expected to be configured)
    if "error" in status["database"] or "error" in status["bot_connectivity"]:
        raise HTTPException(status_code=500, detail=status)

    return status

@app.get("/", response_class=HTMLResponse)
async def index(request: Request, post_id: int = None, db=Depends(get_db)):
    post_data = None
    if post_id:
        try:
            result = await db.execute(select(Post).where(Post.id == int(post_id)))
            post_data = result.scalar_one_or_none()
        except Exception as e:
            logging.error(f"Error fetching post {post_id}: {e}")

    # Use the optimized merged emoji list
    emoji_groups_full = await get_all_emojis()

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
    emoji_groups = await get_all_emojis()
    group = emoji_groups.get(group_name)
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")
    return group["emojis"]

@app.get("/api/emoji_raw/{group_name}/{emoji_id}")
async def get_emoji_raw(group_name: str, emoji_id: str):
    # Security: check if group and emoji_id look safe
    if ".." in group_name or ".." in emoji_id:
         raise HTTPException(status_code=400, detail="Invalid path")

    # Check possible paths (using absolute paths)
    paths = [
        os.path.join(PROJECT_ROOT, "emojis"),
        os.path.join(PROJECT_ROOT, "imoji", "emojis")
    ]
    for base in paths:
        file_path = os.path.join(base, group_name, f"{emoji_id}.json")
        if os.path.exists(file_path):
            with open(file_path, "r") as f:
                return json.load(f)

    raise HTTPException(status_code=404, detail="Emoji file not found")

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

async def _save_post_data(data: dict, db, user_id: int = None):
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

    if post_id and str(post_id).isdigit():
        # Update existing post
        update_vals = {
            "text": text,
            "entities_json": json.dumps(entities),
            "scheduled_at": dt_scheduled
        }
        if channel_id:
            try:
                update_vals["channel_id"] = int(channel_id)
            except: pass

        q = update(Post).where(Post.id == int(post_id)).values(**update_vals)
        await db.execute(q)
        await db.commit()
        return int(post_id)
    else:
        # Create new post
        new_post = Post(
            creator_id=user_id or 0,
            text=text,
            entities_json=json.dumps(entities),
            scheduled_at=dt_scheduled,
            channel_id=int(channel_id) if channel_id else None
        )
        db.add(new_post)
        await db.commit()
        await db.refresh(new_post)
        return new_post.id

@app.post("/save_post")
async def save_post_api(data: dict, x_telegram_init_data: str = Header(None, alias="X-Telegram-Init-Data"), db=Depends(get_db)):
    try:
        user_id = get_user_id_from_init_data(x_telegram_init_data)
        new_id = await _save_post_data(data, db, user_id)
        return {"status": "success", "post_id": new_id}
    except Exception as e:
        logging.error(f"Error in save_post_api: {e}")
        return {"status": "error", "message": str(e)}

@app.post("/publish_now")
async def publish_now_api(data: dict, x_telegram_init_data: str = Header(None, alias="X-Telegram-Init-Data"), db=Depends(get_db)):
    try:
        user_id = get_user_id_from_init_data(x_telegram_init_data)
        # First save the content to ensure we publish the latest version
        post_id = await _save_post_data(data, db, user_id)

        bot = get_bot()
        if not bot:
            return {"status": "error", "message": "Bot token not configured"}

        success = await publish_post(bot, int(post_id))
        if success:
            return {"status": "success"}
        return {"status": "error", "message": "فشل النشر"}
    except Exception as e:
        logging.error(f"Error in publish_now_api: {e}")
        return {"status": "error", "message": str(e)}
