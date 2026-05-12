# بوت محرر المنشورات الاحترافي (Render Edition)

## طريقة الرفع على Render
1. قم بإنشاء حساب على [Render](https://render.com).
2. اربط حسابك بـ GitHub واختر هذا المستودع.
3. اختر نوع الخدمة **Web Service**.
4. الإعدادات المطلوبة:
   - **Runtime:** Python
   - **Build Command:** `pip install -r requirements.txt`
   - **Start Command:** `python main.py`
5. أضف متغيرات البيئة (Environment Variables) في Render:
   - `BOT_TOKEN`: توكن البوت الخاص بك.
   - `OWNER_ID`: معرف التليجرام الخاص بك.
   - `WEBAPP_URL`: الرابط الذي سيمنحه لك Render (سينتهي بـ `.onrender.com`).
   - `DATABASE_URL`: `sqlite+aiosqlite:///./bot_database.db` (أو استخدم PostgreSQL).

## ملاحظة
رابط الـ WebApp الذي سيظهر لك في Render هو الذي يجب وضعه في `WEBAPP_URL` لكي تفتح الأزرار بشكل صحيح.
