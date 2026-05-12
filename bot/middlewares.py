from aiogram import BaseMiddleware
from aiogram.types import Message
from typing import Any, Awaitable, Callable, Dict
from database.models import AsyncSessionLocal, Admin
from sqlalchemy import select

class AuthMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[Any, Dict[str, Any]], Awaitable[Any]],
        event: Any,
        data: Dict[str, Any]
    ) -> Any:
        user = getattr(event, "from_user", None)
        if not user:
            return await handler(event, data)

        async with AsyncSessionLocal() as session:
            result = await session.execute(select(Admin).where(Admin.user_id == user.id))
            admin = result.scalar_one_or_none()

            if admin:
                data["is_admin"] = True
                data["is_owner"] = admin.is_owner
                return await handler(event, data)

            import os
            owner_id = int(os.getenv("OWNER_ID", 0))
            if user.id == owner_id:
                data["is_admin"] = True
                data["is_owner"] = True
                return await handler(event, data)

        # If not authorized, send access denied message and return
        if hasattr(event, "answer"):
            if isinstance(event, Message):
                await event.answer("⚠️ غير مصرح لك باستخدام البوت.")
            else: # CallbackQuery
                await event.answer("⚠️ غير مصرح لك باستخدام البوت.", show_alert=True)
        return
