import os
import threading
import telebot
import yt_dlp
import subprocess
import sys
from http.server import SimpleHTTPRequestHandler, HTTPServer

# --- AUTOMATIC SELF-UPDATE ---
print("Checking for yt-dlp updates...")
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
        bot.reply_to(message, "⚠️ Please send a valid link starting with http or https.")
        return

    status_msg = bot.reply_to(message, "⚡ Processing your link...")
    os.makedirs("downloads", exist_ok=True)
    
    ydl_opts = {
        'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
        'outtmpl': 'downloads/%(title)s_%(id)s.%(ext)s',
        'merge_output_format': 'mp4',
        'quiet': True,
        'headers': {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'},
        'extractor_args': {'youtube': {'player_client': ['tvhtml5', 'android']}}
    }
    
    if os.path.exists("cookies.txt"):
        ydl_opts['cookiefile'] = "cookies.txt"

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            filename = ydl.prepare_filename(info)
            base, _ = os.path.splitext(filename)
            final_file = f"{base}.mp4" if os.path.exists(f"{base}.mp4") else filename

        with open(final_file, "rb") as video_file:
            bot.send_document(message.chat.id, video_file, disable_content_type_detection=True)
        
        os.remove(final_file)
        bot.delete_message(message.chat.id, status_msg.message_id)
    except Exception as e:
        bot.edit_message_text("❌ Error downloading. Link might be private or blocked.", message.chat.id, status_msg.message_id)
        print(f"Error: {e}")

bot.infinity_polling()
