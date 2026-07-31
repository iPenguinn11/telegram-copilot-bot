import os
import requests
import telebot

# Configurations
TELEGRAM_TOKEN = "8992190983:AAFiKT5cknT7dKynl8JdWsiPNGIX4ohe70k"
COPILOT_ENDPOINT = "https://default3476b776e9904f72b9506248983162.3d.environment.api.powerplatform.com/powervirtualagents/botsbyschema/crba2_golfRulesHumorMaster/directline/token?api-version=2022-03-01-preview"

bot = telebot.TeleBot(TELEGRAM_TOKEN)
user_sessions = {}

def start_copilot_conversation():
    try:
        response = requests.get(COPILOT_ENDPOINT)
        token_data = response.json()
        directline_token = token_data["token"]
        
        conv_response = requests.post(
            "https://botframework.com",
            headers={"Authorization": f"Bearer {directline_token}"}
        )
        return conv_response.json()
    except Exception as e:
        print(f"Error starting Copilot conversation: {e}")
        return None

@bot.message_handler(func=lambda message: True)
def handle_message(message):
    user_id = message.from_user.id
    user_text = message.text

    if user_id not in user_sessions or not user_sessions[user_id]:
        user_sessions[user_id] = start_copilot_conversation()

    session = user_sessions[user_id]
    if not session:
        bot.reply_to(message, "Sorry, I am having trouble connecting to the system right now.")
        return

    conv_id = session["conversationId"]
    token = session["token"]

    # Send user text to Copilot Studio
    send_url = f"https://botframework.com/{conv_id}/activities"
    payload = {
        "locale": "en-US",
        "type": "message",
        "from": {"id": str(user_id)},
        "text": user_text
    }
    requests.post(send_url, json=payload, headers={"Authorization": f"Bearer {token}"})

    # Get response back from Copilot Studio
    get_url = f"https://botframework.com/{conv_id}/activities"
    res = requests.get(get_url, headers={"Authorization": f"Bearer {token}"})
    activities = res.json().get("activities", [])

    # Forward the text response back to the user on Telegram
    for activity in activities:
        if activity.get("from", {}).get("id") != str(user_id) and "text" in activity:
            bot.send_message(chat_id=message.chat.id, text=activity["text"])

if __name__ == "__main__":
    print("Bot is running...")
    bot.infinity_polling()
