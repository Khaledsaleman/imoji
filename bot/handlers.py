from aiogram import Router, F, types
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo
from database.models import AsyncSessionLocal, Admin, Channel, CustomEmoji, Post
from sqlalchemy import select, insert, delete
import os
import json

router = Router()

@router.message(Command("start"))
async def cmd_start(message: types.Message, is_admin: bool = False):
    if not is_admin:
        await message.answer("مرحباً بك. هذا البوت مخصص لإدارة القنوات والنشر الاحترافي.")
        return

    kb = [
        [InlineKeyboardButton(text="فتح محرر المنشورات 📝", web_app=WebAppInfo(url=os.getenv("WEBAPP_URL")))],
        [InlineKeyboardButton(text="إعدادات القنوات 📺", callback_data="settings_channels")],
        [InlineKeyboardButton(text="إدارة الأدمنز 👥", callback_data="settings_admins")]
    ]
    await message.answer("أهلاً بك في لوحة التحكم!", reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))

@router.message(F.photo | F.video | F.text)
async def handle_post_content(message: types.Message, is_admin: bool = False):
    if not is_admin: return

    media_file_id = None
    media_type = None
    text = message.text or message.caption

    if message.photo:
        media_file_id = message.photo[-1].file_id
        media_type = "photo"
    elif message.video:
        media_file_id = message.video.file_id
        media_type = "video"

    async with AsyncSessionLocal() as session:
        new_post = Post(
            creator_id=message.from_user.id,
            text=text,
            media_file_id=media_file_id,
            media_type=media_type
        )
        session.add(new_post)
        await session.commit()
        await session.refresh(new_post)

    webapp_url = f"{os.getenv('WEBAPP_URL')}?post_id={new_post.id}"
    kb = [[InlineKeyboardButton(text="تعديل المنشور في WebApp 🎨", web_app=WebAppInfo(url=webapp_url))]]

    await message.answer(f"تم استلام المحتوى. يمكنك الآن تعديله وإضافة إيموجي مميز عبر الرابط أدناه. (رقم المسودة: {new_post.id})",
                         reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))

# Admin Management
@router.callback_data(F.data == "settings_admins")
async def manage_admins(callback: types.CallbackQuery, is_owner: bool = False):
    if not is_owner:
        await callback.answer("عذراً، هذه الصلاحية للمالك فقط.", show_alert=True)
        return
    await callback.message.answer("أرسل ID المستخدم لتعيينه كأدمن، أو استخدم الأمر: \n `/add_admin 12345678`", parse_mode="Markdown")

@router.message(Command("add_admin"))
async def add_admin(message: types.Message, is_owner: bool = False):
    if not is_owner: return
    try:
        user_id = int(message.text.split()[1])
        async with AsyncSessionLocal() as session:
            session.add(Admin(user_id=user_id))
            await session.commit()
        await message.answer(f"تم إضافة {user_id} كمسؤول.")
    except Exception:
        await message.answer("خطأ في إضافة المسؤول. تأكد من الصيغة: /add_admin 12345678")

# Channel Management
@router.callback_data(F.data == "settings_channels")
async def manage_channels(callback: types.CallbackQuery, is_owner: bool = False):
    if not is_owner: return
    await callback.message.answer("لإضافة قناة، أرسل ID القناة مسبوقاً بـ /add_channel \n مثال: `/add_channel -10012345678`", parse_mode="Markdown")

@router.message(Command("add_channel"))
async def add_channel(message: types.Message, is_owner: bool = False):
    if not is_owner: return
    try:
        channel_id = int(message.text.split()[1])
        async with AsyncSessionLocal() as session:
            session.add(Channel(channel_id=channel_id))
            await session.commit()
        await message.answer(f"تم ربط القناة {channel_id} بنجاح.")
    except Exception:
        await message.answer("خطأ في ربط القناة. تأكد من الـ ID.")

@router.message(Command("import_emojis"))
async def import_emojis(message: types.Message, is_owner: bool = False):
    if not is_owner: return
    try:
        data = json.loads(message.text.replace("/import_emojis", "").strip())
        async with AsyncSessionLocal() as session:
            for eid in data:
                # Use a proper check or merge for existing IDs
                stmt = select(CustomEmoji).where(CustomEmoji.custom_emoji_id == str(eid))
                exists = (await session.execute(stmt)).scalar_one_or_none()
                if not exists:
                    session.add(CustomEmoji(custom_emoji_id=str(eid)))
            await session.commit()
        await message.answer("تم استيراد الإيموجي بنجاح.")
    except Exception as e:
        await message.answer(f"خطأ في الاستيراد: {e}")
