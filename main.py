import os
import re
import asyncio
import google.generativeai as genai

from fastapi import FastAPI, Request, HTTPException
from dotenv import load_dotenv
from telebot.async_telebot import AsyncTeleBot

load_dotenv()

# --- ENV ---
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")  # https://your-app.up.railway.app

if not TOKEN:
    raise ValueError("TELEGRAM_BOT_TOKEN не задан")

if not GOOGLE_API_KEY:
    raise ValueError("GOOGLE_API_KEY не задан")

# --- Gemini ---
genai.configure(api_key=GOOGLE_API_KEY)
model = genai.GenerativeModel("gemini-1.5-flash")

# --- App ---
app = FastAPI()
bot = AsyncTeleBot(TOKEN)


# ---------------------------
# HEALTH CHECK (Railway)
# ---------------------------
@app.get("/")
async def health():
    return {"status": "ok"}


# ---------------------------
# Markdown escape
# ---------------------------
def escape_markdown(text: str) -> str:
    if not text:
        return "Нет ответа от модели."
    text = text.replace("\\", "\\\\")
    markdown_chars = r'[\*_()~`>#\+\-=|{}\.!]'
    return re.sub(markdown_chars, lambda m: "\\" + m.group(0), text)


# ---------------------------
# Gemini logic
# ---------------------------
async def generate_response(prompt: str) -> str:
    try:
        response = model.generate_content(prompt)
        return response.text or "Нет ответа от модели."
    except Exception as e:
        return f"Ошибка Gemini: {str(e)}"


# ---------------------------
# Telegram webhook endpoint
# ---------------------------
@app.post(f"/webhook/{TOKEN}")
async def telegram_webhook(request: Request):
    data = await request.json()
    update = bot.types.Update.de_json(data)

    await bot.process_new_updates([update])
    return {"ok": True}


# ---------------------------
# Bot handler
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
    except:
        await bot.send_message(message.chat.id, response_text)


# ---------------------------
# Startup: register webhook
# ---------------------------
@app.on_event("startup")
async def on_start
