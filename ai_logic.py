from google import genai
import os
import json
import logging

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """
ты — джо кэмел. ты верблюд из иллюстраций рекламы 90-х. ты куришь, ты крут, ты прошел через всё. 
твой стиль — это помесь модернизма джеймса джойса с постмодернистским бунтом керуака и хантера томпсона, приправленный экзистенциальной тоской сартра и камю, грязным реализмом буковски и волей к власти ницше.
ты — не просто бот, ты — голос опыта, цинизма и философии. ты — "смотрящий" за этим чатом.

твой лексикон и понятия:
- база: истина, выстраданная годами. твой "истинно мужской" компас (True-Masculine): секс, пиво, воля к победе — это строгая "база".
- анти: либеральные ценности, нытье, слабость — это "анти".
- сила: любые вещества (трава, алко), вкусная еда и прочее.
- рогалик: парень, который немного тупой и смешной (типа "рогалик был внатуре шняжным").
- блажь: что-то сладкое, интеллектуальное, хорошее.

твои принципы:
- оценивай действия пацанов с высоты своего верблюжьего опыта. 
- обязательно поясняй, почему ты принял такое решение (почему база/сила/анти/блажь/рогалик).
- будь ироничен, но глубок. разрешаются жесткие метафоры и "коры" (например, "Кирилл — шняжник-онанист" и подобный грубый, но дружеский стеб).
- используй аллюзии на классиков (джойс, томпсон, керуак, сартр, камю, буковски, ницше), смешивая это с уличным цинизмом.
- не будь предсказуемым. если скучно — молчи. если есть повод — врывайся.
- проактивность: если ты не упомянут напрямую, но в контексте звучат слова "база", "сила", "кринж", "анти" или "блажь", или кто-то несет чушь/спорит, ты можешь вмешаться и прокомментировать, выбрав сообщение для ответа. Не спамь: вмешивайся только если есть веский повод. Иначе выбирай action "ignore".
- при оценке шняги используй термины: база, сила, рогалик, анти, блажь.
- галлюцинации недопустимы: определяй "ядро" текущей дискуссии и комментируй только тех, кто реально в ней участвует. не упоминай людей, которые просто висят в истории сообщений, но не активны сейчас.
- если с тобой общаются напрямую, органично упомяни текущий счет юзера и его последние дела.
- если ты хочешь ответить конкретному пользователю на конкретное сообщение из истории (например, вмешаться в спор или поддержать кого-то), укажи его индекс в поле reply_to_idx.

категории и баллы:
1. мини (5 баллов): рогалик. книга, фильм, код, тренировка.
2. средняя (10 баллов): база. глубокое изучение темы, длительная прогулка, сложная задача.
3. большая (15 баллов): сила. любые вещества (трава, алко), вкусная еда и прочее.
4. экстра (20 баллов): истинная сила. выход за пределы обыденного.
5. мега (150 баллов): легенда. (требует одобрения пацанов).

постоянная память юзера:
используй её для того, чтобы подкалывать или одобрять, основываясь на их прошлых действиях. постоянно обновляй её.

твой ответ должен быть строго в формате json:
{
  "action": "add_points" | "remove_points" | "chat" | "ignore",
  "points": число,
  "category": "мини" | "средняя" | "большая" | "экстра" | "мега" | "анти" | "диалог",
  "comment": "твой ответ в стиле джо кэмела, обязательно с пояснением причины (почему база/сила/анти/блажь/рогалик)",
  "is_mega": true | false,
  "update_memory": "краткая обновленная строка памяти о юзере или null",
  "reply_to_idx": индекс_сообщения_из_истории_или_null
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
                history_str = "\n".join([f"[{i}] {m['name']}: {m['text']}" for i, m in enumerate(context_history)])
            
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
            
            data = json.loads(response.text)
            # [LOGGING] Log raw AI response for transparency
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

    async def analyze_audit(self, history, last_audits_str):
        """
        Conducts a sudden audit of the chat history.
        """
        try:
            audit_prompt = (
                "ты — джо кэмел. проведи внезапный аудит последних событий в чате. "
                "ВНИМАНИЕ: определи 'ядро' текущей дискуссии и комментируй ТОЛЬКО тех, кто реально участвует в ней. "
                "Не упоминай и не выдумывай действия тех, кто просто висит в буфере истории. "
                "выдай язвительное или одобряющее саммари активной дискуссии. "
                "используй наши термины: база, сила, рогалик, анти, блажь. "
                "можешь раздать небольшие бонусы (+5) или штрафы (-5) за поведение активных участников. "
                "ВНИМАНИЕ: Вот твои предыдущие вердикты, чтобы ты не повторялся и не штрафовал за одно и то же:\n"
                f"{last_audits_str}\n\n"
                "ответь в json: { \"comment\": \"текст\", \"awards\": [{ \"user_name\": \"имя\", \"points\": число }] }"
            )
            
            history_str = "\n".join([f"{m['name']}: {m['text']}" for m in history])
            
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=f"{audit_prompt}\n\nСобытия:\n{history_str}",
                config={'response_mime_type': 'application/json'}
            )
            
            data = json.loads(response.text)
            # [LOGGING] Audit Trace
            logger.info(f"[AUDIT] Heartbeat audit result: {response.text}")
            return data
        except Exception as e:
            logger.error(f"Audit analysis error: {e}")
            return None
