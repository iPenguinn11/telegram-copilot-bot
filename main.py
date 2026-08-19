import os
import threading
import requests
import telebot
import time
from flask import Flask

# ========================================================
# 1. RENDER FREE TIER COMPATIBILITY (FLASK SERVER)
# ========================================================
app = Flask('')

@app.route('/')
def home():
    return "Bot is alive and running!"

def run_web_server():
    # Bind to Render's dynamic port to prevent scan timeouts
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

# Start web server in a background thread
threading.Thread(target=run_web_server, daemon=True).start()

# ========================================================
# 2. CONFIGURATIONS
# ========================================================
TELEGRAM_TOKEN = "8992190983:AAGdOir-jXPcW9LrhAuexkjwpe1xBsRCZf4"
COPILOT_ENDPOINT = "https://default3476b776e9904f72b9506248983162.3d.environment.api.powerplatform.com/powervirtualagents/botsbyschema/crba2_golfRulesHumorMaster/directline/token?api-version=2022-03-01-preview"

bot = telebot.TeleBot(TELEGRAM_TOKEN)
# Global session store to track convo IDs and Watermarks per user
user_sessions = {}

def start_copilot_conversation():
    try:
        # Step A: Fetch fresh Direct Line token
        response = requests.get(COPILOT_ENDPOINT)
        if response.status_code != 200:
            print(f"Token Error: {response.status_code}")
            return None
        
        token_data = response.json()
        dl_token = token_data.get("token")
        
        # Step B: Initialize conversation on Direct Line V3
        conv_response = requests.post(
            "https://directline.botframework.com/v3/directline/conversations",
            headers={"Authorization": f"Bearer {dl_token}"}
        )
        
        if conv_response.status_code != 201:
            print(f"Convo Error: {conv_response.status_code}")
            return None
            
        data = conv_response.json()
        return {
            "conversationId": data["conversationId"],
            "token": data["token"],
            "watermark": None  # Initialize the 'bookmark'
        }
    except Exception as e:
        print(f"Exception during startup: {e}")
        return None

# ========================================================
# 3. MESSAGE HANDLER WITH WATERMARK & FILTERING
# ========================================================
@bot.message_handler(func=lambda message: True)
def handle_message(message):
    user_id = message.from_user.id
    user_text = message.text

    # Re-establish session if missing
    if user_id not in user_sessions or not user_sessions:
        user_sessions = start_copilot_conversation()

    session = user_sessions
    if not session:
        bot.reply_to(message, "Sorry, I am having trouble connecting to the system right now.")
        return

    conv_id = session["conversationId"]
    token = session["token"]
    last_watermark = session.get("watermark")

    # A. Send user message to Copilot
    activity_url = f"https://botframework.com{conv_id}/activities"
    payload = {
        "locale": "en-US",
        "type": "message",
        "from": {"id": str(user_id)},
        "text": user_text
    }
    requests.post(activity_url, json=payload, headers={"Authorization": f"Bearer {token}"})

    # B. Retrieve ONLY new responses using the Watermark
    # Wait ~1s for Copilot to generate its reply
    time.sleep(1.2)
    
    get_params = {}
    if last_watermark:
        get_params["watermark"] = last_watermark

    res = requests.get(activity_url, headers={"Authorization": f"Bearer {token}"}, params=get_params)
    
    if res.status_code == 200:
        data = res.json()
        
        # C. Update the bookmark for next time
        new_watermark = data.get("watermark")
        if new_watermark:
            user_sessions["watermark"] = new_watermark

        activities = data.get("activities",)
        
        # D. Process activities, filtering out the user's own text
        for activity in activities:
            # Only send if from the bot and contains text
            if activity.get("from", {}).get("id") != str(user_id) and "text" in activity:
                bot.send_message(chat_id=message.chat.id, text=activity["text"])
    else:
        print(f"Error fetching activities: {res.status_code}")

if __name__ == "__main__":
    print("Bot is live. Waiting for messages...")
    bot.infinity_polling()
