import os
import threading
import requests
import telebot
import time
from flask import Flask

# ========================================================
# 1. RENDER COMPATIBILITY (FLASK BACKGROUND SERVER)
# ========================================================
app = Flask('')

@app.route('/')
def home():
    return "Bot is alive and running!"

def run_web_server():
    # Render requires binding to a port to stay 'Live'
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

threading.Thread(target=run_web_server, daemon=True).start()

# ========================================================
# 2. CONFIGURATIONS
# ========================================================
# It is recommended to use environment variables for security
TELEGRAM_TOKEN = "8992190983:AAFDBhOrxsmfYMkDI3R5S5v6X3B8F2YF3Us"
COPILOT_ENDPOINT = "https://default3476b776e9904f72b9506248983162.3d.environment.api.powerplatform.com/powervirtualagents/botsbyschema/crba2_golfRulesHumorMaster/directline/token?api-version=2022-03-01-preview"

bot = telebot.TeleBot(TELEGRAM_TOKEN)

# Session store to track conversation ID, token, and WATERMARK per user
user_sessions = {}

def start_copilot_conversation():
    try:
        # Step A: Get a fresh Direct Line Token
        response = requests.get(COPILOT_ENDPOINT)
        if response.status_code != 200:
            return None
        
        token_data = response.json()
        directline_token = token_data.get("token")
        
        # Step B: Open the conversation channel
        conv_response = requests.post(
            "https://directline.botframework.com/v3/directline/conversations",
            headers={"Authorization": f"Bearer {directline_token}"}
        )
        
        if conv_response.status_code not in:
            return None
            
        data = conv_response.json()
        return {
            "conversationId": data["conversationId"],
            "token": data["token"],
            "watermark": None  # Initialize the watermark
        }
    except Exception as e:
        print(f"Error starting Copilot conversation: {e}")
        return None

# ========================================================
# 3. MESSAGE HANDLER WITH WATERMARK LOGIC
# ========================================================
@bot.message_handler(func=lambda message: True)
def handle_message(message):
    user_id = message.from_user.id
    user_text = message.text

    # Establish or retrieve session
    if user_id not in user_sessions or not user_sessions:
        user_sessions = start_copilot_conversation()

    session = user_sessions
    if not session:
        bot.reply_to(message, "Sorry, I am having trouble connecting to the system right now.")
        return

    conv_id = session["conversationId"]
    token = session["token"]
    current_watermark = session.get("watermark")

    # A. Send user text to Copilot
    send_url = f"https://directline.botframework.com/v3/directline/conversations/{conv_id}/activities"
    payload = {
        "locale": "en-US",
        "type": "message",
        "from": {"id": str(user_id)},
        "text": user_text
    }
    requests.post(send_url, json=payload, headers={"Authorization": f"Bearer {token}"})

    # B. Retrieve ONLY new responses using the Watermark
    # We add a slight delay to allow Copilot to generate its reply
    time.sleep(1.5)
    
    get_url = f"https://directline.botframework.com/v3/directline/conversations/{conv_id}/activities"
    if current_watermark:
        get_url += f"?watermark={current_watermark}"

    res = requests.get(get_url, headers={"Authorization": f"Bearer {token}"})
    if res.status_code == 200:
        data = res.json()
        
        # C. Update the watermark for this user so we don't see these messages again
        new_watermark = data.get("watermark")
        if new_watermark:
            user_sessions["watermark"] = new_watermark

        activities = data.get("activities",)
        
        # D. Forward only the bot's new text replies back to Telegram
        for activity in activities:
            # Skip messages from the user themselves or empty messages
            if activity.get("from", {}).get("id") != str(user_id) and "text" in activity:
                bot.send_message(chat_id=message.chat.id, text=activity["text"])
    else:
        print(f"Error fetching activities: {res.status_code}")

if __name__ == "__main__":
    print("Bot is starting up...")
    bot.infinity_polling()


