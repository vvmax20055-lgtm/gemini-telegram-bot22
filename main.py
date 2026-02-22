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

# Инициализация
TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
API_KEY = os.getenv('API_KEY')
# Внутренний адрес для связи внутри Railway
BASE_API_URL = "http://127.0.0.1:8080" 

bot = telebot.TeleBot(TOKEN)
app = FastAPI()

# --- ДВИЖОК (API) ---
@app.post("/conversations/{user_id}")
async def handle_conversation(user_id: str, request: Request):
    data = await request.json()
    query = data.get("query")
    return f"Ответ от API: Вы написали '{query}'"

# --- ОБЛОЧКА (БОТ) ---
@bot.message_handler(func=lambda message: True)
def handle_text(message):
    # Используем библиотеку requests для простоты, 
    # чтобы не конфликтовать с потоками asyncio внутри telebot
    import requests
    
    bot.send_chat_action(message.chat.id, 'typing')
    
    payload = {"query": message.text}
    headers = {"x-api-key": API_KEY}
    
    try:
        response = requests.post(f"{BASE_API_URL}/conversations/{message.from_user.id}", 
                                 json=payload, headers=headers)
        if response.status_code == 200:
            bot.reply_to(message, response.text)
        else:
            bot.reply_to(message, "Движок ответил ошибкой.")
    except Exception as e:
        bot.reply_to(message, f"Не удалось связаться с движком: {e}")

# --- ЗАПУСК ---
def run_bot():
    print("Запускаю поток бота...")
    bot.remove_webhook() # Очистка перед стартом
    bot.polling(none_stop=True)

if __name__ == "__main__":
    # 1. Запуск бота в отдельном потоке
    t = threading.Thread(target=run_bot)
    t.daemon = True
    t.start()

    # 2. Запуск сервера (основной поток)
    print("Запускаю сервер API...")
    port = int(os.environ.get("PORT", 8080))
    uvicorn.run(app, host="0.0.0.0", port=port)
    
