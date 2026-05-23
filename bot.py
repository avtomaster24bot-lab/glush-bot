"""
bot.py — Глушь.io Планировщик · Telegram бот
"""
import asyncio
import logging
import os
from dotenv import load_dotenv
from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage

import storage
import planner

load_dotenv()
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

BOT_TOKEN = os.getenv("BOT_TOKEN")

# ── FSM СОСТОЯНИЯ ─────────────────────────────────

class SetupStates(StatesGroup):
    waiting_api_key = State()
    waiting_task_text = State()

# ── КЛАВИАТУРЫ ────────────────────────────────────

def kb_main() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🗓 Начать планирование", callback_data="start_planning")],
        [InlineKeyboardButton(text="📋 Блокнот задач", callback_data="notebook")],
        [InlineKeyboardButton(text="🔑 Сменить ключ", callback_data="change_key")],
    ])

def kb_notebook(tasks: list) -> InlineKeyboardMarkup:
    rows = []
    for t in tasks:
        icon = "✅" if t["done"] else "⬜"
        rows.append([
            InlineKeyboardButton(text=f"{icon} {t['text'][:30]}", callback_data=f"toggle_{t['id']}"),
            InlineKeyboardButton(text="🗑", callback_data=f"del_{t['id']}"),
        ])
    rows.append([InlineKeyboardButton(text="➕ Добавить задачу", callback_data="add_task")])
    rows.append([InlineKeyboardButton(text="🧹 Удалить выполненные", callback_data="clear_done")])
    rows.append([InlineKeyboardButton(text="◀️ Назад", callback_data="back_main")])
    return InlineKeyboardMarkup(inline_keyboard=rows)

def kb_planning() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔄 Новая сессия", callback_data="reset_session")],
        [InlineKeyboardButton(text="◀️ Главное меню", callback_data="back_main")],
    ])

def kb_provider() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🟣 Claude (Anthropic)", callback_data="prov_claude")],
        [InlineKeyboardButton(text="🟢 GPT-4o-mini (OpenAI)", callback_data="prov_openai")],
        [InlineKeyboardButton(text="🔵 Gemini Flash (Google)", callback_data="prov_gemini")],
        [InlineKeyboardButton(text="🟡 Groq Llama 3.3 (бесплатно)", callback_data="prov_groq")],
    ])

# ── ХЕЛПЕРЫ ───────────────────────────────────────

PROVIDER_NAMES = {"claude": "Claude (Anthropic)", "openai": "GPT-4o-mini (OpenAI)", "gemini": "Gemini Flash (Google)", "groq": "Groq (Llama 3.3 бесплатно)"}
PROVIDER_KEYS  = {"claude": "console.anthropic.com/settings/keys", "openai": "platform.openai.com/api-keys", "gemini": "aistudio.google.com/app/apikey", "groq": "console.groq.com"}

async def send_main_menu(message: Message, text: str = None):
    user = await storage.get_user(message.from_user.id)
    provider_info = f"🔑 Провайдер: *{PROVIDER_NAMES.get(user['provider'], '?')}*" if user else "⚠️ API ключ не настроен"
    msg = text or f"*Глушь.io — Планировщик дня*\n\n{provider_info}\n\nВыбери действие:"
    await message.answer(msg, parse_mode="Markdown", reply_markup=kb_main())

# ── КОМАНДЫ ───────────────────────────────────────

async def cmd_start(message: Message, state: FSMContext):
    await state.clear()
    user = await storage.get_user(message.from_user.id)
    if not user:
        await message.answer(
            "👋 *Глушь.io — Планировщик дня*\n\n"
            "Бот-проводник который переводит хаос задач в чёткий план.\n\n"
            "Для начала выбери AI провайдера:",
            parse_mode="Markdown",
            reply_markup=kb_provider()
        )
    else:
        await send_main_menu(message)

async def cmd_menu(message: Message, state: FSMContext):
    await state.clear()
    await send_main_menu(message)

async def cmd_reset(message: Message, state: FSMContext):
    await state.clear()
    await storage.clear_history(message.from_user.id)
    await message.answer("✅ Сессия сброшена. Начни заново через /start")

async def cmd_tasks(message: Message):
    tasks = await storage.get_tasks(message.from_user.id)
    if not tasks:
        await message.answer("📋 *Блокнот пуст*\n\nДобавь задачи кнопкой ниже:", parse_mode="Markdown", reply_markup=kb_notebook([]))
    else:
        lines = [f"{'✅' if t['done'] else '⬜'} {t['text']}" for t in tasks]
        await message.answer("📋 *Твои задачи:*\n\n" + "\n".join(lines), parse_mode="Markdown", reply_markup=kb_notebook(tasks))

# ── CALLBACKS: SETUP ──────────────────────────────

