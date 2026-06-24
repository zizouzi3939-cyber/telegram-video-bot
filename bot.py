import re
import json
import yt_dlp
from datetime import date
from telegram import Update, LabeledPrice, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler,
    PreCheckoutQueryHandler, filters, ContextTypes, CallbackQueryHandler
)

TOKEN = os.environ.get("TOKEN")

DOWNLOAD_FOLDER = "/tmp/BotDownloads"
os.makedirs(DOWNLOAD_FOLDER, exist_ok=True)

# ملف لتخزين بيانات المستخدمين
DATA_FILE = "/tmp/users_data.json"

FREE_DAILY_LIMIT = 3
STARS_PER_DOWNLOAD = 10


# ===== إدارة البيانات =====

def load_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, 'r') as f:
            return json.load(f)
    return {}

def save_data(data):
    with open(DATA_FILE, 'w') as f:
        json.dump(data, f)

def get_user(user_id):
    data = load_data()
    uid = str(user_id)
    today = str(date.today())
    if uid not in data:
        data[uid] = {"date": today, "count": 0}
    elif data[uid]["date"] != today:
        data[uid] = {"date": today, "count": 0}
    return data, uid

def increment_user(user_id):
    data, uid = get_user(user_id)
    data[uid]["count"] += 1
    save_data(data)

def get_daily_count(user_id):
    data, uid = get_user(user_id)
    save_data(data)
    return data[uid]["count"]


# ===== تنزيل الفيديو =====

def is_valid_url(text):
    return re.search(r'https?://[^\s]+', text)

def download_video(url):
    ydl_opts = {
        'outtmpl': os.path.join(DOWNLOAD_FOLDER, '%(title)s.%(ext)s'),
        'format': 'best[ext=mp4]/best',
        'quiet': True,
        'no_warnings': True,
        'merge_output_format': 'mp4',
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        filename = ydl.prepare_filename(info)
        if not filename.endswith('.mp4'):
            filename = os.path.splitext(filename)[0] + '.mp4'
        return filename


# ===== الأوامر =====

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    count = get_daily_count(user.id)
    remaining = max(0, FREE_DAILY_LIMIT - count)
    await update.message.reply_text(
        f"مرحباً {user.first_name}! 🎬\n\n"
        f"أرسل لي رابط فيديو من:\n"
        f"• YouTube\n• TikTok\n• Instagram\n• Facebook\n\n"
        f"📊 تنزيلاتك المجانية اليوم: {remaining}/{FREE_DAILY_LIMIT}\n"
        f"⭐ بعد الانتهاء: {STARS_PER_DOWNLOAD} Stars لكل تنزيل\n\n"
        f"وسأنزّله لك مباشرة! ✅"
    )

async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    count = get_daily_count(user.id)
    remaining = max(0, FREE_DAILY_LIMIT - count)
    await update.message.reply_text(
        f"📊 إحصائياتك اليوم:\n"
        f"• تنزيلات مستخدمة: {count}\n"
        f"• تنزيلات مجانية متبقية: {remaining}\n"
        f"• سعر التنزيل الإضافي: {STARS_PER_DOWNLOAD} ⭐ Stars"
    )


# ===== معالجة الرسائل =====

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    if not is_valid_url(text):
        await update.message.reply_text("⚠️ أرسل رابطاً صحيحاً!")
        return

    user_id = update.effective_user.id
    count = get_daily_count(user_id)

    if count >= FREE_DAILY_LIMIT:
        # عرض الدفع بـ Stars
        keyboard = [[InlineKeyboardButton(
            f"⭐ ادفع {STARS_PER_DOWNLOAD} Stars للتنزيل",
            callback_data=f"pay|{text}"
        )]]
        await update.message.reply_text(
            f"❌ انتهت تنزيلاتك المجانية اليوم ({FREE_DAILY_LIMIT}/{FREE_DAILY_LIMIT})\n\n"
            f"يمكنك تنزيل هذا الفيديو مقابل {STARS_PER_DOWNLOAD} ⭐ Stars\n"
            f"أو انتظر حتى الغد للحصول على {FREE_DAILY_LIMIT} تنزيلات مجانية جديدة 🕐",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return

    await do_download(update, context, text, user_id)


async def do_download(update, context, url, user_id):
    msg = await update.message.reply_text("⏳ جاري التنزيل...")
    try:
        filename = download_video(url)
        size = os.path.getsize(filename)
        if size > 50 * 1024 * 1024:
            await msg.edit_text("❌ الفيديو أكبر من 50MB.")
            os.remove(filename)
            return
        await msg.edit_text("📤 جاري الإرسال...")
        with open(filename, 'rb') as f:
            await update.message.reply_video(video=f)
        await msg.delete()
        os.remove(filename)
        increment_user(user_id)

        count = get_daily_count(user_id)
        remaining = max(0, FREE_DAILY_LIMIT - count)
        if remaining > 0:
            await update.message.reply_text(
                f"✅ تم التنزيل!\n📊 تنزيلات مجانية متبقية اليوم: {remaining}"
            )
        else:
            await update.message.reply_text(
                f"✅ تم التنزيل!\n⚠️ انتهت تنزيلاتك المجانية اليوم.\n"
                f"التنزيلات الإضافية بـ {STARS_PER_DOWNLOAD} ⭐ Stars"
            )
    except Exception as e:
        await msg.edit_text(f"❌ خطأ:\n{str(e)}")


# ===== نظام Stars =====

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    if data.startswith("pay|"):
        url = data[4:]
        context.user_data["pending_url"] = url
        await context.bot.send_invoice(
            chat_id=query.message.chat_id,
            title="تنزيل فيديو ⭐",
            description=f"تنزيل فيديو واحد مقابل {STARS_PER_DOWNLOAD} Telegram Stars",
            payload="video_download",
            currency="XTR",  # عملة Stars
            prices=[LabeledPrice("تنزيل فيديو", STARS_PER_DOWNLOAD)],
        )

async def pre_checkout(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.pre_checkout_query.answer(ok=True)

async def successful_payment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url = context.user_data.get("pending_url")
    if not url:
        await update.message.reply_text("⚠️ حدث خطأ، أرسل الرابط مجدداً.")
        return
    await update.message.reply_text("✅ تم الدفع! جاري التنزيل...")
    await do_download(update, context, url, update.effective_user.id)


# ===== التشغيل =====

if __name__ == '__main__':
    print("✅ البوت شغّال مع نظام Stars...")
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("stats", stats))
    app.add_handler(CallbackQueryHandler(button_callback))
    app.add_handler(PreCheckoutQueryHandler(pre_checkout))
    app.add_handler(MessageHandler(filters.SUCCESSFUL_PAYMENT, successful_payment))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.run_polling()
