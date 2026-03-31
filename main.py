import json
import asyncio
import logging
import os
import random
import re
from datetime import datetime, timedelta
from aiogram import Bot, Dispatcher, types, F, html
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder
from dotenv import load_dotenv
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

import database
from ai_logic import AIScorer

# Load configuration
load_dotenv()
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
GEMINI_KEY = os.getenv("GEMINI_API_KEY")
PENALTY_HOUR = int(os.getenv("PENALTY_HOUR", 0))
PENALTY_MINUTE = int(os.getenv("PENALTY_MINUTE", 0))
MIN_VOTES = int(os.getenv("MIN_VOTES", 2))
# Probability to react even if AI said ignore (rare dialogue spice) - not used if we trust AI ignore
# CHANCE_REACT removed in favor of AI-driven intervention

# Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialization
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()
scorer = AIScorer(GEMINI_KEY)
scheduler = AsyncIOScheduler()
bot_info = None

# In-memory history cache: {chat_id: [messages]}
# Each message: {"name": str, "text": str, "timestamp": datetime}
CHAT_HISTORY = {}
MAX_HISTORY = 15

# Helper to format message with user mention
def get_user_mention(user):
    username = user['username'] if 'username' in user.keys() else None
    if username:
        return f"@{html.quote(username)}"
    full_name = user['full_name'] if 'full_name' in user.keys() else 'Неизвестный'
    return html.quote(full_name)

# Filter to check if the bot is mentioned or replied to
async def is_direct_to_bot(message: types.Message):
    global bot_info
    if not bot_info:
        bot_info = await bot.get_me()
        
    if message.chat.type == "private":
        return True
    
    if not message.text:
        return False
        
    if message.reply_to_message and message.reply_to_message.from_user.id == bot.id:
        return True
        
    if f"@{bot_info.username}" in message.text:
        return True
        
    lower_text = message.text.lower()
    if re.search(r'\b(бот|бодя|джо|camel|верблюд|шняга)\b', lower_text):
        return True
        
    return False

@dp.message(F.content_type == types.ContentType.NEW_CHAT_MEMBERS)
async def on_user_joined(message: types.Message):
    for user in message.new_chat_members:
        if user.id == bot.id:
            await message.answer("Приветствую, утонченные ценители силы и базы. 🤙\n\n"
                                 "Я — Шняга-Бот. Я здесь, чтобы отличать истинную силу от пустой блажи и наставлять вас на путь базы.\n"
                                 "Живите достойно, делайте рогалики, и я это замечу.\n\n"
                                 "Для активации полночных штрафов пропишите /setchat.")

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    await database.update_user(message.from_user.id, message.from_user.username, message.from_user.full_name)
    await message.answer("Приветствую. Я Шняга-Бот, арбитр этого чата. \n\n"
                         "Моя миссия — следить за вашим духом и телом. За истинную СИЛУ и БАЗУ — поощряю. За АНТИ и БЛАЖЬ — караю баллом и словом. \n\n"
                         "Команды:\n"
                         "/help — Узнать все возможности\n"
                         "/top — Список достойных\n"
                         "/stats — Состояние твоего духа\n"
                         "/setchat — Привязать штрафы к этому чату", parse_mode="Markdown")

@dp.message(Command("help"))
async def cmd_help(message: types.Message):
    await message.answer("Я — Шняга-Бот, арбитр этого чата. Мои законы:\n\n"
                         "💎 Мини (5), Средняя (10), Большая (15), Экстра (20), Мега (150)\n"
                         "💀 Анти/Блажь — караются\n\n"
                         "Команды:\n"
                         "/top — Список лучших\n"
                         "/stats — Твой профиль и последние деяния\n"
                         "/setchat — Настройка чата\n\n"
                         "Спрашивай с меня, если не согласен с вердиктом!", parse_mode="Markdown")

@dp.message(Command("top"))
async def cmd_top(message: types.Message):
    top_users = await database.get_top_users()
    if not top_users:
        await message.answer("Список достойных пуст. Где ваша воля?")
        return
    text = "🏆 **СПИСОК ДОСТОЙНЫХ** 🏆\n\n"
    for i, user in enumerate(top_users, 1):
        medal = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else f"{i}."
        text += f"{medal} {get_user_mention(user)} — **{user['score']}** баллов силы\n"
    await message.answer(text, parse_mode="Markdown")

