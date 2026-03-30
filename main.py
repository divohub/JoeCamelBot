import asyncio
import logging
import os
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder
from dotenv import load_dotenv
from apscheduler.schedulers.asyncio import AsyncioScheduler
from apscheduler.triggers.cron import CronTrigger

import database
from ai_logic import AIScorer

# Load configuration
load_dotenv()
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
GEMINI_KEY = os.getenv("GEMINI_API_KEY")
PENALTY_HOUR = int(os.getenv("PENALTY_HOUR", 0))
PENALTY_MINUTE = int(os.getenv("PENALTY_MINUTE", 0))
MIN_VOTES = int(os.getenv("MIN_VOTES", 2))

# Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialization
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()
scorer = AIScorer(GEMINI_KEY)
scheduler = AsyncioScheduler()

# Helper to format message with user mention
def get_user_mention(user):
    if user['username']:
        return f"@{user['username']}"
    return user['full_name']

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    await database.update_user(message.from_user.id, message.from_user.username, message.from_user.full_name)
    await message.answer("Здарова, шнягоходы! Я Шняга-Бот. Пиши мне о своих достижениях (например: 'Шняга: прочитал книгу' или 'Бот, сходил в качалку'), а я решу, сколько баллов ты стоишь. \n\n"
                         "**Правила:**\n"
                         "✅ Мини — 5 баллов\n"
                         "✅ Средняя — 10 баллов\n"
                         "✅ Большая — 15 баллов\n"
                         "✅ Экстра — 20 баллов\n"
                         "🔥 Мега — 150 баллов (нужно 2 голоса пацанов)\n"
                         "⚠️ Каждую полночь: -10 баллов всем.\n\n"
                         "Команды:\n"
                         "/top — Таблица лидеров\n"
                         "/stats — Твои баллы", parse_mode="Markdown")

@dp.message(Command("setchat"))
async def cmd_set_chat(message: types.Message):
    await database.set_setting("main_chat_id", message.chat.id)
    await message.answer(f"✅ Чат установлен как основной для шняги (ID: {message.chat.id}). Сюда буду кидать штрафы.")

# Daily Penalty Task
async def daily_penalty():
    await database.apply_daily_penalty()
    chat_id = await database.get_setting("main_chat_id") or os.getenv("ADMIN_CHAT_ID")
    if chat_id:
        try:
            await bot.send_message(chat_id, "💀 **ПОЛНОЧЬ. ВРЕМЯ РАСПЛАТЫ.**\n\nС каждого списано по **10 баллов** за простой. Если ты сегодня не делал шнягу — ты официальный чушпан.\n\nПиши /top, чтобы увидеть, кто остался гигачадом.", parse_mode="Markdown")
        except Exception as e:
            logger.error(f"Failed to send penalty message: {e}")
    logger.info("Daily penalty applied.")


async def main():
    await database.init_db()
    
    # Setup scheduler
    scheduler.add_job(daily_penalty, CronTrigger(hour=PENALTY_HOUR, minute=PENALTY_MINUTE))
    scheduler.start()
    
    # Start polling
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
