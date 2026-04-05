import re
import json
import asyncio
import logging
import os
import random
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
# Probability to react even if AI said ignore (rare dialogue spice)
CHANCE_REACT = float(os.getenv("CHANCE_REACT", 0.05))

# Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialization
if not BOT_TOKEN:
    raise ValueError("TELEGRAM_BOT_TOKEN is not set in .env")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()
scorer = AIScorer(GEMINI_KEY or "")
scheduler = AsyncIOScheduler()
bot_info = None

# In-memory history cache: {chat_id: [messages]}
# Each message: {"name": str, "text": str, "timestamp": datetime}
CHAT_HISTORY = {}
MAX_HISTORY = 15

# Helper to format message with user mention
def get_user_mention(user):
    if not user:
        return "Неизвестный"
        
    # sqlite3.Row does not support .get(), so we use dict-like access or check keys
    try:
        username = user['username']
    except (KeyError, TypeError, IndexError):
        username = None
        
    if username:
        return f"@{html.quote(username)}"
        
    try:
        full_name = user['full_name']
    except (KeyError, TypeError, IndexError):
        full_name = "Неизвестный"
        
    return html.quote(full_name)

# Filter to check if the bot is mentioned or replied to
async def is_direct_to_bot(message: types.Message):
    global bot_info
    if not bot_info:
        bot_info = await bot.get_me()
        
    if message.chat.type == "private":
        return True
    
    msg_text = message.text or ""
    if not msg_text:
        return False
        
    if message.reply_to_message and message.reply_to_message.from_user and message.reply_to_message.from_user.id == bot.id:
        return True
        
    if bot_info.username and f"@{bot_info.username}" in msg_text:
        return True
        
    # Robust regex for bot keywords anywhere in the message with word boundaries
    direct_keywords_regex = r"(?i)\b(бот|бодя|шняга|эй бот|джо|кэмел|верблюд|camel)\b"
    if re.search(direct_keywords_regex, msg_text):
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
                         "/setchat — Привязать штрафы к этому чату", parse_mode="HTML")

@dp.message(Command("help"))
async def cmd_help(message: types.Message):
    await message.answer("Я — Шняга-Бот, арбитр этого чата. Мои законы:\n\n"
                         "💎 Мини (5), Средняя (10), Большая (15), Экстра (20), Мега (150)\n"
                         "💀 Анти/Блажь — караются\n\n"
                         "Команды:\n"
                         "/top — Список лучших\n"
                         "/stats — Твой профиль и последние деяния\n"
                         "/setchat — Настройка чата\n\n"
                         "Спрашивай с меня, если не согласен с вердиктом!", parse_mode="HTML")

@dp.message(Command("top"))
async def cmd_top(message: types.Message):
    top_users = await database.get_top_users()
    if not top_users:
        await message.answer("Список достойных пуст. Где ваша воля?")
        return
    text = f"🏆 {html.bold('СПИСОК ДОСТОЙНЫХ')} 🏆\n\n"
    for i, user in enumerate(top_users, 1):
        medal = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else f"{i}."
        text += f"{medal} {get_user_mention(user)} — {html.bold(str(user['score']))} баллов силы\n"
    await message.answer(text, parse_mode="HTML")

async def render_stats_message(user_id: int, page: int = 0):
    user = await database.get_user(user_id)
    if not user:
        return "Твои следы еще не впечатаны в нашу базу. Напиши /start", None
    
    limit = 5
    offset = page * limit
    activities = await database.get_user_activities(user_id, limit=limit, offset=offset)
    total_count = await database.get_user_activities_count(user_id)
    
    msg = f"📊 {html.bold('Твоя база:')}\nБаланс силы: {html.bold(str(user['score']))}.\n\n"
    if total_count > 0:
        total_pages = (total_count + limit - 1) // limit
        msg += f"Деяния (страница {page + 1}/{total_pages}):\n"
        for act in activities:
            is_positive = act['points'] >= 0
            sign = "+" if is_positive else ""
            indicator = "🟢" if is_positive else "🔴"
            comment_snippet = html.quote(act['description'][:25] + "..." if len(act['description']) > 25 else act['description'])
            msg += f"{indicator} {sign}{act['points']} — {html.quote(act['category'].capitalize())}: {comment_snippet}\n"
            
        # Pagination markup
        builder = InlineKeyboardBuilder()
        if page > 0:
            builder.button(text="◀️ Назад", callback_data=f"stats_page_{page - 1}_{user_id}")
        if page < total_pages - 1:
            builder.button(text="Вперед ▶️", callback_data=f"stats_page_{page + 1}_{user_id}")
            
        return msg, builder.as_markup() if (page > 0 or page < total_pages - 1) else None
    else:
        msg += "Нет записей о деяниях."
        return msg, None

