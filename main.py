import os
import threading
import requests
import telebot
from flask import Flask

# ========================================================
# 1. RENDER FREE TIER COMPATIBILITY (FLASK BACKGROUND SERVER)
# ========================================================
app = Flask('')

@app.route('/')
def home():
    return "Bot is alive and running 24/7!"

def run_web_server():
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

threading.Thread(target=run_web_server, daemon=True).start()

# ========================================================
# 2. CONFIGURATIONS & INITIALIZATION
# ========================================================
TELEGRAM_TOKEN = "8992190983:AAFiKT5cknT7dKynl8JdWsiPNGIX4ohe70k"
COPILOT_ENDPOINT = "https://powerplatform.com"

bot = telebot.TeleBot(TELEGRAM_TOKEN)
user_sessions = {}

def start_copilot_conversation():
    try:
        # Step A: Fetch the Direct Line token from Power Platform
        response = requests.get(COPILOT_ENDPOINT)
        token_data = response.json()
        directline_token = token_data["token"]
        
        # Step B: FIX - Connect to the actual Direct Line Conversation Endpoint
        conv_response = requests.post(
            "https://directline.botframework.com/v3/directline/conversations",
            headers={"Authorization": f"Bearer {directline_token}"}
        )
        return conv_response.json()
    except Exception as e:
        print(f"Error starting Copilot conversation: {e}")
        return None

# ========================================================
# 3. MESSAGE HANDLERS WITH ROUTING FIXES
# ========================================================
@bot.message_handler(func=lambda message: True)
def handle_message(message):
    user_id = message.from_user.id
    user_text = message.text

    # Start conversation tracking if it's a new user session
    if user_id not in user_sessions or not user_sessions[user_id]:
        user_sessions[user_id] = start_copilot_conversation()

    session = user_sessions[user_id]
    if not session:
        bot.reply_to(message, "Sorry, I am having trouble connecting to the system right now.")
        return

    conv_id = session["conversationId"]
    token = session["token"]

    # FIX: Send user text directly to the specific conversation endpoint
    send_url = f"https://botframework.com{conv_id}/activities"
    payload = {
        "locale": "en-US",
        "type": "message",
        "from": {"id": str(user_id)},
        "text": user_text
    }
    requests.post(send_url, json=payload, headers={"Authorization": f"Bearer {token}"})

    # FIX: Retrieve response back from the specific conversation activities endpoint
    get_url = f"https://botframework.com{conv_id}/activities"
    res = requests.get(get_url, headers={"Authorization": f"Bearer {token}"})
    activities = res.json().get("activities", [])

    # Forward the responses back to the user on Telegram
    for activity in activities:
        # Check that the message is coming from the bot, not echoing the user's own text
        if activity.get("from", {}).get("id") != str(user_id) and "text" in activity:
            bot.send_message(chat_id=message.chat.id, text=activity["text"])

if __name__ == "__main__":
    print("Web server running. Bot is listening for Telegram events...")
    bot.infinity_polling()

