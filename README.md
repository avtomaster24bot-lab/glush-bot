# Глушь.io — Планировщик дня (Telegram бот)

Бот-проводник по методологии Cognitive Guide Architect. Переводит хаос задач в чёткий план дня через 5 станций.

## Возможности

- 🤖 Поддержка Claude (Anthropic), GPT-4o-mini (OpenAI), Gemini Flash (Google)
- 📋 Блокнот задач с чекбоксами
- 💾 Память диалога между сессиями (SQLite)
- 🔑 Каждый пользователь вводит свой API-ключ

## Деплой на Railway (бесплатно)

### 1. Получи токен бота
- Открой @BotFather в Telegram
- /newbot → следуй инструкциям
- Скопируй токен

### 2. Залей код на GitHub
```bash
git init
git add .
git commit -m "init"
git branch -M main
git remote add origin https://github.com/ТВО_ИМЯ/glush-bot.git
git push -u origin main
```

### 3. Задеплой на Railway
1. Зайди на railway.app → New Project
2. Deploy from GitHub repo → выбери glush-bot
3. Variables → добавь: `BOT_TOKEN=твой_токен`
4. Deploy → готово ✅

### 4. Деплой на Koyeb (альтернатива, бесплатно навсегда)
1. koyeb.com → Create App
2. GitHub → выбери репозиторий
3. Build command: `pip install -r requirements.txt`
4. Run command: `python bot.py`
5. Environment: `BOT_TOKEN=твой_токен`

## Команды бота

| Команда | Действие |
|---|---|
| /start | Главное меню |
| /menu | Вернуться в меню |
| /tasks | Блокнот задач |
| /reset | Сбросить сессию |

## Структура проекта

```
glush_bot/
├── bot.py          # Основной файл бота
├── planner.py      # Промпт и вызовы AI
├── storage.py      # SQLite база данных
├── requirements.txt
├── Procfile        # Для Railway
├── runtime.txt     # Версия Python
└── .env.example    # Пример переменных окружения
```
