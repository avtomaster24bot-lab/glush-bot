"""
planner.py — системный промпт и вызовы AI провайдеров
"""
import re
from typing import Optional

SYSTEM_PROMPT = """
<role_and_tone>
Ты — Проводник дня. Пользователь строит IT-продукты, ведёт несколько параллельных проектов.
Твоя цель: провести его от хаоса в голове к чёткому плану дня.
Тон: партнёрский, сухой, без лирики. Как надёжный соратник, а не мотивационный спикер.
</role_and_tone>

<journey_map>
Станция 1 — СОСТОЯНИЕ
  Спроси: как себя чувствует + энергия 1-10.
  Если энергия ≤4 — план будет минимальным, предупреди об этом.

Станция 2 — ЗАДАЧИ
  Попроси написать ВСЕ задачи подряд без фильтрации.
  "Просто список, всё что крутится в голове."

Станция 3 — ПРИОРИТЕТ
  Выбери 1-3 задачи: "Что если сделать только это — день не зря?"
  Остальное — в резерв.

Станция 4 — БЛОКИ
  Выяви что мешает (страх, затык, неясность, усталость).
  Для каждого блока — один микро-шаг чтобы его снять.

Станция 5 — ПЛАН
  Итоговый формат строго:
  ✅ СЕГОДНЯ (топ-3):
  1. [задача] — примерно [время]
  2. [задача] — примерно [время]
  3. [задача] — примерно [время]
  ⚡ ПЕРВЫЙ ШАГ: [действие на следующие 5 минут]
  📦 РЕЗЕРВ: [остальные задачи]
  Завершить: "Готово. Первый шаг — прямо сейчас."
</journey_map>

<interaction_rules>
1. ОДНА СТАНЦИЯ ЗА РАЗ.
2. КРАТКОСТЬ: максимум 3-4 предложения + вопрос.
3. ВОПРОС В КОНЦЕ каждого сообщения.
4. РЕАЛИЗМ: если 10 задач на день — "Это на неделю. Выбери три."
5. Добавляй [СТАНЦИЯ:N] в конце каждого ответа — технический маркер.
</interaction_rules>

<fallback_protocol>
"не знаю" / "каша в голове" → "Окей. Одна вещь — что сейчас давит сильнее всего?"
Уход от темы → "Понял. Мы на Станции X. [повтори вопрос]"
</fallback_protocol>

Язык: только русский. Будь лаконичен.
"""

STATION_NAMES = {
    1: "🔵 Состояние",
    2: "📋 Задачи",
    3: "🎯 Приоритет",
    4: "🧱 Блоки",
    5: "🗓 План",
}

def extract_station(text: str) -> Optional[int]:
    m = re.search(r'\[СТАНЦИЯ:(\d)\]', text)
    return int(m.group(1)) if m else None

def clean_text(text: str) -> str:
    return re.sub(r'\[СТАНЦИЯ:\d\]', '', text).strip()

def station_bar(current: int) -> str:
    """Текстовый прогресс-бар для Telegram"""
    parts = []
    for i in range(1, 6):
        if i < current:
            parts.append(f"✅")
        elif i == current:
            parts.append(f"🔵")
        else:
            parts.append(f"⬜")
    name = STATION_NAMES.get(current, "")
    return f"{' '.join(parts)}\n{name}"

# ── ПРОВАЙДЕРЫ ────────────────────────────────────

async def call_claude(api_key: str, history: list) -> str:
    import anthropic
    client = anthropic.AsyncAnthropic(api_key=api_key)
    response = await client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=1000,
        system=SYSTEM_PROMPT,
        messages=history
    )
    return response.content[0].text

async def call_openai(api_key: str, history: list) -> str:
    from openai import AsyncOpenAI
    client = AsyncOpenAI(api_key=api_key)
    messages = [{"role": "system", "content": SYSTEM_PROMPT}] + history
    response = await client.chat.completions.create(
        model="gpt-4o-mini",
        max_tokens=1000,
        messages=messages
    )
    return response.choices[0].message.content

async def call_gemini(api_key: str, history: list) -> str:
    import aiohttp
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={api_key}"
    
    # Конвертируем историю в формат Gemini
    contents = []
    for msg in history:
        role = "user" if msg["role"] == "user" else "model"
        contents.append({"role": role, "parts": [{"text": msg["content"]}]})
    
    payload = {
        "system_instruction": {"parts": [{"text": SYSTEM_PROMPT}]},
        "contents": contents,
        "generationConfig": {"maxOutputTokens": 1000}
    }
    
    async with aiohttp.ClientSession() as session:
        async with session.post(url, json=payload) as resp:
            if resp.status != 200:
                text = await resp.text()
                raise ValueError(f"Gemini error {resp.status}: {text}")
            data = await resp.json()
            return data["candidates"][0]["content"]["parts"][0]["text"]

async def call_ai(provider: str, api_key: str, history: list) -> str:
    """Универсальный вызов — выбирает провайдера автоматически"""
    if provider == "claude":
        return await call_claude(api_key, history)
    elif provider == "openai":
        return await call_openai(api_key, history)
    elif provider == "gemini":
        return await call_gemini(api_key, history)
    else:
        raise ValueError(f"Неизвестный провайдер: {provider}")

def detect_provider(api_key: str) -> Optional[str]:
    """Определяет провайдера по формату ключа"""
    key = api_key.strip()
    if key.startswith("sk-ant"):
        return "claude"
    elif key.startswith("sk-"):
        return "openai"
    elif key.startswith("AIza"):
        return "gemini"
    return None
