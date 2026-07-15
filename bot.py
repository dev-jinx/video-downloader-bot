import os
import subprocess
import sys
import threading
import telebot
import yt_dlp
from http.server import SimpleHTTPRequestHandler, HTTPServer

# Force update yt-dlp on every boot to ensure the latest bypasses
subprocess.check_call([sys.executable, "-m", "pip", "install", "--upgrade", "yt-dlp"])

# --- 1. HEALTH CHECK SERVER ---
def run_health_server():
    class HealthHandler(SimpleHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.send_header("Content-type", "text/plain")
            self.end_headers()
            self.wfile.write(b"Bot is online!")
    port = int(os.environ.get("PORT", 8080))
    server = HTTPServer(("", port), HealthHandler)
    server.serve_forever()

threading.Thread(target=run_health_server, daemon=True).start()

# --- 2. BOT LOGIC ---
BOT_TOKEN = os.environ.get("BOT_TOKEN")
bot = telebot.TeleBot(BOT_TOKEN)

@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    bot.reply_to(message, "👋 Hey! Send me a video link!")

@bot.message_handler(func=lambda message: True)
def download_video(message):
    url = message.text
    if not url.startswith(("http://", "https://")):
        return

    status_msg = bot.reply_to(message, "⚡ Processing your link...")
    os.makedirs("downloads", exist_ok=True)
    
    # We use a more aggressive format string and explicit cookie handling
    ydl_opts = {
        'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
        'outtmpl': 'downloads/%(title)s_%(id)s.%(ext)s',
        'merge_output_format': 'mp4',
        'quiet': False, # Changed to False to help you debug in logs
        'no_warnings': False,
        'cookiefile': 'cookies.txt' if os.path.exists('cookies.txt') else None,
        'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
    }
    
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            filename = ydl.prepare_filename(info)
            base, _ = os.path.splitext(filename)
            final_file = f"{base}.mp4" if os.path.exists(f"{base}.mp4") else filename

        with open(final_file, "rb") as video_file:
            bot.send_document(message.chat.id, video_file, disable_content_type_detection=True)
        
        if os.path.exists(final_file):
            os.remove(final_file)
        bot.delete_message(message.chat.id, status_msg.message_id)
    except Exception as e:
        error_msg = str(e)
        bot.edit_message_text(f"❌ Error: {error_msg[:100]}", message.chat.id, status_msg.message_id)
        print(f"DEBUG ERROR: {e}")

bot.infinity_polling()