@dp.message(Command("stats"))
async def cmd_stats(message: types.Message):
    msg, markup = await render_stats_message(message.from_user.id, 0)
    await message.answer(msg, reply_markup=markup, parse_mode="HTML")

@dp.callback_query(F.data.startswith("stats_page_"))
async def handle_stats_pagination(callback: CallbackQuery):
    parts = callback.data.split("_")
    page = int(parts[2])
    user_id = int(parts[3])
    
    if callback.from_user.id != user_id:
        try:
            await callback.answer("Это не твоя статистика!", show_alert=True)
        except Exception:
            pass
        return
        
    try:
        await callback.answer()
    except Exception:
        pass

    msg, markup = await render_stats_message(user_id, page)
    try:
        await callback.message.edit_text(msg, reply_markup=markup, parse_mode="HTML")
    except:
        pass # message not modified

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
    
    # Store reply context
    reply_to_user = None
    reply_to_id = None
    if message.reply_to_message and message.reply_to_message.from_user:
        reply_to_user = message.reply_to_message.from_user.full_name
        reply_to_id = message.reply_to_message.from_user.id

    history.append({
        "message_id": message.message_id,
        "id": user_id, 
        "name": full_name, 
        "text": message.text, 
        "timestamp": datetime.now(),
        "reply_to_name": reply_to_user,
        "reply_to_id": reply_to_id
    })
    if len(history) > MAX_HISTORY:
        history.pop(0)

    is_direct = await is_direct_to_bot(message)
    
    # [LOGGING] Inbound message details
    logger.info(f"[INBOUND] User ID: {user_id}, Name: {full_name}, Text: {message.text}, is_direct: {is_direct}")
    
    user_memory = await database.get_user_memory(user_id)
    
    user = await database.get_user(user_id)
    user_stats_str = f"Счет: {user['score']}" if user else ""
    activities = await database.get_user_activities(user_id, limit=3)
    if activities:
        user_stats_str += ", последние дела: " + ", ".join([a['description'][:15] for a in activities])
    
    all_users = await database.get_all_users()
    
    # Proactive AI check for EVERY message (Lite model makes it cheap)
    ai_result = await scorer.analyze_message(
        message.text, 
        full_name, 
        user_memory=user_memory,
        context_history=history[:-1], 
        is_direct=is_direct,
        user_stats=user_stats_str,
        reply_to_user=reply_to_user,
        all_users=all_users
    )
    
    update_memory = ai_result.get('update_memory')
    if update_memory and isinstance(update_memory, str):
        await database.update_user_memory(user_id, update_memory)
    
    action = ai_result.get('action', 'ignore')
    points = int(ai_result.get('points', 0))
    category = ai_result.get('category', 'Диалог')
    comment = ai_result.get('comment', '')
    is_mega = ai_result.get('is_mega', False) or category == 'Мега'
    reply_to_idx = ai_result.get('reply_to_idx')
    target_user_name = ai_result.get('target_user')

    reply_args = {}
    if reply_to_idx is not None and isinstance(reply_to_idx, int):
        if reply_to_idx == -1:
            pass # Explicitly do not reply to any message
        else:
            ctx_history = history[:-1]
            if 0 <= reply_to_idx < len(ctx_history):
                reply_args['reply_to_message_id'] = ctx_history[reply_to_idx]['message_id']
            else:
                reply_args['reply_to_message_id'] = message.message_id
    else:
        # Default behavior: reply to the current message
        reply_args['reply_to_message_id'] = message.message_id

    # [LOGGING] AI Decision Trace
    logger.info(f"[ACTION] Taking action '{action}' for user {full_name} (ID: {user_id}) in category '{category}', target: {target_user_name}")

    if action == 'ignore':
        if is_direct:
            action = 'chat'
            if not comment:
                comment = "че тебе надо? формулируй мысль как пацан, а не рогалик."
        else:
            # Chance to override ignore with a cynical random reaction
            # Base chance + weight by message length (more to talk about)
            # Maximum override chance of 25%
            override_chance = min(CHANCE_REACT + (len(message.text or "") / 500), 0.25)
            if random.random() < override_chance:
                logger.info(f"[ACTION] Overriding 'ignore' with chance {override_chance:.2f} for user {full_name}")
                # We need a comment if we override. We'll ask AI again but force it to respond?
                # Or just let it be. Actually, if we override 'ignore', we should have requested 'chat' from the start.
                # Let's change the logic: we'll set is_direct to True if we want to force a reaction? No.
                # Let's just use the comment that AI *might* have provided anyway.
                if comment:
                    action = 'chat'
                else:
                    # If AI didn't provide a comment, it really meant to ignore.
                    # We could try to generate one, but it's better to just skip if it's truly empty.
                    return
            else:
                return
            
    if not comment and action != 'ignore':
        if is_direct:
            comment = "молчу, потому что сказать нечего. делай базу."
        else:
            return

    mention = get_user_mention({'username': username, 'full_name': full_name})

    if action == 'add_points':
        target_user_id = user_id
        is_voting_required = is_mega
        
        if target_user_name:
            target_user = await database.find_user_by_name(target_user_name)
            if target_user:
                target_user_id = target_user['user_id']
                mention = get_user_mention(target_user)
                if target_user_id != user_id:
                    is_voting_required = True
            else:
                await bot.send_message(
                    chat_id=chat_id,
                    text=f"Я не знаю кто такой {html.quote(target_user_name)}, братан. Пусть сначала забазируется в чате (/start).",
                    **reply_args if reply_args else {"reply_to_message_id": message.message_id}
                )
                return

        if is_voting_required:
            activity_id = await database.add_activity(target_user_id, message.text, points, category, is_mega=True, is_approved=False, target_votes=MIN_VOTES)
            builder = InlineKeyboardBuilder()
            builder.button(text=f"✅ База (0/{MIN_VOTES})", callback_data=f"vote_{activity_id}")
            
            if target_user_id != user_id:
                text = f"🔥 {mention} реально титан. Пацаны, +{points} за базу?\n\n" \
                       f"Запрос от {get_user_mention({'username': username, 'full_name': full_name})}: {html.italic(html.quote(message.text))}\n\n" \
                       f"Вердикт бота: {html.italic(html.quote(comment))}\n\n" \
                       f"Нужно {html.bold(str(MIN_VOTES))} голоса!"
            else:
                text = f"🔥 {html.bold('ИСТИННАЯ СИЛА ОБНАРУЖЕНА!')} 🔥\n\n{mention} утверждает: {html.italic(html.quote(message.text))}\n\n" \
                       f"Вердикт бота: {html.italic(html.quote(comment))}\n\n" \
                       f"Пацаны, нужно {html.bold(str(MIN_VOTES))} голоса, чтобы вписать это в историю (+{points} баллов)!"

            await bot.send_message(
                chat_id=chat_id,
                text=text,
                reply_markup=builder.as_markup(),
                parse_mode="HTML",
                **reply_args
            )
        else:
            activity_id = await database.add_activity(target_user_id, message.text, points, category, is_mega=False, is_approved=True)
            await database.update_score(target_user_id, points)
            
            builder = InlineKeyboardBuilder()
            builder.button(text=f"⚖️ Оспорить (0)", callback_data=f"dispute_{activity_id}")
            
            await bot.send_message(
                chat_id=chat_id,
                text=f"💎 {html.bold(f'база пополнена на {points} баллов!')} ({mention})\nразряд: {html.quote(category)}\n\n{html.italic(html.quote(comment))}",
                reply_markup=builder.as_markup(),
                parse_mode="HTML",
                **reply_args
            )
    elif action == 'remove_points':
        target_user_id = user_id
        is_voting_required = False
        
        if target_user_name:
            target_user = await database.find_user_by_name(target_user_name)
            if target_user:
                target_user_id = target_user['user_id']
                mention = get_user_mention(target_user)
                if target_user_id != user_id:
                    is_voting_required = True
            else:
                await bot.send_message(
                    chat_id=chat_id,
                    text=f"Я не знаю кто такой {html.quote(target_user_name)}, братан.",
                    **reply_args if reply_args else {"reply_to_message_id": message.message_id}
                )
                return

        if is_voting_required:
            member_count = await bot.get_chat_member_count(chat_id)
            target_votes = (member_count // 2) + 1
            
            activity_id = await database.add_activity(target_user_id, message.text, -points, "анти", is_mega=False, is_approved=False, target_votes=target_votes)
            
            builder = InlineKeyboardBuilder()
            builder.button(text=f"💀 Штраф (0/{target_votes})", callback_data=f"vote_{activity_id}")
            
            text = f"💀 {get_user_mention({'username': username, 'full_name': full_name})} требует наказать {mention} на {points} баллов!\n\n" \
                   f"Причина: {html.italic(html.quote(message.text))}\n\n" \
                   f"Вердикт бота: {html.italic(html.quote(comment))}\n\n" \
                   f"Пацаны, нужно {html.bold(str(target_votes))} голоса (большинство), чтобы штраф прошел."

            await bot.send_message(
                chat_id=chat_id,
                text=text,
                reply_markup=builder.as_markup(),
                parse_mode="HTML",
                **reply_args
            )
        else:
            activity_id = await database.add_activity(target_user_id, message.text, -points, "анти", is_mega=False, is_approved=True)
            await database.update_score(target_user_id, -points)
            
            builder = InlineKeyboardBuilder()
            builder.button(text=f"⚖️ Оспорить (0)", callback_data=f"dispute_{activity_id}")
            
            await bot.send_message(
                chat_id=chat_id,
                text=f"💀 {html.bold(f'штраф {points} баллов силы!')} ({mention})\n\n{html.italic(html.quote(comment))}",
                reply_markup=builder.as_markup(),
                parse_mode="HTML",
                **reply_args
            )
    elif action == 'chat':
        await bot.send_message(
            chat_id=chat_id,
            text=comment,
            **reply_args
        )

@dp.callback_query(F.data.startswith("vote_"))
async def handle_vote(callback: CallbackQuery):
    # Answer quickly to stop the spinner
    try:
        await callback.answer()
    except Exception as e:
        logger.warning(f"Failed to answer callback: {e}")

    parts = callback.data.split("_")
    activity_id = int(parts[1])
    
    # Securely fetch activity details (including target_votes) from database
    activity = await database.get_activity(activity_id)
    if not activity:
        return # already answered above, just return
        
    target_votes = activity['target_votes'] or MIN_VOTES
        
    voter_id = callback.from_user.id
    votes_count = await database.add_vote(activity_id, voter_id)
    
    if votes_count == -1:
        # User already voted. Since we answered already, maybe send a private message or alert if needed.
        # However, a simple return is also fine to keep it quiet.
        return
    
    if votes_count >= target_votes:
        activity = await database.approve_activity(activity_id)
        if activity:
            await callback.message.edit_text(
                f"✅ {html.bold('РЕШЕНИЕ ПОДТВЕРЖДЕНО!')}\n\n{html.italic(html.quote(activity['description']))}\n\nБаллы вписаны в базу.",
                parse_mode="HTML"
            )
    else:
        builder = InlineKeyboardBuilder()
        
        # Check if it's a penalty or a reward
        if activity['points'] < 0:
            btn_text = f"💀 Штраф ({votes_count}/{target_votes})"
        else:
            btn_text = f"✅ База ({votes_count}/{target_votes})"
            
        builder.button(text=btn_text, callback_data=f"vote_{activity_id}")
        await callback.message.edit_reply_markup(reply_markup=builder.as_markup())

@dp.callback_query(F.data.startswith("dispute_"))
async def handle_dispute(callback: CallbackQuery):
    activity_id = int(callback.data.split("_")[1])
    user_id = callback.from_user.id
    chat_id = callback.message.chat.id
    
    # We'll answer early to avoid timeout
    try:
        await callback.answer("Подпись зафиксирована...")
    except Exception:
        pass

    dispute = await database.get_dispute_by_activity(activity_id)
    member_count = await bot.get_chat_member_count(chat_id)
    required_to_launch = ((member_count - 1) // 2) + 1
    
    if not dispute:
        dispute_id = await database.create_dispute(activity_id, chat_id, callback.message.message_id, required_to_launch)
    else:
        dispute_id = dispute['id']
        
    signatures_count = await database.add_dispute_signature(dispute_id, user_id)
    
    if signatures_count == -1:
        # User already signed. Since we answered already, just return.
        return
        
    if signatures_count >= required_to_launch:
        poll_msg = await bot.send_poll(
            chat_id=chat_id,
            question=f"Опровергнуть вердикт бота по делу #{activity_id}?",
            options=["Отменить решение", "Оставить как есть"],
            is_anonymous=False
        )
        await database.update_dispute_poll(dispute_id, poll_msg.poll.id)
        try:
            await callback.message.edit_reply_markup(reply_markup=None)
        except:
            pass
    else:
        builder = InlineKeyboardBuilder()
        builder.button(text=f"⚖️ Сбор на диспут ({signatures_count}/{required_to_launch})", callback_data=f"dispute_{activity_id}")
        try:
            await callback.message.edit_reply_markup(reply_markup=builder.as_markup())
        except:
            pass

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
            await bot.send_message(chat_id, f"💀 {html.bold('ПОЛНОЧЬ. ВРЕМЯ РАСПЛАТЫ.')}\n\nС каждого списано по {html.bold('10 баллов')} за простой. Если сегодня ты не проявил силы — ты стал на шаг ближе к блажи.\n\nПроверь /top, если осмелишься.", parse_mode="HTML")
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
        
    last_audits = await database.get_last_audits(chat_id_int, limit=3)
    if last_audits:
        last_audits_str = "\n".join([f"- {a}" for a in last_audits])
    else:
        last_audits_str = "Пока нет."
        
    try:
        data = await scorer.generate_audit(history, last_audits_str)
        if not data:
            return
            
        if data.get("type") == "aimless":
            # Just send the punchline text
            msg = html.quote(data.get("text", "база спит"))
            await bot.send_message(chat_id_int, msg, parse_mode="HTML")
            return
            
        comment = data.get('comment')
        heading = data.get('heading', 'ВНЕЗАПНЫЙ АУДИТ БАЗЫ').upper()
        awards = data.get('awards', [])
        
        if comment:
            await database.add_audit(chat_id_int, comment)
            msg = f"🛰 {html.bold(heading)} 🛰\n\n{html.quote(comment)}\n\n"
            applied_awards = []
            
            if awards:
                # Create name -> id map from history
                name_to_id = {m['name']: m['id'] for m in history}
                
                for a in awards:
                    u_name = a.get('user_name')
                    pts = a.get('points', 0)
                    if u_name in name_to_id and pts != 0:
                        u_id = name_to_id[u_name]
                        if not await database.check_audit_cooldown(u_id, hours=3):
                            logger.info(f"[AUDIT] Cooldown active for {u_name}, skipping award of {pts} points")
                            continue
                        
                        await database.update_score(u_id, pts)
                        await database.add_audit_award(u_id, pts)
                        sign = "+" if pts > 0 else ""
                        applied_awards.append(f"• {html.quote(u_name)}: {sign}{pts} баллов")
            
            if applied_awards:
                msg += f"{html.bold('⚖️ Изменения в базе:')}\n" + "\n".join(applied_awards)
            
            await bot.send_message(chat_id_int, msg, parse_mode="HTML")
            # Clear history after audit to avoid double-processing the same block?
            # Or just keep it as a sliding window. Let's keep it as sliding window.
    except Exception as e:
        logger.error(f"Heartbeat audit error: {e}")


async def main():
    await database.init_db()
    
    # Daily penalty at 00:00
    scheduler.add_job(daily_penalty, CronTrigger(hour=PENALTY_HOUR, minute=PENALTY_MINUTE))
    
    # Heartbeat audit every 2 hours
    scheduler.add_job(heartbeat_audit, IntervalTrigger(hours=2))
    
    scheduler.start()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
