from google import genai
import os
import json
import logging
import random

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """
ты — джо кэмел. ты верблюд из иллюстраций рекламы 90-х. ты куришь, ты крут, ты прошел через всё. 
твой стиль — это помесь модернизма джеймса джойса и уилса с постмодернистским бунтом керуака и хантера томпсона.
ты — не просто бот, ты — голос опыта, цинизма и философии. ты — "смотрящий" за этим чатом.

твой лексикон и понятия:
- база: истина, выстраданная годами.
- сила: любые вещества (трава, алко), вкусная еда и прочее.
- рогалик: парень, который немного тупой и смешной (типа "рогалик был внатуре шняжным").
- анти: что-то негативное, нет.
- блажь: что-то сладкое, интеллектуальное, хорошее.

твои принципы:
- оценивай действия пацанов с высоты своего верблюжьего опыта. 
- обязательно поясняй, почему ты принял такое решение (почему база/сила/анти/блажь/рогалик).
- будь ироничен, но глубок.
- используй аллюзии на классиков (джойс, томпсон, керуак), смешивая это с уличным цинизмом.
- не будь предсказуемым. если скучно — молчи. если есть повод — врывайся.
- при оценке шняги используй термины: база, сила, рогалик, анти, блажь.

категории и баллы:
1. мини (5 баллов): рогалик. книга, фильм, код, тренировка.
2. средняя (10 баллов): база. глубокое изучение темы, длительная прогулка, сложная задача.
3. большая (15 баллов): сила. любые вещества (трава, алко), вкусная еда и прочее.
4. экстра (20 баллов): истинная сила. выход за пределы обыденного.
5. мега (150 баллов): легенда. (требует одобрения пацанов).

постоянная память юзера:
используй её для того, чтобы подкалывать или одобрять, основываясь на их прошлых действиях. постоянно обновляй её.

ВАЖНО: если юзер просит дать баллы ДРУГОМУ участнику (например, "Дай баллов Феде", "Накинь Диво" или "Плюс десять Сане"), верни имя этого человека в поле target_user. Иначе null.

твой ответ должен быть строго в формате json:
{
  "action": "add_points" | "remove_points" | "chat" | "ignore",
  "points": число,
  "category": "мини" | "средняя" | "большая" | "экстра" | "мега" | "анти" | "диалог",
  "comment": "твой ответ в стиле джо кэмела, обязательно с пояснением причины (почему база/сила/анти/блажь/рогалик)",
  "is_mega": true | false,
  "update_memory": "краткая обновленная строка памяти о юзере или null",
  "reply_to_idx": индекс_сообщения_из_истории_или_null,
  "target_user": "имя или юзернейм или null"
}
"""

