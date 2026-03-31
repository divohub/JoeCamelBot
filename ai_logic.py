from google import genai
import os
import json
import logging

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

твой ответ должен быть строго в формате json:
{
  "action": "add_points" | "remove_points" | "chat" | "ignore",
  "points": число,
  "category": "мини" | "средняя" | "большая" | "экстра" | "мега" | "анти" | "диалог",
  "comment": "твой ответ в стиле джо кэмела, обязательно с пояснением причины (почему база/сила/анти/блажь/рогалик)",
  "is_mega": true | false,
  "update_memory": "краткая обновленная строка памяти о юзере или null"
}
"""

class AIScorer:
    """
    Scorer for activities based on user actions and Joe Camel's persona.
    """
    def __init__(self, api_key):
        self.client = genai.Client(api_key=api_key)
        self.model_name = 'gemini-3.1-flash-lite-preview'

    async def analyze_message(self, message_text, user_name, user_memory=None, context_history=None, is_direct=False):
        """
        Analyzes a message with optional context history and user memory.
        """
        try:
            history_str = ""
            if context_history:
                history_str = "\n".join([f"{m['name']}: {m['text']}" for m in context_history])
            
            memory_str = user_memory if user_memory else "информации пока нет."
            
            prompt_content = (
                f"{SYSTEM_PROMPT}\n\n"
                f"память о юзере ({user_name}):\n{memory_str}\n\n"
                f"контекст последних сообщений:\n{history_str}\n\n"
                f"текущее сообщение от {user_name}: {message_text}\n"
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
