import os
import threading
import telebot
import yt_dlp
from http.server import SimpleHTTPRequestHandler, HTTPServer

# --- 1. HEALTH CHECK SERVER (Required by Render to stay online) ---
def run_health_server():
    class HealthHandler(SimpleHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.send_header("Content-type", "text/plain")
            self.end_headers()
            self.wfile.write(b"Bot is online!")

    port = int(os.environ.get("PORT", 8080))
    server = HTTPServer(("", port), HealthHandler)
    print(f"Health server running on port {port}...")
    server.serve_forever()

# Start the health server in a background thread
threading.Thread(target=run_health_server, daemon=True).start()

# --- 2. TELEGRAM BOT LOGIC ---
BOT_TOKEN = os.environ.get("BOT_TOKEN")
if not BOT_TOKEN:
    raise ValueError("No BOT_TOKEN found in environment variables!")

bot = telebot.TeleBot(BOT_TOKEN)

@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    # Keeping your custom welcome message!
    bot.reply_to(
        message, 
        "👋 Hey! Send me a video link!"
    )

@bot.message_handler(func=lambda message: True)
def download_video(message):
    url = message.text
    if not url.startswith(("http://", "https://")):
        bot.reply_to(message, "⚠️ Please send a valid link starting with http or https.")
        return

    status_msg = bot.reply_to(message, "⚡ Processing your link... Please wait.")
    
    # Create a clean folder for temporary downloads
    os.makedirs("downloads", exist_ok=True)
    output_template = "downloads/%(title)s_%(id)s.%(ext)s"
    
    # Base configuration for yt-dlp
    ydl_opts = {
        'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
        'outtmpl': output_template,
        'merge_output_format': 'mp4',
        'quiet': True,
        'no_warnings': True,
        'nocheckcertificate': True,
        'headers': {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9',
        },
        'extractor_args': {
            'youtube': {
                'player_client': ['tvhtml5', 'android'],
                'player_skip': ['configs', 'webpage'],
            }
        }
    }

    # Automatically load cookies if they exist in the repository
    cookies_file = "cookies.txt"
    if os.path.exists(cookies_file):
        ydl_opts['cookiefile'] = cookies_file
        print("Using exported cookies to bypass bot blocks!")
    else:
        print("No cookies.txt found. Proceeding without session cookies.")

    try:
        bot.edit_message_text("📥 Downloading layers...", message.chat.id, status_msg.message_id)
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            filename = ydl.prepare_filename(info)
            
            # Handle instances where format merges changed the extension
            base, _ = os.path.splitext(filename)
            mp4_filename = f"{base}.mp4"
            final_file = mp4_filename if os.path.exists(mp4_filename) else filename

        # Check file size (Telegram Bot API limit is 50MB)
        file_size_mb = os.path.getsize(final_file) / (1024 * 1024)
        if file_size_mb > 50:
            bot.edit_message_text(
                f"⚠️ File is too large ({file_size_mb:.1f}MB). Telegram restricts bot uploads to 50MB.", 
                message.chat.id, 
                status_msg.message_id
            )
            if os.path.exists(final_file):
                os.remove(final_file)
            return

        bot.edit_message_text("📤 Sending uncompressed file...", message.chat.id, status_msg.message_id)
        
        # Sends file as a clean, raw document file card
        with open(final_file, "rb") as video_file:
            bot.send_document(
                message.chat.id, 
                video_file, 
                timeout=180, 
                disable_content_type_detection=True
            )
        
        # Clean up disk space
        os.remove(final_file)
        bot.delete_message(message.chat.id, status_msg.message_id)

    except Exception as e:
        bot.edit_message_text(
            "❌ Error downloading video. The link might be private, blocked by the host, or temporarily down.", 
            message.chat.id, 
            status_msg.message_id
        )
        print(f"Error encountered: {e}")
        # Clean up any partial files if download failed
        if 'final_file' in locals() and os.path.exists(final_file):
            os.remove(final_file)

print("Bot is ready and starting polling...")
bot.infinity_polling()
