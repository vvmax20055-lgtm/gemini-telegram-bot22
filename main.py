import os
import telebot
import threading
import uvicorn
from fastapi import FastAPI
from dotenv import load_dotenv

load_dotenv()

# 1. Настройки
TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
bot = telebot.TeleBot(TOKEN)
app = FastAPI()

# 2. ТА САМАЯ ПРОВЕРКА ДЛЯ RAILWAY (Health Check)
# Без этого Railway будет постоянно убивать твой контейнер
@app.get("/")
async def health_check():
    return {"status": "working", "message": "I am alive!"}

# 3. Твой основной хендлер (упростил для теста)
@bot.message_handler(func=lambda m: True)
def echo_all(message):
    bot.reply_to(message, f"Я на связи! Ты написал: {message.text}")

# 4. Функция запуска бота
def run_bot():
    print("--- Бот запущен (polling) ---")
    bot.remove_webhook()
    bot.polling(none_stop=True)

# 5. Запуск всего вместе
if __name__ == "__main__":
    # Запускаем бота в отдельном потоке
    threading.Thread(target=run_bot, daemon=True).start()
    
    # Запускаем сервер FastAPI (он будет отвечать Railway на проверки)
    port = int(os.environ.get("PORT", 8080))
    print(f"--- Сервер запущен на порту {port} ---")
    uvicorn.run(app, host="0.0.0.0", port=port)
    