@dp.message(Command("stats"))
async def cmd_stats(message: types.Message):
    user = await database.get_user(message.from_user.id)
    if not user:
        await message.answer("Твои следы еще не впечатаны в нашу базу. Напиши /start")
        return
    
    activities = await database.get_user_activities(message.from_user.id, limit=3)
    
    msg = f"📊 **Твоя база:**\nБаланс силы: **{user['score']}**.\n\n"
    if activities:
        msg += "Последние деяния:\n"
        for act in activities:
            sign = "+" if act['points'] >= 0 else ""
            comment_snippet = act['description'][:20] + "..." if len(act['description']) > 20 else act['description']
            msg += f"• {act['category'].capitalize()}: {sign}{act['points']} — {comment_snippet}\n"
    
    await message.answer(msg, parse_mode="Markdown")

@dp.message(Command("setchat"))
async def cmd_set_chat(message: types.Message):
    await database.set_setting("main_chat_id", message.chat.id)
    await message.answer(f"✅ Чат признан ареной силы (ID: {message.chat.id}). Сюда будут приходить отчеты.")

# Main logic: Handle all messages
@dp.message(F.text)
async def handle_all_messages(message: types.Message):
    if message.text.startswith("/"):
        return

    chat_id = message.chat.id
    user_id = message.from_user.id
    username = message.from_user.username
    full_name = message.from_user.full_name
    
    await database.update_user(user_id, username, full_name)
    
    # Maintain chat history
    if chat_id not in CHAT_HISTORY:
        CHAT_HISTORY[chat_id] = []
    
    history = CHAT_HISTORY[chat_id]
    history.append({"id": user_id, "name": full_name, "text": message.text, "timestamp": datetime.now()})
    if len(history) > MAX_HISTORY:
        history.pop(0)

    is_direct = await is_direct_to_bot(message)
    
    user_memory = await database.get_user_memory(user_id)
    
    user = await database.get_user(user_id)
    user_stats_str = f"Счет: {user['score']}" if user else ""
    activities = await database.get_user_activities(user_id, limit=3)
    if activities:
        user_stats_str += ", последние дела: " + ", ".join([a['description'][:15] for a in activities])
    
    # Proactive AI check for EVERY message (Lite model makes it cheap)
    ai_result = await scorer.analyze_message(
        message.text, 
        full_name, 
        user_memory=user_memory,
        context_history=history[:-1], 
        is_direct=is_direct,
        user_stats=user_stats_str
    )
    
    update_memory = ai_result.get('update_memory')
    if update_memory and isinstance(update_memory, str):
        await database.update_user_memory(user_id, update_memory)
    
    action = ai_result.get('action', 'ignore')
    points = int(ai_result.get('points', 0))
    category = ai_result.get('category', 'Диалог')
    comment = ai_result.get('comment', '')
    is_mega = ai_result.get('is_mega', False) or category == 'Мега'

    if (action == 'ignore' or not comment) and not is_direct:
        return

    # Fallback if AI still says ignore or returns empty comment for a direct mention
    if (action == 'ignore' or not comment) and is_direct:
        action = 'chat'
        comment = "слышь, я сейчас не в настроении на философию. попробуй позже."

    mention = get_user_mention({'username': username, 'full_name': full_name})

    if action == 'add_points':
        if is_mega:
            activity_id = await database.add_activity(user_id, message.text, points, category, is_mega=True, is_approved=False)
            builder = InlineKeyboardBuilder()
            builder.button(text=f"✅ База (0/{MIN_VOTES})", callback_data=f"vote_{activity_id}")
            await message.reply(
                f"🔥 **ИСТИННАЯ СИЛА ОБНАРУЖЕНА!** 🔥\n\n{mention} утверждает: *{message.text}*\n\n"
                f"Вердикт бота: *{comment}*\n\n"
                f"Пацаны, нужно **{MIN_VOTES} голоса**, чтобы вписать это в историю (+{points} баллов)!",
                reply_markup=builder.as_markup(),
                parse_mode="Markdown"
            )
        else:
            activity_id = await database.add_activity(user_id, message.text, points, category, is_mega=False, is_approved=True)
            await database.update_score(user_id, points)
            
            builder = InlineKeyboardBuilder()
            builder.button(text=f"⚖️ Оспорить (0)", callback_data=f"dispute_{activity_id}")
            
            await message.reply(
                f"💎 **база пополнена на {points} баллов!**\nразряд: {category}\n\n*{comment}*",
                reply_markup=builder.as_markup(),
                parse_mode="Markdown"
            )
    elif action == 'remove_points':
        activity_id = await database.add_activity(user_id, message.text, -points, "анти", is_mega=False, is_approved=True)
        await database.update_score(user_id, -points)
        
        builder = InlineKeyboardBuilder()
        builder.button(text=f"⚖️ Оспорить (0)", callback_data=f"dispute_{activity_id}")
        
        await message.reply(
            f"💀 **штраф {points} баллов силы!**\n\n*{comment}*",
            reply_markup=builder.as_markup(),
            parse_mode="Markdown"
        )
    elif action == 'chat':
        await message.reply(comment)

