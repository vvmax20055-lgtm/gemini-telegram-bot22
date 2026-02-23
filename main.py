import os
import re
import asyncio
import logging

import google.generativeai as genai
from dotenv import load_dotenv
from fastapi import FastAPI, Request, HTTPException
from telebot.async_telebot import AsyncTeleBot

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

load_dotenv()

# --- Переменные окружения ---
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET")  # отдельный секрет
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-1.5-flash")

if not TOKEN:
    raise ValueError("TELEGRAM_BOT_TOKEN не задан")
if not GOOGLE_API_KEY:
    raise ValueError("GOOGLE_API_KEY не задан")
if not WEBHOOK_URL:
    raise ValueError("WEBHOOK_URL не задан")
if not WEBHOOK_SECRET:
    raise ValueError("WEBHOOK_SECRET не задан")

# --- Инициализация Gemini ---
genai.configure(api_key=GOOGLE_API_KEY)
model = genai.GenerativeModel(GEMINI_MODEL)

# --- FastAPI и бот ---
app = FastAPI()
bot = AsyncTeleBot(TOKEN)


# ---------------------------
# Health check
# ---------------------------
@app.get("/")
async def health():
    return {"status": "ok"}


# ---------------------------
# Экранирование MarkdownV2
# ---------------------------
def escape_markdown(text: str) -> str:
    if not text:
        return "Нет ответа от модели."
    text = text.replace("\\", "\\\\")
    markdown_chars = r'[_*\[\]()~`>#+\-=|{}.!]'
    return re.sub(markdown_chars, lambda m: "\\" + m.group(0), text)


# ---------------------------
# Вызов Gemini
# ---------------------------
async def generate_response(prompt: str) -> str:
    try:
        response = await asyncio.to_thread(model.generate_content, prompt)
        return response.text or "Нет ответа от модели."
    except Exception as e:
        logger.exception("Ошибка при обращении к Gemini")
        return f"Ошибка Gemini: {str(e)}"


# ---------------------------
# Команда /start
# ---------------------------
@bot.message_handler(commands=['start'])
async def handle_start(message):
    await bot.send_chat_action(message.chat.id, "typing")
    welcome_text = (
        "Привет! Я бот на базе Gemini.\n"
        "Просто отправь мне любой текст, и я постараюсь ответить."
    )
    await bot.send_message(message.chat.id, welcome_text)


# ---------------------------
# Обработка текста
# ---------------------------
@bot.message_handler(content_types=["text"])
async def handle_text(message):
    await bot.send_chat_action(message.chat.id, "typing")
    response_text = await generate_response(message.text)

    try:
        await bot.send_message(
            message.chat.id,
            escape_markdown(response_text),
            parse_mode="MarkdownV2"
        )
    except Exception as e:
        logger.warning(f"Ошибка Markdown: {e}")
        await bot.send_message(message.chat.id, response_text)


# ---------------------------
# Webhook endpoint
# ---------------------------
@app.post("/webhook")
async def telegram_webhook(request: Request):
    secret_token = request.headers.get("X-Telegram-Bot-Api-Secret-Token")
    if secret_token != WEBHOOK_SECRET:
        logger.warning("Неверный секретный токен")
        raise HTTPException(status_code=403, detail="Forbidden")

    data = await request.json()
    update = bot.types.Update.de_json(data)
    await bot.process_new_updates([update])
    return {"ok": True}


# ---------------------------
# Startup
# ---------------------------
@app.on_event("startup")
async def on_startup():
    logger.info("Удаление предыдущего вебхука...")
    await bot.remove_webhook()

    webhook_url = f"{WEBHOOK_URL.rstrip('/')}/webhook"
    logger.info(f"Установка вебхука: {webhook_url}")

    result = await bot.set_webhook(
        url=webhook_url,
        secret_token=WEBHOOK_SECRET
    )

    if result:
        logger.info("Вебхук установлен")
    else:
        raise RuntimeError("Ошибка установки вебхука")


# ---------------------------
# Локальный запуск
# ---------------------------
if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8080))
    uvicorn.run(app, host="0.0.0.0", port=port)
