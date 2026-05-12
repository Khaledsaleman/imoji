from fastapi import FastAPI, Request, Depends, HTTPException, Header
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from database.models import AsyncSessionLocal, Post, CustomEmoji, Admin
from sqlalchemy import select, update
from utils.publisher import publish_post
from utils.auth import validate_init_data
from aiogram import Bot
import json
import os

app = FastAPI()
app.mount("/static", StaticFiles(directory="webapp/static"), name="static")
templates = Jinja2Templates(directory="webapp/templates")

bot = Bot(token=os.getenv("BOT_TOKEN"))

async def get_db():
    async with AsyncSessionLocal() as db:
        yield db

async def verify_user(request: Request, db=Depends(get_db)):
    # In a real scenario, the client sends initData in a header
    init_data = request.headers.get("X-Telegram-Init-Data")
    if not init_data:
        # For development/preview, we might allow it, but for production it's strict
        if os.getenv("ENV") == "dev": return True
        raise HTTPException(status_code=401, detail="Unauthorized")

    if not validate_init_data(os.getenv("BOT_TOKEN"), init_data):
        raise HTTPException(status_code=401, detail="Invalid init data")

    # Further check if user is admin
    user_id = get_user_id_from_init_data(init_data)
    res = await db.execute(select(Admin).where(Admin.user_id == user_id))
    if not res.scalar_one_or_none():
        raise HTTPException(status_code=403, detail="Not an admin")
    return True

@app.get("/", response_class=HTMLResponse)
async def index(request: Request, post_id: int = None, db=Depends(get_db)):
    post_data = None
    if post_id:
        result = await db.execute(select(Post).where(Post.id == int(post_id)))
        post_data = result.scalar_one_or_none()

    emojis_result = await db.execute(select(CustomEmoji))
    emojis = emojis_result.scalars().all()

    return templates.TemplateResponse(
        request,
        "index.html",
        {
            "post": post_data,
            "emojis": emojis
        }
    )

@app.post("/save_post")
async def save_post(data: dict, db=Depends(get_db)):
    post_id = data.get("post_id")
    text = data.get("text")
    entities = data.get("entities", [])
    scheduled_at = data.get("scheduled_at")

    allowed_emojis_res = await db.execute(select(CustomEmoji.custom_emoji_id))
    allowed_ids = set(allowed_emojis_res.scalars().all())

    validated_entities = []
    for ent in entities:
        if ent.get("type") == "custom_emoji":
            emoji_id = str(ent.get("custom_emoji_id"))
            if emoji_id in allowed_ids:
                validated_entities.append(ent)
        else:
            validated_entities.append(ent)

    # Convert scheduled_at string to datetime if present
    import datetime
    dt_scheduled = None
    if scheduled_at:
        try:
            dt_scheduled = datetime.datetime.fromisoformat(scheduled_at)
        except: pass

    q = update(Post).where(Post.id == post_id).values(
        text=text,
        entities_json=json.dumps(validated_entities),
        scheduled_at=dt_scheduled
    )
    await db.execute(q)
    await db.commit()
    return {"status": "success"}

@app.post("/publish_now")
async def publish_now_api(data: dict, db=Depends(get_db)):
    post_id = data.get("post_id")
    success = await publish_post(bot, int(post_id))
    if success:
        return {"status": "success"}
    return {"status": "error", "message": "فشل النشر"}
