import os
import re
import aiohttp
import asyncio
import telebot
import threading
import uvicorn
import google.generativeai as genai
from fastapi import FastAPI, Request
from dotenv import load_dotenv

load_dotenv()
genai.configure(api_key=os.getenv("GOOGLE_API_KEY")) # Убедись, что этот ключ есть в Railway Variables
model = genai.GenerativeModel('gemini-1.5-flash')

# --- НАСТРОЙКИ ---
TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
API_KEY = os.getenv('API_KEY')
# Связь внутри одного контейнера
BASE_API_URL = "http://127.0.0.1:8080" 

bot = telebot.TeleBot(TOKEN)
app = FastAPI()

# --- 1. HEALTH CHECK ДЛЯ RAILWAY ---
@app.get("/")
async def health_check():
    return {"status": "ok"}

# --- 2. ДВИЖОК (ЗДЕСЬ ТВОЯ ЛОГИКА GEMINI) ---
@app.post("/conversations/{user_id}")
async def handle_api_logic(user_id: str, request: Request):
    data = await request.json()
    query = data.get("query")
    
    try:
        # Отправляем запрос в настоящую нейросеть
        response = model.generate_content(query)
        return response.text
    except Exception as e:
        return f"Ошибка Gemini: {str(e)}"

# --- 3. ОБРАБОТКА МАРКДАУНА ---
def escape_markdown(text):
    text = text.replace('\\n', '\n')
    markdown_chars = r'[\*_\[\]()~`>#\+\-=|{}\.!]'
    return re.sub(markdown_chars, lambda m: '\\' + m.group(0), text)

# --- 4. СВЯЗЬ БОТА С ДВИЖКОМ ---
async def call_engine(user_id, text):
    headers = {'Content-Type': 'application/json', 'x-api-key': API_KEY}
    async with aiohttp.ClientSession() as session:
        async with session.post(f"{BASE_API_URL}/conversations/{user_id}", 
                                 json={"query": text}, headers=headers) as resp:
            if resp.status == 200:
                return await resp.text()
            return "Ошибка движка."

# --- 5. ХЕНДЛЕР БОТА ---
@bot.message_handler(content_types=['text', 'photo'])
def handle_message(message):
    user_id = message.from_user.id
    query = message.text or message.caption or "Опиши это фото"
    
    bot.send_chat_action(message.chat.id, 'typing')
    
    # Запускаем асинхронный вызов движка
    response_text = asyncio.run(call_engine(user_id, query))
    
    try:
        bot.send_message(message.chat.id, escape_markdown(response_text), parse_mode='MarkdownV2')
    except:
        bot.send_message(message.chat.id, response_text)

# --- 6. ЗАПУСК ВСЕГО ---
def start_bot():
    bot.remove_webhook()
    bot.polling(none_stop=True)

if __name__ == "__main__":
    # Поток бота
    threading.Thread(target=start_bot, daemon=True).start()
    # Основной сервер
    port = int(os.environ.get("PORT", 8080))
    uvicorn.run(app, host="0.0.0.0", port=port)
    
