import os
import threading
import requests
import telebot
import time
from flask import Flask
from functools import wraps

# ========================================================
# 1. RENDER FREE TIER COMPATIBILITY (FLASK SERVER)
# ========================================================
app = Flask('')

@app.route('/')
def home():
    return "Bot is active and running!"

def run_web_server():
    # Bind to Render's dynamic port to satisfy port scan
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

threading.Thread(target=run_web_server, daemon=True).start()

# ========================================================
# 2. CONFIGURATIONS & TOKEN
# ========================================================
# Your persistent Telegram Bot Token
TELEGRAM_TOKEN = "8992190983:AAGdOir-jXPcW9LrhAuexkjwpe1xBsRCZf4"
# Microsoft Copilot Token Endpoint
COPILOT_ENDPOINT = "https://default3476b776e9904f72b9506248983162.3d.environment.api.powerplatform.com/powervirtualagents/botsbyschema/crba2_golfRulesHumorMaster/directline/token?api-version=2022-03-01-preview"

bot = telebot.TeleBot(TELEGRAM_TOKEN)
user_sessions = {}

# ========================================================
# 3. AUTOMATED 409 CONFLICT HANDLING (RETRY LOGIC)
# ========================================================
def retry_with_backoff(retries=5, initial_delay=2):
    """Decorator to automate recovery from 409 Conflicts."""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            attempts = 0
            delay = initial_delay
            while attempts < retries:
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    if "409" in str(e):  # Catch Conflict error
                        attempts += 1
                        print(f"Conflict detected (Attempt {attempts}/{retries}). Retrying in {delay}s...")
                        time.sleep(delay)
                        delay *= 2  # Double the wait time (exponential)
                    else:
                        raise e
            raise RuntimeError(f"Failed to resolve Conflict after {retries} retries.")
        return wrapper
    return decorator

# ========================================================
# 4. COPILOT STUDIO DIRECT LINE LOGIC
# ========================================================
def start_copilot_conversation():
    try:
        response = requests.get(COPILOT_ENDPOINT)
        if response.status_code != 200: return None
        
        token_data = response.json()
        dl_token = token_data.get("token")
        
        # Initialize conversation on Direct Line V3
        conv_response = requests.post(
            "https://botframework.com",
            headers={"Authorization": f"Bearer {dl_token}"}
        )
        
        if conv_response.status_code != 201: return None
            
        data = conv_response.json()
        return {
            "conversationId": data["conversationId"],
            "token": data["token"],
            "watermark": None  # Digital bookmark
        }
    except Exception as e:
        print(f"Error starting Copilot: {e}")
        return None

# ========================================================
# 5. MESSAGE HANDLER WITH WATERMARK (HISTORY FIX)
# ========================================================
@bot.message_handler(func=lambda message: True)
def handle_message(message):
    user_id = message.from_user.id
    user_text = message.text

    if user_id not in user_sessions or not user_sessions:
        user_sessions = start_copilot_conversation()

    session = user_sessions
    if not session:
        bot.reply_to(message, "Having trouble connecting to the system.")
        return

    conv_id = session["conversationId"]
    token = session["token"]
    last_watermark = session.get("watermark")

    # Send message to Copilot
    activity_url = f"https://botframework.com/{conv_id}/activities"
    payload = {
        "locale": "en-US", "type": "message",
        "from": {"id": str(user_id)}, "text": user_text
    }
    requests.post(activity_url, json=payload, headers={"Authorization": f"Bearer {token}"})

    # Wait for bot generation, then fetch ONLY NEW activities
    time.sleep(1.5)
    get_params = {}
    if last_watermark:
        get_params["watermark"] = last_watermark

    res = requests.get(activity_url, headers={"Authorization": f"Bearer {token}"}, params=get_params)
    
    if res.status_code == 200:
        data = res.json()
        
        # Advance the watermark to ensure we don't replay history
        new_watermark = data.get("watermark")
        if new_watermark:
            user_sessions["watermark"] = new_watermark

        activities = data.get("activities",)
        for activity in activities:
            # Filter out our own messages and only send Bot text
            if activity.get("from", {}).get("id") != str(user_id) and "text" in activity:
                bot.send_message(chat_id=message.chat.id, text=activity["text"])

# ========================================================
# 6. START POLLING WITH AUTO-RECOVERY
# ========================================================
@retry_with_backoff()
def start_bot():
    print("Clearing webhooks and starting bot polling...")
    bot.remove_webhook()  # Clear stuck webhooks before starting
    bot.infinity_polling(timeout=10, long_polling_timeout=5)

if __name__ == "__main__":
    start_bot()
