import os
import threading
import requests
import telebot
from flask import Flask

# ========================================================
# 1. RENDER COMPATIBILITY
# ========================================================
app = Flask('')

@app.route('/')
def home():
    return "Bot is alive and running!"

def run_web_server():
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

threading.Thread(target=run_web_server, daemon=True).start()

# ========================================================
# 2. CONFIGURATIONS
# ========================================================
TELEGRAM_TOKEN = "8992190983:AAFDBhOrxsmfYMkDI3R5S5v6X3B8F2YF3Us"
COPILOT_ENDPOINT = "https://default3476b776e9904f72b9506248983162.3d.environment.api.powerplatform.com/powervirtualagents/botsbyschema/crba2_golfRulesHumorMaster/directline/token?api-version=2022-03-01-preview"

bot = telebot.TeleBot(TELEGRAM_TOKEN)
user_sessions = {}

def start_copilot_conversation():
    try:
        # Step A: Get a fresh Direct Line Token
        print("Attempting to fetch fresh Direct Line Token from Power Platform...")
        response = requests.get(COPILOT_ENDPOINT)
        if response.status_code != 200:
            print(f"Failed to fetch token. HTTP Status Code: {response.status_code}. Response: {response.text}")
            return None
            
        token_data = response.json()
        directline_token = token_data.get("token")
        
        # Step B: Open the container conversation channel
        print("Opening conversation channel container on Direct Line...")
        conv_response = requests.post(
            "https://directline.botframework.com/v3/directline/conversations",
            headers={"Authorization": f"Bearer {directline_token}"}
        )
        
        if conv_response.status_code not in [200, 201]:
            print(f"Failed to start conversation. HTTP Status: {conv_response.status_code}. Details: {conv_response.text}")
            return None
            
        return conv_response.json()
    except Exception as e:
        print(f"Critical exception raised during Copilot init: {e}")
        return None

# ========================================================
# 3. MESSAGE HANDLING AND SHUTTLE ROUTING
# ========================================================
@bot.message_handler(func=lambda message: True)
def handle_message(message):
    user_id = message.from_user.id
    user_text = message.text

    # Re-verify or establish a fresh connection session
    if user_id not in user_sessions or not user_sessions[user_id]:
        user_sessions[user_id] = start_copilot_conversation()

    session = user_sessions[user_id]
    if not session:
        bot.reply_to(message, "Sorry, I am having trouble connecting to the system right now.")
        return

    conv_id = session.get("conversationId")
    token = session.get("token")

    # Destination URL structures
    activity_url = f"https://directline.botframework.com/v3/directline/conversations/{conv_id}/activities"
    
    # Send user data up
    payload = {
        "locale": "en-US",
        "type": "message",
        "from": {"id": str(user_id)},
        "text": user_text
    }
    requests.post(activity_url, json=payload, headers={"Authorization": f"Bearer {token}"})

    # Pull response payload back down
    res = requests.get(activity_url, headers={"Authorization": f"Bearer {token}"})
    activities = res.json().get("activities", [])

    # Process and route back to Telegram client screen
    bot_replied = False
    for activity in activities:
        if activity.get("from", {}).get("id") != str(user_id) and "text" in activity:
            bot.send_message(chat_id=message.chat.id, text=activity["text"])
            bot_replied = True
            
    # Reset tracking if session failed mid-way through payload delivery
    if not bot_replied:
        user_sessions[user_id] = None

if __name__ == "__main__":
    print("Application successfully built. Standing by for loops...")
    bot.infinity_polling()
# Store the watermark in your session data
user_sessions = {
    "conversationId": conv_id,
    "token": token,
    "watermark": None  # Initialize watermark
}

# When getting activities, include the watermark if it exists
watermark = session.get("watermark")
get_url = f"https://directline.botframework.com/v3/directline/conversations/{conv_id}/activities"
if watermark:
    get_url += f"?watermark={watermark}"

res = requests.get(get_url, headers={"Authorization": f"Bearer {token}"})
data = res.json()

# Save the new watermark for the next turn
user_sessions["watermark"] = data.get("watermark")


