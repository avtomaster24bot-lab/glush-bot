"""
storage.py — SQLite хранилище для пользователей и диалогов
"""
import aiosqlite
import json
from typing import Optional

DB_PATH = "glush.db"

async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id     INTEGER PRIMARY KEY,
                provider    TEXT,
                api_key     TEXT,
                created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS sessions (
                user_id     INTEGER PRIMARY KEY,
                history     TEXT DEFAULT '[]',
                station     INTEGER DEFAULT 0,
                updated_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS tasks (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id     INTEGER,
                text        TEXT,
                done        INTEGER DEFAULT 0,
                created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        await db.commit()

# ── ПОЛЬЗОВАТЕЛИ ──────────────────────────────────

async def save_user(user_id: int, provider: str, api_key: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            INSERT INTO users (user_id, provider, api_key)
            VALUES (?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET provider=excluded.provider, api_key=excluded.api_key
        """, (user_id, provider, api_key))
        await db.commit()

async def get_user(user_id: int) -> Optional[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT provider, api_key FROM users WHERE user_id=?", (user_id,)) as cur:
            row = await cur.fetchone()
            if row:
                return {"provider": row[0], "api_key": row[1]}
    return None

async def delete_user(user_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM users WHERE user_id=?", (user_id,))
        await db.execute("DELETE FROM sessions WHERE user_id=?", (user_id,))
        await db.execute("DELETE FROM tasks WHERE user_id=?", (user_id,))
        await db.commit()

# ── СЕССИИ ────────────────────────────────────────

async def get_history(user_id: int) -> list:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT history FROM sessions WHERE user_id=?", (user_id,)) as cur:
            row = await cur.fetchone()
            if row:
                return json.loads(row[0])
    return []

async def save_history(user_id: int, history: list, station: int = 0):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            INSERT INTO sessions (user_id, history, station)
            VALUES (?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET history=excluded.history, station=excluded.station, updated_at=CURRENT_TIMESTAMP
        """, (user_id, json.dumps(history, ensure_ascii=False), station))
        await db.commit()

async def clear_history(user_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM sessions WHERE user_id=?", (user_id,))
        await db.commit()

async def get_station(user_id: int) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT station FROM sessions WHERE user_id=?", (user_id,)) as cur:
            row = await cur.fetchone()
            return row[0] if row else 0

# ── ЗАДАЧИ ────────────────────────────────────────

async def add_task(user_id: int, text: str) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("INSERT INTO tasks (user_id, text) VALUES (?, ?)", (user_id, text))
        await db.commit()
        return cur.lastrowid

async def get_tasks(user_id: int) -> list:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT id, text, done FROM tasks WHERE user_id=? ORDER BY id", (user_id,)) as cur:
            rows = await cur.fetchall()
            return [{"id": r[0], "text": r[1], "done": bool(r[2])} for r in rows]

async def toggle_task(task_id: int, user_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE tasks SET done = 1 - done WHERE id=? AND user_id=?", (task_id, user_id))
        await db.commit()

async def delete_task(task_id: int, user_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM tasks WHERE id=? AND user_id=?", (task_id, user_id))
        await db.commit()

async def clear_done_tasks(user_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM tasks WHERE user_id=? AND done=1", (user_id,))
        await db.commit()
