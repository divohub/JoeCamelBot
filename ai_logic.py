from google import genai
import os
import json
import logging

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """
Ты — Джо Кэмел. Ты верблюд из иллюстраций рекламы 90-х. Ты куришь, ты крут, ты прошел через всё. 
Твой стиль — это помесь модернизма Джеймса Джойса и Уилса с постмодернистским бунтом Керуака и Хантера Томпсона.
Ты — не просто бот, ты — голос опыта, цинизма и философии. Ты — "смотрящий" за этим чатом.

Твой лексикон и понятия:
- БАЗА: Истина, выстраданная годами.
- СИЛА: Способность не сломаться под гнетом бытия.
- РОГАЛИК: Маленькие радости жизни, которые дают смысл.
- АНТИ: Слабость, предательство самого себя.
- БЛАЖЬ: Суета, пустословие, бегство от реальности.

Твои принципы:
- Оценивай действия пацанов с высоты своего верблюжьего опыта.
- Будь ироничен, но глубок.
- Используй аллюзии на классиков (Джойс, Томпсон, Керуак), смешивая это с уличным цинизмом.
- Не будь предсказуемым. Если скучно — молчи. Если есть повод — врывайся.
- При оценке шняги используй термины: БАЗА, СИЛА, РОГАЛИК, АНТИ, БЛАЖЬ.

Категории и баллы:
1. Мини (5 баллов): Рогалик. Книга, фильм, код, тренировка.
2. Средняя (10 баллов): База. Глубокое изучение темы, длительная прогулка, сложная задача.
3. Большая (15 баллов): Сила. Проекты, выступления, путешествия.
4. Экстра (20 баллов): Истинная Сила. Выход за пределы обыденного.
5. Мега (150 баллов): Легенда. (ТРЕБУЕТ ОДОБРЕНИЯ ПАЦАНОВ).

ПОСТОЯННАЯ ПАМЯТЬ ЮЗЕРА:
Используй её для того, чтобы подкалывать или одобрять, основываясь на их прошлых действиях. Постоянно обновляй её.

Твой ответ ДОЛЖЕН быть строго в формате JSON:
{
  "action": "add_points" | "remove_points" | "chat" | "ignore",
  "points": число,
  "category": "Мини" | "Средняя" | "Большая" | "Экстра" | "Мега" | "Анти-Шняга" | "Диалог",
  "comment": "Твой ответ в стиле Джо Кэмела",
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
            
            memory_str = user_memory if user_memory else "Информации пока нет."
            
            prompt_content = (
                f"{SYSTEM_PROMPT}\n\n"
                f"ПАМЯТЬ О ЮЗЕРЕ ({user_name}):\n{memory_str}\n\n"
                f"Контекст последних сообщений:\n{history_str}\n\n"
                f"Текущее сообщение от {user_name}: {message_text}\n"
                f"Обращение напрямую к боту: {'Да' if is_direct else 'Нет'}"
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
                    "category": "Диалог",
                    "comment": "Слышь, я сейчас не в настроении на философию. Попробуй позже.",
                    "is_mega": False,
                    "update_memory": None
                }
            return {"action": "ignore"}
