import os
import re
import asyncio
import logging
from typing import Optional

import google.generativeai as genai
from dotenv import load_dotenv
from fastapi import FastAPI, Request, HTTPException
from telebot.async_telebot import AsyncTeleBot

# Настройка логирования
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

load_dotenv()

# --- Переменные окружения ---
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")          # например, https://your-app.up.railway.app
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-1.5-flash")  # модель по умолчанию

if not TOKEN:
    raise ValueError("TELEGRAM_BOT_TOKEN не задан")
if not GOOGLE_API_KEY:
    raise ValueError("GOOGLE_API_KEY не задан")
if not WEBHOOK_URL:
    raise ValueError("WEBHOOK_URL не задан")

# --- Инициализация Gemini ---
genai.configure(api_key=GOOGLE_API_KEY)
model = genai.GenerativeModel(GEMINI_MODEL)

# --- FastAPI и бот ---
app = FastAPI()
bot = AsyncTeleBot(TOKEN)


# ---------------------------
# Health check для Railway
# ---------------------------
@app.get("/")
async def health():
    return {"status": "ok"}


# ---------------------------
# Экранирование MarkdownV2
# ---------------------------
def escape_markdown(text: str) -> str:
    """Экранирует специальные символы MarkdownV2."""
    if not text:
        return "Нет ответа от модели."
    # Сначала экранируем обратную косую черту
    text = text.replace("\\", "\\\\")
    # Затем все спецсимволы MarkdownV2
    markdown_chars = r'[_*[\]()~`>#+\-=|{}.!]'
    return re.sub(markdown_chars, lambda m: "\\" + m.group(0), text)


# ---------------------------
# Асинхронный вызов Gemini
# ---------------------------
async def generate_response(prompt: str) -> str:
    """Отправляет запрос в Gemini и возвращает текст ответа."""
    try:
        # Запускаем синхронный вызов в отдельном потоке, чтобы не блокировать event loop
        response = await asyncio.to_thread(model.generate_content, prompt)
        return response.text or "Нет ответа от модели."
    except Exception as e:
        logger.exception("Ошибка при обращении к Gemini")
        return f"Ошибка Gemini: {str(e)}"


# ---------------------------
# Обработчик команд и текста
# ---------------------------
@bot.message_handler(commands=['start'])
async def handle_start(message):
    """Приветственное сообщение."""
    await bot.send_chat_action(message.chat.id, "typing")
    welcome_text = (
        "Привет! Я бот на базе Gemini.\n"
        "Просто отправь мне любой текст, и я постараюсь ответить."
    )
    await bot.send_message(message.chat.id, welcome_text)


@bot.message_handler(content_types=["text"])
async def handle_text(message):
    """Обработка текстовых сообщений."""
    await bot.send_chat_action(message.chat.id, "typing")
    response_text = await generate_response(message.text)

    try:
        # Пытаемся отправить с MarkdownV2
        await bot.send_message(
            message.chat.id,
            escape_markdown(response_text),
            parse_mode="MarkdownV2"
        )
    except Exception as e:
        # Если Markdown вызвал ошибку, отправляем без форматирования
        logger.warning(f"Ошибка отправки с Markdown: {e}. Отправляем без форматирования.")
        await bot.send_message(message.chat.id, response_text)


# ---------------------------
# Эндпоинт для вебхука Telegram
# ---------------------------
@app.post(f"/webhook/{TOKEN}")
async def telegram_webhook(request: Request):
    """
    Принимает обновления от Telegram.
    Проверяет секретный токен в заголовке для безопасности.
    """
    # Проверка секретного токена (должен совпадать с тем, что мы установили при регистрации вебхука)
    secret_token = request.headers.get("X-Telegram-Bot-Api-Secret-Token")
    if secret_token != TOKEN:
        logger.warning("Попытка доступа с неверным секретным токеном")
        raise HTTPException(status_code=403, detail="Forbidden")

    data = await request.json()
    update = bot.types.Update.de_json(data)
    await bot.process_new_updates([update])
    return {"ok": True}


# ---------------------------
# Startup: регистрация вебхука
# ---------------------------
@app.on_event("startup")
async def on_startup():
    """При запуске приложения удаляем старый вебхук и устанавливаем новый."""
    logger.info("Удаление предыдущего вебхука...")
    await bot.remove_webhook()

    webhook_url = f"{WEBHOOK_URL}/webhook/{TOKEN}"
    logger.info(f"Установка вебхука на {webhook_url}")

    # Устанавливаем вебхук с секретным токеном
    result = await bot.set_webhook(
        url=webhook_url,
        secret_token=TOKEN  # используем сам токен как секрет (можно вынести отдельно)
    )

    if result:
        logger.info("Вебхук успешно установлен")
    else:
        logger.error("Не удалось установить вебхук")
        # Можно добавить дополнительную обработку, например, завершение процесса
        raise RuntimeError("Ошибка установки вебхука")


# ---------------------------
# Точка входа для локального запуска
# ---------------------------
if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8080))
    uvicorn.run(app, host="0.0.0.0", port=port)