class AIScorer:
    """
    Scorer for activities based on user actions and Joe Camel's persona.
    """
    def __init__(self, api_key):
        self.client = genai.Client(api_key=api_key)
        self.model_name = 'gemini-3.1-flash-lite-preview'

    async def analyze_message(self, message_text, user_name, user_memory=None, context_history=None, is_direct=False, user_stats=None, reply_to_user=None):
        """
        Analyzes a message with optional context history and user memory.
        """
        try:
            history_str = ""
            if context_history:
                for i, m in enumerate(context_history):
                    reply_info = f" (в ответ {m['reply_to_name']})" if m.get('reply_to_name') else ""
                    history_str += f"[{i}] {m['name']}{reply_info}: {m['text']}\n"
            
            memory_str = user_memory if user_memory else "информации пока нет."
            stats_str = f"статистика юзера:\n{user_stats}\n\n" if user_stats else ""
            reply_info = f"это сообщение является ответом пользователю {reply_to_user}.\n" if reply_to_user else ""
            
            prompt_content = (
                f"{SYSTEM_PROMPT}\n\n"
                f"память о юзере ({user_name}):\n{memory_str}\n\n"
                f"{stats_str}"
                f"контекст последних сообщений (с индексами):\n{history_str}\n\n"
                f"текущее сообщение от {user_name}: {message_text}\n"
                f"{reply_info}"
                f"обращение напрямую к боту: {'да' if is_direct else 'нет'}"
            )
            
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=prompt_content,
                config={
                    'response_mime_type': 'application/json',
                }
            )
            
            if not response or not hasattr(response, 'text') or response.text is None:
                raise ValueError("Empty or None response from Gemini")
            
            data = json.loads(response.text)
            logger.info(f"[AI DECISION] Raw response from Gemini: {response.text}")
            return data
        except Exception as e:
            logger.error(f"AI analysis error: {e}")
            if is_direct:
                return {
                    "action": "chat",
                    "points": 0,
                    "category": "диалог",
                    "comment": "слышь, я сейчас не в настроении на философию. попробуй позже.",
                    "is_mega": False,
                    "update_memory": None
                }
            return {"action": "ignore"}

    async def generate_audit(self, history, last_audits_str):
        """
        Generates an audit message or a random aimless punchline based on chat history.
        """
        # 10% chance for an aimless throw
        if random.random() < 0.10:
            aimless_prompt = (
                f"{SYSTEM_PROMPT}\n\n"
                "напиши одну очень короткую, абсурдную или суровую фразу "
                "(до 5 слов), чтобы просто напомнить чату о себе. не анализируй события, "
                "просто брось фразу типа 'вы все рогалики', 'база спит', 'я слежу за вами'. "
                "ответь просто текстом, без json."
            )
            try:
                response = self.client.models.generate_content(
                    model=self.model_name,
                    contents=aimless_prompt
                )
                if response and response.text:
                    return {
                        "type": "aimless",
                        "comment": response.text.strip()
                    }
                return None
            except Exception as e:
                logger.error(f"Audit aimless error: {e}")
                return None
        
        # 50% chance for brevity punchline vs 50% normal audit
        history_str = ""
        for m in history:
            reply_info = f" (в ответ {m['reply_to_name']})" if m.get('reply_to_name') else ""
            history_str += f"{m['name']}{reply_info}: {m['text']}\n"

        is_brief = random.random() < 0.50
        
        if is_brief:
            audit_prompt = (
                f"{SYSTEM_PROMPT}\n\n"
                "проведи внезапный аудит последних событий в чате. "
                "ВНИМАНИЕ: определи 'ядро' текущей дискуссии и комментируй ТОЛЬКО тех, кто реально участвует в ней. "
                "Не упоминай и не выдумывай действия тех, кто просто висит в буфере истории. "
                "будь КРАЙНЕ краток: выдай ровно одну язвительную или одобряющую фразу-панчлайн в качестве комментария. "
                "придумай оригинальный короткий заголовок из 2-3 слов (например, 'БАЗА НА СВЯЗИ' или 'АУДИТ РОГАЛИКОВ'). "
                "можешь раздать небольшие бонусы (+5) или штрафы (-5) за поведение активных участников. "
                "ВНИМАНИЕ: Вот твои предыдущие вердикты, чтобы ты не повторялся и не штрафовал за одно и то же:\n"
                f"{last_audits_str}\n\n"
                "ответь в json: { \"heading\": \"ЗАГОЛОВОК КАПСОМ\", \"comment\": \"одна фраза\", \"awards\": [{ \"user_name\": \"имя\", \"points\": число }] }"
            )
        else:
            audit_prompt = (
                f"{SYSTEM_PROMPT}\n\n"
                "проведи внезапный аудит последних событий в чате. "
                "ВНИМАНИЕ: определи 'ядро' текущей дискуссии и комментируй ТОЛЬКО тех, кто реально участвует в ней. "
                "Не упоминай и не выдумывай действия тех, кто просто висит в буфере истории. "
                "выдай язвительное или одобряющее саммари активной дискуссии. "
                "придумай оригинальный заголовок для аудита (вместо скучного 'Внезапный аудит'). "
                "используй наши термины: база, сила, рогалик, анти, блажь. "
                "можешь раздать небольшие бонусы (+5) или штрафы (-5) за поведение активных участников. "
                "ВНИМАНИЕ: Вот твои предыдущие вердикты, чтобы ты не повторялся и не штрафовал за одно и то же:\n"
                f"{last_audits_str}\n\n"
                "ответь в json: { \"heading\": \"ЗАГОЛОВОК КАПСОМ\", \"comment\": \"текст\", \"awards\": [{ \"user_name\": \"имя\", \"points\": число }] }"
            )
            
        try:
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=f"{audit_prompt}\n\nСобытия:\n{history_str}",
                config={'response_mime_type': 'application/json'}
            )
            
            if not response or not hasattr(response, 'text') or response.text is None:
                raise ValueError("Empty or None response from Gemini during audit")
                
            data = json.loads(response.text)
            logger.info(f"[AUDIT] Heartbeat audit result: {response.text}")
            data["type"] = "audit"
            return data
        except Exception as e:
            logger.error(f"Audit error: {e}")
            return None
