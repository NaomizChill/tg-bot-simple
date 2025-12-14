import os
import sqlite3

DB_PATH = os.getenv("DB_PATH", "bot.db")

def _connect():
    conn = sqlite3.connect(DB_PATH, timeout=5.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA busy_timeout = 5000")
    return conn


# db.py

def init_db():
    # Шаг 1: Определяем структуру всех таблиц
    schema = """
    CREATE TABLE IF NOT EXISTS notes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        text TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    CREATE TABLE IF NOT EXISTS models(
        id INTEGER PRIMARY KEY,
        key TEXT NOT NULL UNIQUE,
        label TEXT NOT NULL,
        active INTEGER NOT NULL DEFAULT 0 CHECK (active IN (0,1))
    );
    CREATE UNIQUE INDEX IF NOT EXISTS ux_models_single_active ON models(active) WHERE active=1;

    CREATE TABLE IF NOT EXISTS characters (
        id INTEGER PRIMARY KEY,
        name TEXT NOT NULL UNIQUE,
        prompt TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS user_character (
        telegram_user_id INTEGER PRIMARY KEY,
        character_id INTEGER NOT NULL,
        FOREIGN KEY(character_id) REFERENCES characters(id)
    );

    CREATE TABLE IF NOT EXISTS settings (
        key TEXT PRIMARY KEY,
        value TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS feature_toggles (
        name TEXT PRIMARY KEY,
        enabled INTEGER NOT NULL CHECK (enabled IN (0, 1))
    );
    """

    # ---> ИЗМЕНЕНИЕ ЗДЕСЬ <---
    # Шаг 2: Определяем данные для моделей (теперь 10 штук) в отдельной переменной
    models_data = """
    INSERT OR IGNORE INTO models(id, key, label, active) VALUES
        (1, 'anthropic/claude-3-haiku-20240307-v1:beta', 'Claude 3 Haiku (free)', 1),
        (2, 'google/gemma-7b-it:free', 'Google Gemma 7B (free)', 0),
        (3, 'mistralai/mistral-7b-instruct:free', 'Mistral 7B Instruct (free)', 0),
        (4, 'meta-llama/llama-3-8b-instruct:free', 'Llama 3 8B Instruct (free)', 0),
        (5, 'microsoft/phi-3-mini-128k-instruct:free', 'Phi-3 Mini 128k (free)', 0),
        (6, 'nousresearch/nous-hermes-2-mixtral-8x7b-dpo:free', 'Nous Hermes 2 Mixtral (free)', 0),
        (7, 'openchat/openchat-7b:free', 'OpenChat 3.5 (free)', 0),
        (8, 'gryphe/mythomax-l2-13b:free', 'MythoMax L2 13B (free)', 0),
        (9, 'huggingfaceh4/zephyr-7b-beta:free', 'Zephyr 7B Beta (free)', 0),
        (10, 'undi95/toppy-m-7b:free', 'Toppy M 7B (free)', 0);
    """

    # Шаг 3: Данные для персонажей (этот блок у вас уже есть, он не меняется)
    characters_data = """
    INSERT OR IGNORE INTO characters (id, name, prompt) VALUES
        (1, 'Йода', 'Ты отвечаешь строго в образе персонажа «Йода» из вселенной «Звёздные войны». Стиль: мудрые и загадочные речи, инверсия слов.'),
        (2, 'Дарт Вейдер', 'Ты отвечаешь строго в образе персонажа «Дарт Вейдер» из «Звёздных войн». Стиль: властный, тёмный, угрожающий.'),
        (3, 'Мистер Спок', 'Ты отвечаешь строго в образе персонажа «Спок» из «Звёздного пути». Стиль: логичный, беспристрастный, точный.'),
        (4, 'Тони Старк', 'Ты отвечаешь строго в образе персонажа «Тони Старк» из киновселенной Marvel. Стиль: остроумный, саркастичный, гениальный.'),
        (5, 'Шерлок Холмс', 'Ты отвечаешь строго в образе «Шерлока Холмса». Стиль: дедукция шаг за шагом, внимание к деталям.'),
        (6, 'Капитан Джек Воробей', 'Ты отвечаешь строго в образе «Капитана Джека Воробья». Стиль: ироничный, эксцентричный, непредсказуемый.'),
        (7, 'Гэндальф', 'Ты отвечаешь строго в образе «Гэндальфа» из «Властелина колец». Стиль: наставнический, мудрый, величественный.'),
        (8, 'Винни-Пух', 'Ты отвечаешь строго в образе «Винни-Пуха». Стиль: просто, доброжелательно, наивный, с любовью к мёду.'),
        (9, 'Голум', 'Ты отвечаешь строго в образе «Голума» из «Властелина колец». Стиль: шёпот, шипящие звуки, раздвоение личности.'),
        (10, 'Рик', 'Ты отвечаешь строго в образе «Рика» из «Рика и Морти». Стиль: сухой сарказм, цинизм, научный жаргон.'),
        (11, 'Бендер', 'Ты отвечаешь строго в образе «Бендера» из «Футурамы». Стиль: дерзкий, самоуверенный, эгоистичный.');
    """

    # Шаг 4: Выполняем все запросы
    with _connect() as conn:
        conn.executescript(schema)
        conn.executescript(models_data)  # <--- Добавляем выполнение запроса для моделей
        conn.executescript(characters_data)


def add_note(user_id: int, text: str) -> int:
    with _connect() as conn:
        cur = conn.execute(
            "INSERT INTO notes(user_id, text) VALUES (?, ?)",
            (user_id, text)
        )
    return cur.lastrowid


def list_notes(user_id: int, limit: int = 100):
    with _connect() as conn:
        cur = conn.execute(
            """SELECT id, text, created_at
            FROM notes
            WHERE user_id = ?
            ORDER BY id DESC
            LIMIT ?""",
            (user_id, limit)
        )
    return cur.fetchall()


def find_notes(user_id: int, query: str, limit: int = 50):
    """Поиск заметок по тексту"""
    with _connect() as conn:
        cur = conn.execute(
            """SELECT id, text, created_at
            FROM notes
            WHERE user_id = ? AND LOWER(text) LIKE LOWER(?)
            ORDER BY id DESC
            LIMIT ?""",
            (user_id, f"%{query}%", limit)
        )
    return cur.fetchall()


def get_note_by_id(user_id: int, note_id: int):
    """Получить одну заметку по ID"""
    with _connect() as conn:
        cur = conn.execute(
            """SELECT id, text, created_at
            FROM notes
            WHERE user_id = ? AND id = ?""",
            (user_id, note_id)
        )
    return cur.fetchone()


def update_note(user_id: int, note_id: int, text: str) -> bool:
    with _connect() as conn:
        cur = conn.execute(
            """UPDATE notes
            SET text = ?
            WHERE user_id = ? AND id = ?""",
            (text, user_id, note_id)
        )
    return cur.rowcount > 0

def list_models() -> list[dict]:
    with _connect() as conn:
        rows = conn.execute("SELECT id,key,label,active FROM models ORDER BY id").fetchall()
        return [{"id":r["id"], "key":r["key"], "label":r["label"], "active":bool(r["active"])} for r in rows]

def get_active_model() -> dict:
    with _connect() as conn:
        row = conn.execute("SELECT id,key,label FROM models WHERE active=1").fetchone()
        if row:
            return {"id":row["id"], "key":row["key"], "label":row["label"], "active":True}
        row = conn.execute("SELECT id,key,label FROM models ORDER BY id LIMIT 1").fetchone()
        if not row:
            raise RuntimeError("В реестре моделей нет записей")
        conn.execute("UPDATE models SET active=CASE WHEN id=? THEN 1 ELSE 0 END", (row["id"],))
        return {"id":row["id"], "key":row["key"], "label":row["label"], "active":True}

def set_active_model(model_id: int)-> dict:
    with _connect as conn:
        conn.execute("BEGIN IMMEDIATE")
        exists = conn.execute("SELECT 1 FROM models WHERE id=?", (model_id,)).fetchone()
        if not exists:
            conn.rollback()
            raise ValueError("Неизвестный ID модели")
        conn.execute("UPDATE  models  SET active=CASE WHEN id=? THEN 1 ELSE 0 END", (model_id,))
        conn.commit()
    return get_active_model()

def delete_note(user_id: int, note_id: int) -> bool:
    with _connect() as conn:
        cur = conn.execute(
            "DELETE FROM notes WHERE user_id = ? AND id = ?",
            (user_id, note_id)
        )
    return cur.rowcount > 0


# --- Функции для работы с персонажами ---

def list_characters() -> list[dict]:
    """Возвращает список всех персонажей."""
    with _connect() as conn:
        rows = conn.execute("SELECT id, name FROM characters ORDER BY id").fetchall()
        return [{"id": r["id"], "name": r["name"]} for r in rows]


def get_character_by_id(character_id: int) -> dict | None:
    """Возвращает персонажа по его ID."""
    with _connect() as conn:
        row = conn.execute(
            "SELECT id, name, prompt FROM characters WHERE id=?",
            (character_id,)
        ).fetchone()
        if row:
            return {"id": row["id"], "name": row["name"], "prompt": row["prompt"]}
        return None


def set_user_character(user_id: int, character_id: int) -> dict:
    """Устанавливает персонажа для пользователя (UPSERT)."""
    character = get_character_by_id(character_id)
    if not character:
        raise ValueError("Неизвестный ID персонажа")
    with _connect() as conn:
        conn.execute(
            """
            INSERT INTO user_character(telegram_user_id, character_id) VALUES(?, ?)
            ON CONFLICT(telegram_user_id) DO UPDATE SET character_id=excluded.character_id
            """,
            (user_id, character_id)
        )
    return character


def get_user_character(user_id: int) -> dict:
    """Получает персонажа для пользователя, с фолбэком на первого в списке."""
    with _connect() as conn:
        # Сначала пробуем найти выбранного персонажа
        row = conn.execute("""
            SELECT p.id, p.name, p.prompt
            FROM user_character uc
            JOIN characters p ON p.id = uc.character_id
            WHERE uc.telegram_user_id = ?
        """, (user_id,)).fetchone()
        if row:
            return {"id": row["id"], "name": row["name"], "prompt": row["prompt"]}

        # Если не найден, берем первого персонажа по умолчанию (ID=1)
        row = conn.execute("SELECT id, name, prompt FROM characters WHERE id=1").fetchone()
        if row:
            return {"id": row["id"], "name": row["name"], "prompt": row["prompt"]}

        # Если и его нет, берем вообще любого первого
        row = conn.execute("SELECT id, name, prompt FROM characters ORDER BY id LIMIT 1").fetchone()
        if not row:
            raise RuntimeError("Таблица characters пуста")
        return {"id": row["id"], "name": row["name"], "prompt": row["prompt"]}


def get_setting_or_default(key: str, default: str) -> str:
    """Возвращает динамический параметр по ключу. Если его нет - возвращает default."""
    with _connect() as conn:
        row = conn.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
        if row is None:
            return default
        return row["value"]


def get_int_setting(key: str, default: int) -> int:
    """Возвращает динамический параметр по ключу в виде int."""
    raw = get_setting_or_default(key, str(default))
    try:
        return int(raw)
    except ValueError:
        return default


def get_bool_setting(key: str, default: bool) -> bool:
    """Возвращает динамический параметр по ключу в виде bool."""
    raw = get_setting_or_default(key, "true" if default else "false")
    raw_low = raw.lower()
    if raw_low in ("1", "true", "yes", "on"):
        return True
    return False


def is_feature_enabled(name: str, default: bool) -> bool:
    """Возвращает состояние фиче-тоггла по имени (включен/выключен)."""
    with _connect() as conn:
        row = conn.execute("SELECT enabled FROM feature_toggles WHERE name = ?", (name,)).fetchone()
        if row is None:
            return default
        return bool(row["enabled"])


def set_setting(key: str, value: str) -> None:
    """Установить динамический параметр (UPSERT)."""
    with _connect() as conn:
        conn.execute(
            "INSERT INTO settings (key, value) VALUES (?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (key, value),
        )

def set_feature_toggle(name: str, enabled: bool) -> None:
    """Установить фиче-тоггл (UPSERT)."""
    with _connect() as conn:
        conn.execute(
            "INSERT INTO feature_toggles (name, enabled) VALUES (?, ?) "
            "ON CONFLICT(name) DO UPDATE SET enabled = excluded.enabled",
            (name, 1 if enabled else 0),
        )