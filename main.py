import os
import re
import aiohttp
import asyncio
import telebot
import threading
import uvicorn
from fastapi import FastAPI, Request
from dotenv import load_dotenv

load_dotenv()

# Настройки
TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
API_KEY = os.getenv('API_KEY')
# Внутренняя связь
BASE_API_URL = "http://127.0.0.1:8080" 

bot = telebot.TeleBot(TOKEN)
app = FastAPI()

# --- 1. ДВИЖОК (API) ---
@app.post("/conversations/{user_id}")
async def handle_conversation(user_id: str, request: Request):
    data = await request.json()
    query = data.get("query", "")
    return f"Ответ: Я получил ваш запрос '{query}'"

# --- 2. ОБЛОЧКА (БОТ) ---
@bot.message_handler(func=lambda m: True)
def handle_text(message):
    import requests # используем requests, чтобы не конфликтовать с asyncio
    bot.send_chat_action(message.chat.id, 'typing')
    
    try:
        res = requests.post(
            f"{BASE_API_URL}/conversations/{message.from_user.id}",
            json={"query": message.text},
            headers={"x-api-key": API_KEY},
            timeout=10
        )
        bot.reply_to(message, res.text if res.status_code == 200 else "Ошибка API")
    except Exception as e:
        bot.reply_to(message, f"Ошибка связи: {e}")

# --- 3. ЗАПУСК ---
def start_bot():
    print("--- [ПОТОК БОТА ЗАПУЩЕН] ---")
    bot.remove_webhook()
    bot.polling(none_stop=True)

if __name__ == "__main__":
    # Сначала запускаем бота в фоне
    bot_thread = threading.Thread(target=start_bot, daemon=True)
    bot_thread.start()

    # Затем запускаем сервер (он заблокирует основной поток и не даст программе закрыться)
    print("--- [СЕРВЕР API ЗАПУСКАЕТСЯ] ---")
    port = int(os.environ.get("PORT", 8080))
    uvicorn.run(app, host="0.0.0.0", port=port)
    
