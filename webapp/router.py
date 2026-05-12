from fastapi import FastAPI, Request, Depends, HTTPException, Header
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from database.models import AsyncSessionLocal, Post, CustomEmoji, Admin
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

    emoji_groups = scan_emojis()

    return templates.TemplateResponse(
        request,
        "index.html",
        {
            "post": post_data,
            "emoji_groups": emoji_groups
        }
    )

@app.post("/save_post")
async def save_post(data: dict, db=Depends(get_db)):
    post_id = data.get("post_id")
    text = data.get("text")
    entities = data.get("entities", [])
    scheduled_at = data.get("scheduled_at")

    dt_scheduled = None
    if scheduled_at:
        try:
            dt_scheduled = datetime.datetime.fromisoformat(scheduled_at)
        except: pass

    q = update(Post).where(Post.id == post_id).values(
        text=text,
        entities_json=json.dumps(entities),
        scheduled_at=dt_scheduled
    )
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
