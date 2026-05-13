from aiogram import Router, F, types
from aiogram.filters import Command, StateFilter
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo
from database.models import AsyncSessionLocal, Admin, Channel, CustomEmoji, Post
from sqlalchemy import select, insert, delete, update
import os
import json

router = Router()

class BotStates(StatesGroup):
    waiting_for_channel = State()
    waiting_for_admin = State()

def get_webapp_url():
    url = os.getenv("WEBAPP_URL")
    if not url or "your-webapp-url.com" in url:
        return None
    return url

@router.message(Command("config"))
async def cmd_config(message: types.Message, is_owner: bool = False):
    if not is_owner: return

    webapp_url = os.getenv("WEBAPP_URL")
    db_url = os.getenv("DATABASE_URL")

    status = "✅ مضبوط" if webapp_url and "your-webapp-url.com" not in webapp_url else "❌ غير مضبوط"

    text = (
        "⚙️ **إعدادات البوت الحالية:**\n\n"
        f"🔗 **رابط WebApp:** `{webapp_url}`\n"
        f"📊 **الحالة:** {status}\n\n"
        f"📁 **قاعدة البيانات:** `{db_url}`\n"
        f"👤 **معرف المالك:** `{os.getenv('OWNER_ID')}`\n\n"
        "💡 لتغيير هذه الإعدادات، يرجى تعديلها في لوحة تحكم Render (Environment Variables)."
    )
    await message.answer(text, parse_mode="Markdown")

@router.message(Command("start"))
async def cmd_start(message: types.Message, state: FSMContext, is_admin: bool = False, is_owner: bool = False):
    try:
        await state.clear()
        webapp_url = get_webapp_url()

        kb = []
        # Ensure the button always appears if a URL exists, regardless of placeholder check if needed,
        # but here we follow get_webapp_url logic
        url = webapp_url or os.getenv("WEBAPP_URL")

        if url:
            kb.append([InlineKeyboardButton(text="فتح محرر المنشورات 📝", web_app=WebAppInfo(url=url))])

        if is_owner:
            kb.append([InlineKeyboardButton(text="إعدادات القنوات 📺", callback_data="settings_channels")])
            kb.append([InlineKeyboardButton(text="إدارة الأدمنز 👥", callback_data="settings_admins")])

        msg = "أهلاً بك في لوحة التحكم!"
        await message.answer(msg, reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))
    except Exception:
        pass

@router.message(StateFilter(None), F.photo | F.video | F.text)
async def handle_post_content(message: types.Message, is_admin: bool = False):
    if not is_admin: return

    webapp_url = get_webapp_url()
    if not webapp_url:
        return

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

    url_base = get_webapp_url()
    webapp_url = f"{url_base}?post_id={new_post.id}" if url_base else None

    kb = []
    if webapp_url:
        kb.append([InlineKeyboardButton(text="تعديل المنشور في WebApp 🎨", web_app=WebAppInfo(url=webapp_url))])

    await message.answer(f"تم استلام المحتوى. يمكنك الآن تعديله وإضافة إيموجي مميز عبر الرابط أدناه. (رقم المسودة: {new_post.id})",
                         reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))

# Admin Management
@router.callback_query(F.data == "settings_admins")
async def manage_admins(callback: types.CallbackQuery, state: FSMContext, is_owner: bool = False):
    if not is_owner: return

    await state.set_state(BotStates.waiting_for_admin)
    kb = [[InlineKeyboardButton(text="❌ إلغاء", callback_data="cancel_operation")]]

    async with AsyncSessionLocal() as session:
        stmt = select(Admin).where(Admin.is_owner == False)
        admins = (await session.execute(stmt)).scalars().all()

    text = "👥 **قائمة المسؤولين الحالية:**\n\n"
    if not admins:
        text += "لا يوجد مسؤولين حالياً.\n"
    for admin in admins:
        text += f"- `{admin.user_id}` {f'(@{admin.username})' if admin.username else ''} /remove_{admin.user_id}\n"

    text += "\n➕ لإضافة مسؤول جديد، أرسل اليوزر الخاص به مباشرة (مثال: @username) أو المعرف (ID)."
    await callback.message.answer(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))

@router.message(BotStates.waiting_for_admin, F.text)
async def handle_admin_addition_state(message: types.Message, state: FSMContext, is_owner: bool = False):
    if not is_owner: return

    input_data = message.text.strip()
    user_id = None
    username = None

    try:
        if input_data.startswith("@"):
            username = input_data.replace("@", "")
            try:
                chat = await message.bot.get_chat(input_data)
                if chat.type != "private":
                    await message.answer("❌ هذا اليوزر ليس لمستخدم (Private User).")
                    return
                user_id = chat.id
            except Exception as e:
                import logging
                logging.error(f"Error fetching user {input_data}: {e}")
                await message.answer("❌ لم أتمكن من العثور على المستخدم عبر اليوزر. تأكد من اليوزر.")
                return
        elif input_data.isdigit():
            user_id = int(input_data)
        else:
            await message.answer("❌ يرجى إرسال يوزر صحيح (@username) أو معرف (ID).")
            return

        async with AsyncSessionLocal() as session:
            stmt = select(Admin).where(Admin.user_id == user_id)
            existing = (await session.execute(stmt)).scalar_one_or_none()

            if existing:
                await message.answer("ℹ️ هذا المستخدم مضاف بالفعل كمسؤول.")
            else:
                session.add(Admin(user_id=user_id, username=username))
                await session.commit()
                await message.answer(f"✅ تم إضافة الأدمن بنجاح\n\nID: `{user_id}`" + (f"\nيوزر: @{username}" if username else ""))
                await state.clear()
    except Exception as e:
        import logging
        logging.error(f"Unexpected error in admin addition: {e}")
        await message.answer(f"❌ حدث خطأ غير متوقع.")