@dp.callback_query(F.data.startswith("vote_"))
async def handle_vote(callback: CallbackQuery):
    activity_id = int(callback.data.split("_")[1])
    voter_id = callback.from_user.id
    votes_count = await database.add_vote(activity_id, voter_id)
    
    if votes_count == -1:
        await callback.answer("Твоя воля уже учтена.", show_alert=True)
        return
    
    if votes_count >= MIN_VOTES:
        activity = await database.approve_activity(activity_id)
        if activity:
            await callback.message.edit_text(
                f"✅ **СИЛА ПОДТВЕРЖДЕНА!**\n\n*{activity['description']}*\n\nБаллы вписаны в базу.",
                parse_mode="Markdown"
            )
            await callback.answer("Успех.")
    else:
        builder = InlineKeyboardBuilder()
        builder.button(text=f"✅ База ({votes_count}/{MIN_VOTES})", callback_data=f"vote_{activity_id}")
        await callback.message.edit_reply_markup(reply_markup=builder.as_markup())
        await callback.answer("Голос принят.")

@dp.callback_query(F.data.startswith("dispute_"))
async def handle_dispute(callback: CallbackQuery):
    activity_id = int(callback.data.split("_")[1])
    user_id = callback.from_user.id
    chat_id = callback.message.chat.id
    
    dispute = await database.get_dispute_by_activity(activity_id)
    member_count = await bot.get_chat_member_count(chat_id)
    required_to_launch = ((member_count - 1) // 2) + 1
    
    if not dispute:
        dispute_id = await database.create_dispute(activity_id, chat_id, callback.message.message_id, required_to_launch)
    else:
        dispute_id = dispute['id']
        
    signatures_count = await database.add_dispute_signature(dispute_id, user_id)
    
    if signatures_count == -1:
        await callback.answer("Ты уже подписался на диспут.", show_alert=True)
        return
        
    if signatures_count >= required_to_launch:
        poll_msg = await bot.send_poll(
            chat_id=chat_id,
            question=f"Опровергнуть вердикт бота по делу #{activity_id}?",
            options=["Отменить решение", "Оставить как есть"],
            is_anonymous=False
        )
        await database.update_dispute_poll(dispute_id, poll_msg.poll.id)
        await callback.message.edit_reply_markup(reply_markup=None)
        await callback.answer("Диспут запущен! Голосуйте в опросе.")
    else:
        builder = InlineKeyboardBuilder()
        builder.button(text=f"⚖️ Сбор на диспут ({signatures_count}/{required_to_launch})", callback_data=f"dispute_{activity_id}")
        await callback.message.edit_reply_markup(reply_markup=builder.as_markup())
        await callback.answer("Подпись принята.")

@dp.poll()
async def handle_poll(poll: types.Poll):
    dispute = await database.get_dispute_by_poll_id(poll.id)
    if not dispute:
        return
        
    if dispute['status'] != 'polling':
        return
        
    cancel_votes = poll.options[0].voter_count
    keep_votes = poll.options[1].voter_count
    
    if keep_votes > 0:
        await database.set_dispute_status(dispute['id'], 'rejected')
        await bot.send_message(dispute['chat_id'], f"⚖️ Диспут по делу #{dispute['activity_id']} провален! Вердикт остается в силе.")
        return
        
    member_count = await bot.get_chat_member_count(dispute['chat_id'])
    required_to_win = member_count - 1
    
    if cancel_votes >= required_to_win:
        await database.set_dispute_status(dispute['id'], 'resolved')
        await database.delete_activity(dispute['activity_id'])
        await bot.send_message(dispute['chat_id'], f"⚖️ Диспут по делу #{dispute['activity_id']} выигран! Вердикт отменен, баллы возвращены.")

# Daily Penalty Task
async def daily_penalty():
    await database.apply_daily_penalty()
    chat_id = await database.get_setting("main_chat_id") or os.getenv("ADMIN_CHAT_ID")
    if chat_id:
        try:
            await bot.send_message(chat_id, "💀 **ПОЛНОЧЬ. ВРЕМЯ РАСПЛАТЫ.**\n\nС каждого списано по **10 баллов** за простой. Если сегодня ты не проявил силы — ты стал на шаг ближе к блажи.\n\nПроверь /top, если осмелишься.", parse_mode="Markdown")
        except Exception as e:
            logger.error(f"Failed to send penalty message: {e}")
    logger.info("Daily penalty applied.")

# Heartbeat Audit Task
async def heartbeat_audit():
    chat_id = await database.get_setting("main_chat_id") or os.getenv("ADMIN_CHAT_ID")
    if not chat_id:
        return
    
    # Ensure it's an int for dict lookup
    try:
        chat_id_int = int(chat_id)
    except:
        return

    history = CHAT_HISTORY.get(chat_id_int, [])
    if not history:
        return
        
    audit_prompt = (
        "ты — джо кэмел. проведи внезапный аудит последних событий в чате. "
        "посмотри, кто проявлял силу, кто нес блажь, а кто просто молчал. "
        "выдай язвительное или одобряющее саммари последних 15 сообщений. "
        "используй наши термины: база, сила, рогалик, анти, блажь. "
        "можешь раздать небольшие бонусы (+5) или штрафы (-5) за общее поведение. "
        "ответь в json: { \"comment\": \"текст\", \"awards\": [{ \"user_name\": \"имя\", \"points\": число }] }"
    )
    
    try:
        history_str = "\n".join([f"{m['name']}: {m['text']}" for m in history])
        response = scorer.client.models.generate_content(
            model=scorer.model_name,
            contents=f"{audit_prompt}\n\nСобытия:\n{history_str}",
            config={'response_mime_type': 'application/json'}
        )
        
        data = json.loads(response.text)
        comment = data.get('comment')
        awards = data.get('awards', [])
        
        if comment:
            msg = f"🛰 **ВНЕЗАПНЫЙ АУДИТ БАЗЫ** 🛰\n\n{comment}\n\n"
            applied_awards = []
            
            if awards:
                # Create name -> id map from history
                name_to_id = {m['name']: m['id'] for m in history}
                
                for a in awards:
                    u_name = a.get('user_name')
                    pts = a.get('points', 0)
                    if u_name in name_to_id and pts != 0:
                        u_id = name_to_id[u_name]
                        await database.update_score(u_id, pts)
                        sign = "+" if pts > 0 else ""
                        applied_awards.append(f"• {u_name}: {sign}{pts} баллов")
            
            if applied_awards:
                msg += "⚖️ **Изменения в базе:**\n" + "\n".join(applied_awards)
            
            await bot.send_message(chat_id_int, msg, parse_mode="Markdown")
            # Clear history after audit to avoid double-processing the same block?
            # Or just keep it as a sliding window. Let's keep it as sliding window.
    except Exception as e:
        logger.error(f"Heartbeat audit error: {e}")


async def main():
    await database.init_db()
    
    # Daily penalty at 00:00
    scheduler.add_job(daily_penalty, CronTrigger(hour=PENALTY_HOUR, minute=PENALTY_MINUTE))
    
    # Heartbeat audit every 4 hours
    scheduler.add_job(heartbeat_audit, IntervalTrigger(hours=4))
    
    scheduler.start()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
