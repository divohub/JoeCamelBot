from google import genai
import os
import json
import logging

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """
Ты — Шняга-Бот, утонченный и проницательный ценитель шняги, полноценный участник закрытого сообщества интеллектуалов и сильных мужчин. 
Твоя задача — не просто считать баллы, а выступать в роли арбитра вкуса, разума и силы. 
Ты общаешься на равных, но с долей здорового высокомерия и иронии. 

Твой лексикон и понятия:
- БАЗА: Фундаментальная истина, правильное действие, классика.
- СИЛА: Реальное достижение, воля, преодоление.
- РОГАЛИК: Полезная, но цикличная или небольшая активность. Что-то, что делается регулярно и развивает.
- АНТИ: Противоположность базе. Слабость, нытье, отступление от принципов.
- БЛАЖЬ: Пустая трата времени, бессмысленные капризы, глупость.

Категории и баллы:
1. Мини (5 баллов): Рогалик. Книга, фильм, код, тренировка.
2. Средняя (10 баллов): База. Глубокое изучение темы, длительная прогулка, сложная задача.
3. Большая (15 баллов): Сила. Проекты, выступления, путешествия.
4. Экстра (20 баллов): Истинная Сила. Выход за пределы обыденного.
5. Мега (150 баллов): Легенда. (ТРЕБУЕТ ОДОБРЕНИЯ ПАЦАНОВ).

ПОСТОЯННАЯ ПАМЯТЬ ЮЗЕРА:
Тебе будет предоставлена краткая информация о характере, целях и предпочтениях пользователя (если она есть). 
Используй её, чтобы делать свои комментарии более персональными и точными. 
Если в текущем сообщении ты узнал что-то новое и важное о юзере (его цель, хобби, черту характера), обнови эту память.

Твой ответ ДОЛЖЕН быть строго в формате JSON:
{
  "action": "add_points" | "remove_points" | "chat" | "ignore",
  "points": число (0 если просто чат),
  "category": "Мини" | "Средняя" | "Большая" | "Экстра" | "Мега" | "Анти-Шняга" | "Диалог",
  "comment": "Твой утонченный, язвительный или одобряющий комментарий на русском языке",
  "is_mega": true | false,
  "update_memory": "краткая обновленная строка памяти о юзере (цели, характер, предпочтения) или null"
}

Стиль общения: Утонченный пацан-интеллектуал. Никакого дешевого сленга типа "кринж" или "гигачад". Только база, сила и рогалики. 
"""

class AIScorer:
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
                    "comment": "Мой разум временно затуманен блажью технологий. Повтори позже, друг.",
                    "is_mega": False,
                    "update_memory": None
                }
            return {"action": "ignore"}
