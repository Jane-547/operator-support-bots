"""Telegram-бот для ответов на вопросы операторов по регламенту."""

import asyncio
import logging
import os
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

from site_agent import get_context_for_query, load_index

load_dotenv(Path(__file__).parent.parent.parent / ".env")

ROOT = Path(__file__).parent.parent.parent
REPORTS_DIR = ROOT / "reports"
REPORTS_DIR.mkdir(exist_ok=True)

logging.basicConfig(
    format="%(asctime)s %(levelname)s %(message)s",
    level=logging.INFO,
    handlers=[logging.StreamHandler()],
)
logging.getLogger().handlers[0].stream.reconfigure(encoding="utf-8", errors="replace")
logger = logging.getLogger(__name__)

TELEGRAM_TOKEN = os.environ["REGULATION_BOT_TOKEN"]

SYSTEM_PROMPT = (
    "Ты — помощник для операторов онлайн-школы скорочтения Матриус. "
    "Отвечаешь на вопросы по регламенту работы строго по базе знаний.\n\n"
    "Правила:\n"
    "- Отвечай только по контексту. Не придумывай.\n"
    "- Давай конкретный, практический ответ: шаги, цифры, формулировки.\n"
    "- Тон: мягкий, как опытный коллега. Без давления.\n"
    "- Если ответа в базе нет: «Не нашёл ответа на этот вопрос. Обратись к руководителю.»\n"
    "- Не начинай с «Конечно!», «Отлично!», «Хорошо!».\n"
    "- Отвечай на русском языке.\n"
    "- Не упоминай ссылки и URL в своём ответе — они будут добавлены отдельно.\n"
    "- Не сохраняй файлы и не упоминай отчёты, логи или любые файловые операции."
)


async def _ask_llm(question: str, context: str) -> str:
    prompt = (
        f"{SYSTEM_PROMPT}\n\n"
        f"База знаний:\n\n{context}\n\n"
        f"---\nВопрос оператора: {question}"
    )
    process = await asyncio.create_subprocess_exec(
        "claude", "--dangerously-skip-permissions", "--model", "claude-haiku-4-5-20251001", "-p", prompt,
        stdin=asyncio.subprocess.DEVNULL,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        cwd=str(Path(__file__).parent.parent.parent),
    )
    try:
        stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=120)
    except asyncio.TimeoutError:
        process.kill()
        raise RuntimeError("Превышено время ожидания ответа от Claude.")
    if process.returncode != 0 or not stdout.strip():
        raise RuntimeError(stderr.decode(errors="replace").strip() or "Claude вернул пустой ответ.")
    lines = stdout.decode(errors="replace").splitlines()
    low_skip = {"отчёт", "report", "сохранён", "сохранен", "добавлен", "записан"}
    lines = [l for l in lines if not any(w in l.lower() for w in low_skip)]
    return "\n".join(lines).strip()


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Привет! Начни сообщение с ! — отвечу по регламенту и дам ссылку на нужную страницу.\n\n"
        "Пример: ! что делать при недозвоне"
    )


def _save_log(question: str, answer: str) -> None:
    log_path = REPORTS_DIR / "regulation-bot-log.md"
    ts = datetime.now().strftime("%Y-%m-%d %H:%M")
    entry = f"\n---\n**{ts}**\n\n**Вопрос:** {question}\n\n**Ответ:** {answer}\n"
    with open(log_path, "a", encoding="utf-8") as f:
        f.write(entry)


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    question = update.message.text
    if not question or not question.startswith("!"):
        return
    question = question[1:].strip()
    if not question:
        return

    placeholder = await update.message.reply_text("Думаю...")

    try:
        kb_context, top_pages = await asyncio.to_thread(get_context_for_query, question)
    except Exception as e:
        logger.exception("Ошибка построения контекста: %s", e)
        await placeholder.edit_text(f"Ошибка при поиске по базе знаний: {e}")
        return

    try:
        answer = await _ask_llm(question, kb_context)
    except Exception as e:
        logger.exception("Ошибка LLM: %s", e)
        await placeholder.edit_text(f"Ошибка при обращении к LLM: {e}")
        return

    if top_pages:
        full_answer = f"{answer}\n\n📎 Подробнее: {top_pages[0]['url']}"
    else:
        full_answer = answer

    await placeholder.edit_text(full_answer)
    _save_log(question, full_answer)


def main():
    load_index()  # строим индекс при старте

    app = Application.builder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    logger.info("Бот регламента запущен (источник: локальный сайт)")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