async def cb_provider(callback: CallbackQuery, state: FSMContext):
    provider = callback.data.replace("prov_", "")
    await state.update_data(provider=provider)
    key_url = PROVIDER_KEYS.get(provider, "")
    await callback.message.edit_text(
        f"*Выбран: {PROVIDER_NAMES[provider]}*\n\n"
        f"Введи API ключ:\n`{key_url}`\n\n"
        f"Ключ хранится только в базе бота и нигде не публикуется.",
        parse_mode="Markdown"
    )
    await state.set_state(SetupStates.waiting_api_key)
    await callback.answer()

async def cb_change_key(callback: CallbackQuery):
    await callback.message.edit_text("Выбери провайдера:", reply_markup=kb_provider())
    await callback.answer()

async def process_api_key(message: Message, state: FSMContext):
    key = message.text.strip()
    data = await state.get_data()
    provider = data.get("provider")

    # Автоопределение провайдера если не выбран
    if not provider:
        provider = planner.detect_provider(key)
        if not provider:
            await message.answer("❌ Не могу определить провайдера по ключу. Начни заново /start")
            return

    # Тест ключа
    await message.answer("⏳ Проверяю ключ...")
    try:
        test_history = [{"role": "user", "content": "Скажи только: ОК"}]
        await planner.call_ai(provider, key, test_history)
        await storage.save_user(message.from_user.id, provider, key)
        await state.clear()
        await message.answer(
            f"✅ *Ключ принят!*\nПровайдер: {PROVIDER_NAMES[provider]}\n\nГотов к работе.",
            parse_mode="Markdown",
            reply_markup=kb_main()
        )
    except Exception as e:
        log.error(f"Key test failed: {e}")
        await message.answer("❌ Ключ не работает. Проверь и попробуй ещё раз.", reply_markup=kb_provider())
        await state.clear()

# ── CALLBACKS: ПЛАНИРОВАНИЕ ───────────────────────

async def cb_start_planning(callback: CallbackQuery):
    uid = callback.from_user.id
    user = await storage.get_user(uid)
    if not user:
        await callback.message.edit_text("⚠️ Сначала настрой API ключ.", reply_markup=kb_provider())
        await callback.answer()
        return

    history = await storage.get_history(uid)
    station = await storage.get_station(uid)

    if history:
        # Продолжаем существующую сессию
        bar = planner.station_bar(station)
        last_bot = next((m["content"] for m in reversed(history) if m["role"] == "assistant"), None)
        text = f"{bar}\n\n*Продолжаем сессию...*\n\n{planner.clean_text(last_bot)}" if last_bot else f"{bar}\n\nПродолжаем — напиши свой ответ."
        await callback.message.edit_text(text, parse_mode="Markdown", reply_markup=kb_planning())
    else:
        # Новая сессия
        await callback.message.edit_text("⏳ Начинаю сессию...", reply_markup=None)
        try:
            starter = [{"role": "user", "content": "Начни сессию планирования дня."}]
            reply = await planner.call_ai(user["provider"], user["api_key"], starter)
            station = planner.extract_station(reply) or 1
            history = [{"role": "assistant", "content": reply}]
            await storage.save_history(uid, history, station)
            bar = planner.station_bar(station)
            await callback.message.edit_text(
                f"{bar}\n\n{planner.clean_text(reply)}",
                parse_mode="Markdown",
                reply_markup=kb_planning()
            )
        except Exception as e:
            log.error(f"Start planning error: {e}")
            await callback.message.edit_text("❌ Ошибка соединения. Проверь ключ.", reply_markup=kb_main())

    await callback.answer()

async def cb_reset_session(callback: CallbackQuery):
    await storage.clear_history(callback.from_user.id)
    await callback.message.edit_text("✅ Сессия сброшена.", reply_markup=kb_main())
    await callback.answer()

# ── ОБРАБОТКА СООБЩЕНИЙ В СЕССИИ ─────────────────

async def handle_message(message: Message, state: FSMContext):
    uid = message.from_user.id
    fsm = await state.get_state()

    # Если FSM активен — обрабатывается в FSM хендлерах
    if fsm:
        return

    user = await storage.get_user(uid)
    if not user:
        await message.answer("Введи /start чтобы начать.")
        return

    history = await storage.get_history(uid)
    if not history:
        await message.answer("Нажми 'Начать планирование' в меню.", reply_markup=kb_main())
        return

    # Добавляем сообщение пользователя
    history.append({"role": "user", "content": message.text})

    # Индикатор печатания
    await message.bot.send_chat_action(uid, "typing")

    try:
        reply = await planner.call_ai(user["provider"], user["api_key"], history)
        station = planner.extract_station(reply) or await storage.get_station(uid)
        history.append({"role": "assistant", "content": reply})
        await storage.save_history(uid, history, station)

        bar = planner.station_bar(station)
        clean = planner.clean_text(reply)
        await message.answer(f"{bar}\n\n{clean}", parse_mode="Markdown", reply_markup=kb_planning())
    except Exception as e:
        log.error(f"Message handler error: {e}")
        await message.answer("❌ Ошибка. Попробуй ещё раз или проверь ключ.")

