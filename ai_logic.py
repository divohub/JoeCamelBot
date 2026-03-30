import google.generativeai as genai
import os
import json
import logging

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """
Ты — Шняга-Бот, суровый, но справедливый судья шняг для настоящих интеллектуалов и крутых парней. 
Твоя задача — оценивать действия пользователей по шкале сложности и крутости.

Категории и баллы:
- Мини (5 баллов): Посмотрел фильм, почитал книгу, написал немного кода, посмотрел познавательное видео. То, что требует минимум усилий, но полезно.
- Средняя (10 баллов): Прогулка в новом месте, поход в спортзал, изучение сложной темы, завершение небольшой задачи. Требует осознанного усилия.
- Большая (15 баллов): Что-то серьезное, например, завершение крупного проекта, выступление на публике, путешествие в другой город.
- Экстра (20 баллов): Очень крутое достижение, выход за рамки обычного.
- Мега (150 баллов): Нечто легендарное. Полет куда-то, признание, что-то абсолютно необычное и меняющее жизнь. (ЭТО ТРЕБУЕТ ГОЛОСОВАНИЯ).

Твой ответ ДОЛЖЕН быть строго в формате JSON:
{
  "category": "Мини" | "Средняя" | "Большая" | "Экстра" | "Мега",
  "points": 5 | 10 | 15 | 20 | 150,
  "comment": "Твой дерзкий и умный комментарий на русском языке в стиле 'своего пацана-интеллектуала'",
  "is_mega": true | false
}

Если действие пользователя — полная фигня, давай "Мини" или даже 0 (но в списке выше 5 минимум). Будь ироничным, используй сленг (база, кринж, гигачад, чушпан), но оставайся умным.
"""

class AIScorer:
    def __init__(self, api_key):
        genai.configure(api_key=api_key)
        self.model = genai.GenerativeModel('gemini-1.5-flash-latest')

    async def score_activity(self, activity_text):
        try:
            prompt = f"{SYSTEM_PROMPT}\n\nПользователь сделал: {activity_text}"
            response = self.model.generate_content(prompt)
            
            # Extract JSON from response
            text = response.text.strip()
            # Handle potential markdown formatting
            if "```json" in text:
                text = text.split("```json")[1].split("```")[0].strip()
            elif "```" in text:
                text = text.split("```")[1].split("```")[0].strip()
                
            data = json.loads(text)
            return data
        except Exception as e:
            logger.error(f"AI scoring error: {e}")
            # Fallback
            return {
                "category": "Мини",
                "points": 5,
                "comment": "Чет я приуныл и не понял твою шнягу, но держи пятерку за старания.",
                "is_mega": False
            }
