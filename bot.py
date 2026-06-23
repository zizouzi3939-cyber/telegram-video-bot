import os
import re
import yt_dlp
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes

TOKEN = os.environ.get("TOKEN")

DOWNLOAD_FOLDER = "/tmp/BotDownloads"
os.makedirs(DOWNLOAD_FOLDER, exist_ok=True)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "مرحباً! 🎬\n"
        "أرسل لي رابط فيديو من:\n"
        "• YouTube\n"
        "• TikTok\n"
        "• Instagram\n"
        "• Facebook\n\n"
        "وسأنزّله لك مباشرة! ✅"
    )

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

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    if not is_valid_url(text):
        await update.message.reply_text("⚠️ أرسل رابطاً صحيحاً!")
        return
    msg = await update.message.reply_text("⏳ جاري التنزيل...")
    try:
        filename = download_video(text)
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
    except Exception as e:
        await msg.edit_text(f"❌ خطأ:\n{str(e)}")

if __name__ == '__main__':
    print("✅ البوت شغّال...")
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.run_polling()