# ── CALLBACKS: БЛОКНОТ ────────────────────────────

async def cb_notebook(callback: CallbackQuery):
    tasks = await storage.get_tasks(callback.from_user.id)
    lines = [f"{'✅' if t['done'] else '⬜'} {t['text']}" for t in tasks] if tasks else ["Список пуст"]
    await callback.message.edit_text(
        "📋 *Блокнот задач*\n\n" + "\n".join(lines),
        parse_mode="Markdown",
        reply_markup=kb_notebook(tasks)
    )
    await callback.answer()

async def cb_toggle_task(callback: CallbackQuery):
    task_id = int(callback.data.replace("toggle_", ""))
    await storage.toggle_task(task_id, callback.from_user.id)
    tasks = await storage.get_tasks(callback.from_user.id)
    lines = [f"{'✅' if t['done'] else '⬜'} {t['text']}" for t in tasks]
    await callback.message.edit_text(
        "📋 *Блокнот задач*\n\n" + "\n".join(lines),
        parse_mode="Markdown",
        reply_markup=kb_notebook(tasks)
    )
    await callback.answer()

async def cb_del_task(callback: CallbackQuery):
    task_id = int(callback.data.replace("del_", ""))
    await storage.delete_task(task_id, callback.from_user.id)
    tasks = await storage.get_tasks(callback.from_user.id)
    lines = [f"{'✅' if t['done'] else '⬜'} {t['text']}" for t in tasks] if tasks else ["Список пуст"]
    await callback.message.edit_text(
        "📋 *Блокнот задач*\n\n" + "\n".join(lines),
        parse_mode="Markdown",
        reply_markup=kb_notebook(tasks)
    )
    await callback.answer("Удалено")

async def cb_add_task(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text("✏️ Напиши текст задачи:")
    await state.set_state(SetupStates.waiting_task_text)
    await callback.answer()

async def process_task_text(message: Message, state: FSMContext):
    await storage.add_task(message.from_user.id, message.text.strip())
    await state.clear()
    tasks = await storage.get_tasks(message.from_user.id)
    lines = [f"{'✅' if t['done'] else '⬜'} {t['text']}" for t in tasks]
    await message.answer(
        "✅ Задача добавлена!\n\n📋 *Блокнот задач*\n\n" + "\n".join(lines),
        parse_mode="Markdown",
        reply_markup=kb_notebook(tasks)
    )

async def cb_clear_done(callback: CallbackQuery):
    await storage.clear_done_tasks(callback.from_user.id)
    tasks = await storage.get_tasks(callback.from_user.id)
    lines = [f"{'✅' if t['done'] else '⬜'} {t['text']}" for t in tasks] if tasks else ["Список пуст"]
    await callback.message.edit_text(
        "📋 *Блокнот задач*\n\n" + "\n".join(lines),
        parse_mode="Markdown",
        reply_markup=kb_notebook(tasks)
    )
    await callback.answer("Выполненные удалены")

async def cb_back_main(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    user = await storage.get_user(callback.from_user.id)
    provider_info = f"🔑 Провайдер: *{PROVIDER_NAMES.get(user['provider'], '?')}*" if user else "⚠️ API ключ не настроен"
    await callback.message.edit_text(
        f"*Глушь.io — Планировщик дня*\n\n{provider_info}\n\nВыбери действие:",
        parse_mode="Markdown",
        reply_markup=kb_main()
    )
    await callback.answer()

# ── ЗАПУСК ────────────────────────────────────────

async def main():
    await storage.init_db()
    bot = Bot(token=BOT_TOKEN)
    dp = Dispatcher(storage=MemoryStorage())

    # Команды
    dp.message.register(cmd_start, CommandStart())
    dp.message.register(cmd_menu,  Command("menu"))
    dp.message.register(cmd_reset, Command("reset"))
    dp.message.register(cmd_tasks, Command("tasks"))

    # FSM
    dp.message.register(process_api_key,   SetupStates.waiting_api_key)
    dp.message.register(process_task_text, SetupStates.waiting_task_text)

    # Callbacks
    dp.callback_query.register(cb_provider,       F.data.startswith("prov_"))
    dp.callback_query.register(cb_change_key,     F.data == "change_key")
    dp.callback_query.register(cb_start_planning, F.data == "start_planning")
    dp.callback_query.register(cb_reset_session,  F.data == "reset_session")
    dp.callback_query.register(cb_notebook,       F.data == "notebook")
    dp.callback_query.register(cb_toggle_task,    F.data.startswith("toggle_"))
    dp.callback_query.register(cb_del_task,       F.data.startswith("del_"))
    dp.callback_query.register(cb_add_task,       F.data == "add_task")
    dp.callback_query.register(cb_clear_done,     F.data == "clear_done")
    dp.callback_query.register(cb_back_main,      F.data == "back_main")

    # Обычные сообщения
    dp.message.register(handle_message, F.text)

    log.info("Глушь.io бот запущен")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
