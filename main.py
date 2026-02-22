import os
import re
import aiohttp
import asyncio
import telebot
import threading
import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI, Request # Добавили FastAPI

# Load environment variables
load_dotenv()

TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
# ВАЖНО: Для связи внутри одного контейнера используем localhost
BASE_API_URL = "http://127.0.0.1:8080" 
API_KEY = os.getenv('API_KEY')

bot = telebot.TeleBot(TOKEN)
app = FastAPI() # СОЗДАЕМ ДВИЖОК

# --- ЧАСТЬ 1: ДВИЖОК (API) ---
# Сюда нужно перенести логику обработки Gemini, которая была в старом движке
@app.post("/conversations/{user_id}")
async def handle_conversation(user_id: str, request: Request):
    data = await request.json()
    query = data.get("query")
    # Здесь должен быть ваш вызов нейросети Gemini
    # Пока сделаем простую заглушку для проверки:
    return f"Движок получил сообщение: {query}"

@app.delete("/delete/{user_id}")
async def delete_conversation(user_id: str):
    return {"status": "deleted"}

# --- ЧАСТЬ 2: ОБЛОЧКА (ТЕЛЕГРАМ БОТ) ---
# (Ваши функции escape_markdown и handle_api_request остаются без изменений)
def escape_markdown(text):
    text = text.replace('\\n', '\n')
    markdown_chars = r'[\*_\[\]()~`>#\+\-=|{}\.!]'
    return re.sub(markdown_chars, lambda m: '\\' + m.group(0), text)

async def handle_api_request(message, delete=False, image_url=None):
    user_id = str(message.from_user.id)
    headers = {'Content-Type': 'application/json', 'x-api-key': API_KEY}
    async with aiohttp.ClientSession() as session:
        if delete:
            async with session.delete(f"{BASE_API_URL}/delete/{user_id}", headers=headers) as response:
                yield "Conversation deleted." if response.status == 200 else "Error."
        else:
            query_text = message.caption if message.content_type == 'photo' else message.text
            data = {"query": query_text}
            # Стучимся в наш же FastAPI (app)
            async with session.post(f"{BASE_API_URL}/conversations/{user_id}", headers=headers, json=data) as response:
                if response.status == 200:
                    result = await response.text()
                    yield result
                else:
                    yield "Ошибка связи с движком."

@bot.message_handler(content_types=['text', 'photo'])
def handle_text(message):
    async def process_response():
        async for response in handle_api_request(message):
            bot.send_message(message.chat.id, escape_markdown(response), parse_mode='MarkdownV2')
    
    bot.send_chat_action(message.chat.id, 'typing')
    asyncio.run(process_response())

# --- ЧАСТЬ 3: ЗАПУСК ВСЕГО ВМЕСТЕ ---
if __name__ == '__main__':
    print("Запуск системы...")
    # 1. Запускаем бота в фоне
    bot_thread = threading.Thread(target=bot.polling, kwargs={"none_stop": True}, daemon=True)
    bot_thread.start()

    # 2. Запускаем сервер (Движок)
    port = int(os.environ.get("PORT", 8080))
    uvicorn.run(app, host="0.0.0.0", port=port)
    
