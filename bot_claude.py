import asyncio
import logging
import os

from dotenv import load_dotenv
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

load_dotenv()
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")

if not TELEGRAM_TOKEN:
    print("❌ Токен не найден!")
    exit(1)

logging.basicConfig(
    format="%(asctime)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

REPORTS_DIR = "reports"
os.makedirs(REPORTS_DIR, exist_ok=True)


async def generate_response(client_message: str) -> str:
    prompt = f"""Используй скилл response-generator.

Сообщение клиента: {client_message}

Сгенерируй ответ согласно инструкциям в скилле."""

    try:
        process = await asyncio.create_subprocess_exec(
            "claude", "--dangerously-skip-permissions", "-p", prompt,
            stdin=asyncio.subprocess.DEVNULL,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=os.getcwd(),
        )

        try:
            stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=120)
        except asyncio.TimeoutError:
            process.kill()
            return "❌ Превышено время ожидания ответа от Claude."

        if process.returncode == 0 and stdout.strip():
            return stdout.decode().strip()
        else:
            logger.error(f"Claude ошибка: {stderr.decode()}")
            return "Извините, не удалось сгенерировать ответ."

    except FileNotFoundError:
        return "❌ Ошибка: Claude Code не найден. Убедитесь, что он установлен и доступен в командной строке."


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Бот с Claude Skill\n\n"
        "Начни сообщение с ! — я сгенерирую ответ клиенту.\n"
        "Без ! — пишу как обычно, бот молчит.\n\n"
        "Пример: ! Дорого, у других дешевле\n\n"
        "Все ответы сохраняются в reports/log.md"
    )


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    client_message = update.message.text
    if not client_message.startswith("!"):
        return
    client_message = client_message[1:].strip()
    if not client_message:
        return
    placeholder = await update.message.reply_text("Думаю...")
    bot_response = await generate_response(client_message)
    await placeholder.edit_text(bot_response)


def main():
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    logger.info("Бот запущен с Claude Code!")
    logger.info(f"Папка скилла: {os.getcwd()}/.claude/skills/response-generator/")
    app.run_polling()


if __name__ == "__main__":
    main()