@router.message(BotStates.waiting_for_admin)
async def handle_admin_addition_wrong_content(message: types.Message):
    await message.answer("⚠️ يرجى إرسال اليوزر أو المعرف كنص، أو اضغط على إلغاء.")

# Remove legacy handlers that were not state-based

@router.message(F.text.startswith("/remove_"))
async def remove_admin(message: types.Message, is_owner: bool = False):
    if not is_owner: return
    try:
        user_id = int(message.text.split("_")[1])
        async with AsyncSessionLocal() as session:
            stmt = delete(Admin).where(Admin.user_id == user_id, Admin.is_owner == False)
            result = await session.execute(stmt)
            await session.commit()

            if result.rowcount > 0:
                await message.answer(f"✅ تم إزالة المسؤول `{user_id}` بنجاح.")
            else:
                await message.answer("❌ لم يتم العثور على مسؤول بهذا المعرف.")
    except Exception as e:
        await message.answer(f"❌ خطأ: {e}")

# Channel Management
@router.callback_query(F.data == "settings_channels")
async def manage_channels(callback: types.CallbackQuery, state: FSMContext, is_owner: bool = False):
    if not is_owner: return
    await state.set_state(BotStates.waiting_for_channel)
    kb = [[InlineKeyboardButton(text="❌ إلغاء", callback_data="cancel_operation")]]
    await callback.message.answer("لإضافة قناة جديدة، قم بإرسال رابط القناة أو اليوزر الخاص بها مباشرة.\nمثال: @mychannel أو https://t.me/mychannel",
                                 reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))

@router.message(BotStates.waiting_for_channel, F.text)
async def handle_channel_addition_state(message: types.Message, state: FSMContext, is_owner: bool = False):
    if not is_owner: return

    link = message.text.strip()
    if "t.me/" in link:
        parts = link.split("t.me/")[1].split("/")
        if parts[0] == "c":
            await message.answer("⚠️ يرجى إرسال يوزر القناة العام أو ID القناة. الروابط الخاصة غير مدعومة حالياً عبر الرابط.")
            return
        link = "@" + parts[0]

    try:
        try:
            chat = await message.bot.get_chat(link)
            if chat.type != "channel":
                await message.answer("❌ هذا اليوزر ليس لقناة.")
                return
            channel_id = chat.id
            title = chat.title
        except Exception as e:
            import logging
            logging.error(f"Error fetching channel {link}: {e}")
            await message.answer(f"❌ لم أتمكن من العثور على القناة. تأكد من صحة الرابط وأنني عضو فيها.")
            return

        # Verify if bot is admin in the channel
        try:
            member = await message.bot.get_chat_member(chat_id=channel_id, user_id=message.bot.id)
            if member.status not in ["administrator", "creator"]:
                await message.answer(f"❌ البوت ليس مسؤولاً في القناة '{title}'. يرجى رفعه لمسؤول أولاً.")
                return

            if member.status == "administrator" and not member.can_post_messages:
                await message.answer(f"❌ البوت مسؤول في القناة ولكن ليس لديه صلاحية 'نشر الرسائل'. يرجى تفعيلها.")
                return
        except Exception as e:
            import logging
            logging.error(f"Error checking bot permissions in {channel_id}: {e}")
            await message.answer(f"❌ لا يمكنني التحقق من صلاحياتي في القناة.")
            return

        async with AsyncSessionLocal() as session:
            stmt_count = select(Channel).where(Channel.is_active == True)
            active_channels = (await session.execute(stmt_count)).scalars().all()

            stmt = select(Channel).where(Channel.channel_id == channel_id)
            existing = (await session.execute(stmt)).scalar_one_or_none()

            if existing:
                if not existing.is_active and len(active_channels) >= 5:
                    await message.answer("⚠️ وصلت للحد الأقصى من القنوات النشطة (5 قنوات). يرجى تعطيل قناة قبل إضافة جديدة.")
                    return
                existing.is_active = True
                existing.title = title
            else:
                if len(active_channels) >= 5:
                    await message.answer("⚠️ وصلت للحد الأقصى من القنوات النشطة (5 قنوات). يرجى تعطيل قناة قبل إضافة جديدة.")
                    return
                session.add(Channel(channel_id=channel_id, title=title, is_active=True))

            await session.commit()

        await message.answer(f"✅ تم ربط القناة بنجاح\n\nاسم القناة: **{title}**")
        await state.clear()
    except Exception as e:
        import logging
        logging.error(f"Unexpected error in channel addition: {e}")
        await message.answer(f"❌ حدث خطأ غير متوقع.")

@router.message(BotStates.waiting_for_channel)
async def handle_channel_addition_wrong_content(message: types.Message):
    await message.answer("⚠️ يرجى إرسال رابط القناة أو اليوزر كنص، أو اضغط على إلغاء.")

async def handle_channel_link(message: types.Message, is_owner: bool = False):
    # This is a fallback for legacy calls if any, we'll keep it simple
    if not is_owner: return
    # We can just redirect to the state handler if we want, or implement it here too.
    # But for simplicity, we'll just advise using the button.
    await message.answer("يرجى استخدام الأزرار من القائمة الرئيسية لإضافة القناة.")

@router.callback_query(F.data == "cancel_operation")
async def cancel_operation(callback: types.CallbackQuery, state: FSMContext, is_admin: bool = False, is_owner: bool = False):
    await state.clear()
    await callback.answer("تم الإلغاء")
    await cmd_start(callback.message, state, is_admin=is_admin, is_owner=is_owner)

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
