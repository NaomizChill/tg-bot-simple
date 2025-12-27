# =================================================================================
# --------------------------------- ИМПОРТЫ ---------------------------------------
# =================================================================================

# --- Стандартные библиотеки ---
import os
import logging
import random

# --- Сторонние библиотеки ---
import requests
from telebot import TeleBot, types
from dotenv import load_dotenv
from duckduckgo_search import DDGS

# --- Локальные модули ---
# Конфигурация
from config3 import (
    MAX_PROMPT_CHARS_DEFAULT, SHOW_MODEL_FOOTER_DEFAULT,
    DEBUG_SETTINGS_SHOW, CMD_MODEL_ID_ENABLED,
    DEFAULT_TEMPERATURE, DEFAULT_API_TIMEOUT,
    WEATHER_COMMAND_ENABLED, ASK_ENABLED
)
# База данных
from db import (
    init_db,
    get_active_model, set_active_model,
    get_user_character, set_user_character, list_characters, get_character_by_id, list_models,
    get_int_setting, get_bool_setting, get_setting_or_default,
    set_setting, set_feature_toggle, is_feature_enabled,
    add_to_chat_history, get_chat_history, clear_chat_history,
    add_note  # Для команды summarize_and_save
)
# Клиент для AI
from openrouter_client import chat_once, OpenRouterError
# Наши кастомные модули
from logging_config import setup_logging
from metrics import metric, timed

# =================================================================================
# ------------------------------ ИНИЦИАЛИЗАЦИЯ ------------------------------------
# =================================================================================

# 1. Настраиваем логирование в самом начале
setup_logging()
log = logging.getLogger(__name__)

# 2. Загружаем переменные окружения из .env файла
load_dotenv()

# 3. Инициализируем бота
bot = TeleBot(os.getenv('TOKEN'))
log.info("Старт приложения (инициализация бота)")


# =================================================================================
# -------------------------- ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ------------------------------
# =================================================================================

def make_main_kb() -> types.ReplyKeyboardMarkup:
    """Создает основную Reply-клавиатуру."""
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.row("Погода (Москва)")
    return kb


@timed("build_messages_ms", logger=log)
def _build_messages(user_id: int, user_text: str) -> list[dict]:
    """Формирует промпт для LLM с учетом персонажа и ИСТОРИИ ДИАЛОГА."""
    p = get_user_character(user_id)
    history = get_chat_history(user_id)
    system_prompt = (
        f"Ты отвечаешь строго в образе персонажа «{p['name']}».\n"
        f"{p['prompt']}\n"
        "Правила:\n"
        "1) Всегда держи стиль и манеру речи.\n"
        "2) Не раскрывай, что ты 'играешь роль'.\n"
    )
    messages = [{"role": "system", "content": system_prompt}]
    messages.extend(history)
    messages.append({"role": "user", "content": user_text})
    return messages


def _build_messages_for_character(character: dict, user_text: str) -> list[dict]:
    """Формирует промпт для LLM для СЛУЧАЙНОГО персонажа (без истории)."""
    system = (
        f"Ты отвечаешь строго в образе персонажа: {character['name']}.\n"
        f"{character['prompt']}\n"
    )
    return [{"role": "system", "content": system}, {"role": "user", "content": user_text}]


# =================================================================================
# --------------------------- ОБРАБОТЧИКИ КОМАНД (HANDLERS) -------------------------
# =================================================================================

@bot.message_handler(commands=['start', 'help'])
def start_help(m: types.Message):
    """Отправляет приветствие и описание всех команд."""
    metric.counter("commands_total").inc()
    metric.counter("start_requests_total").inc()
    welcome_text = (
        "Привет! Я твой умный ассистент с разными AI-персонажами.\n\n"
        "**Основные возможности:**\n"
        "- Я помню наш диалог. Чтобы начать заново, используй /clear.\n"
        "- Чтобы задать вопрос с доступом в интернет, используй /ask_web <вопрос>.\n"
        "- Чтобы сохранить итоги нашего разговора, используй /summarize_and_save.\n\n"
        "**Настройка:**\n"
        "/models - Показать/сменить AI-модель\n"
        "/characters - Показать/сменить персонажа\n\n"
        "Чтобы задать обычный вопрос, просто напиши мне сообщение."
    )
    bot.send_message(m.chat.id, welcome_text, parse_mode="Markdown")


# --- Команды финального проекта ---

@bot.message_handler(commands=['clear'])
def cmd_clear(message: types.Message):
    """Очищает историю диалога."""
    metric.counter("commands_total").inc()
    metric.counter("clear_requests_total").inc()
    user_id = message.from_user.id
    clear_chat_history(user_id)
    bot.reply_to(message, "История вашего диалога очищена.")


@bot.message_handler(commands=['ask_web'])
def cmd_ask_web(message: types.Message):
    """Задает вопрос AI с поиском актуальной информации в интернете."""
    metric.counter("commands_total").inc()
    metric.counter("ask_web_requests_total").inc()

    user_id = message.from_user.id
    query = message.text.replace("/ask_web", "", 1).strip()
    if not query:
        bot.reply_to(message, "Использование: /ask_web <ваш вопрос>")
        return

    try:
        bot.send_chat_action(message.chat.id, 'typing')

        # ---> ФИНАЛЬНОЕ ИЗМЕНЕНИЕ ЗДЕСЬ <---
        # Мы явно просим использовать бэкенд DuckDuckGo, а не Bing
        with DDGS() as ddgs:
            results = list(ddgs.text(query, region='wt-wt', safesearch='off', max_results=3))

        if not results:
            bot.reply_to(message, "Не удалось найти информацию по вашему запросу в интернете.")
            return

        context = " ".join([r['body'] for r in results])
        context = context[:3000]

        p = get_user_character(user_id)
        final_prompt = (
            f"Ты отвечаешь в образе персонажа «{p['name']}» ({p['prompt']}).\n"
            f"Основываясь на следующей информации из интернета: '{context}', "
            f"ответь на вопрос пользователя: '{query}'"
        )

        msgs = [{"role": "user", "content": final_prompt}]
        model_key = get_active_model()["key"]
        response_text, ms = chat_once(msgs, model=model_key)

        bot.reply_to(message, response_text)

    except Exception as e:
        log.error(f"Ошибка в /ask_web: {e}", exc_info=True)
        bot.reply_to(message, f"Произошла ошибка при поиске в интернете: {e}")


@bot.message_handler(commands=['summarize_and_save'])
def cmd_summarize_and_save(message: types.Message):
    """Делает краткое резюме диалога и сохраняет его в заметки."""
    metric.counter("commands_total").inc()
    metric.counter("summarize_requests_total").inc()
    user_id = message.from_user.id
    history = get_chat_history(user_id)
    if not history:
        bot.reply_to(message, "История диалога пуста, нечего сохранять.")
        return
    try:
        bot.send_chat_action(message.chat.id, 'typing')
        dialog_text = "\n".join([f"{h['role']}: {h['message']}" for h in history])
        prompt = (
            "Сделай краткое, но емкое резюме следующего диалога. "
            "Выдели ключевые темы и выводы. Ответ должен быть только самим текстом заметки.\n\n"
            f"ДИАЛОГ:\n{dialog_text}"
        )
        msgs = [{"role": "user", "content": prompt}]
        model_key = get_active_model()["key"]
        summary_text, ms = chat_once(msgs, model=model_key, temperature=0.2)
        note_id = add_note(user_id, summary_text)
        bot.reply_to(message, f"Готово! Сохранил резюме нашего разговора в заметку #{note_id}.")
    except Exception as e:
        log.error(f"Ошибка в /summarize_and_save: {e}", exc_info=True)
        bot.reply_to(message, f"Произошла ошибка при создании резюме: {e}")


# --- Команды настройки и управления ---

@bot.message_handler(commands=['models'])
def cmd_models(message: types.Message) -> None:
    metric.counter("commands_total").inc()
    metric.counter("models_requests_total").inc()
    if not is_feature_enabled("model_commands", CMD_MODEL_ID_ENABLED):
        bot.reply_to(message, "Команда временно отключена.")
        return
    items = list_models()
    lines = ["**Доступные модели:**"]
    for m in items:
        star = "★" if m["active"] else " "
        lines.append(f"{star} `{m['id']}`. {m['label']}")
    lines.append("\n**Активировать:** /model <ID>")
    bot.reply_to(message, "\n".join(lines), parse_mode="Markdown")


@bot.message_handler(commands=['model'])
def cmd_model(message: types.Message) -> None:
    metric.counter("commands_total").inc()
    metric.counter("model_requests_total").inc()
    if not is_feature_enabled("model_commands", CMD_MODEL_ID_ENABLED):
        bot.reply_to(message, "Команды выбора модели временно отключены.")
        return
    arg = message.text.replace("/model", "", 1).strip()
    if not arg:
        try:
            active = get_active_model()
            bot.reply_to(message,
                         f"Текущая активная модель: {active['label']} [{active['key']}]\n(сменить: /model <ID>)")
        except Exception as e:
            log.error(f"Ошибка в /model: {e}", exc_info=True)
            bot.reply_to(message, f"Не удалось получить активную модель: {e}")
        return
    if not arg.isdigit():
        bot.reply_to(message, "Использование: /model <ID из /models>")
        return
    try:
        active = set_active_model(int(arg))
        bot.reply_to(message, f"Активная модель переключена на: {active['label']}")
    except ValueError as e:
        bot.reply_to(message, str(e))
    except Exception as e:
        log.error(f"Ошибка в /model: {e}", exc_info=True)
        bot.reply_to(message, f"Произошла непредвиденная ошибка: {e}")


@bot.message_handler(commands=['characters'])
def cmd_characters(message: types.Message) -> None:
    metric.counter("commands_total").inc()
    metric.counter("characters_requests_total").inc()
    items = list_characters()
    current_char_id = get_user_character(message.from_user.id)["id"]
    lines = ["**Доступные персонажи:**"]
    for p in items:
        star = "★" if p["id"] == current_char_id else " "
        lines.append(f"{star} `{p['id']}`. {p['name']}")
    lines.append("\n**Выбор:** /character <ID>")
    bot.reply_to(message, "\n".join(lines), parse_mode="Markdown")


@bot.message_handler(commands=['character'])
def cmd_character(message: types.Message) -> None:
    metric.counter("commands_total").inc()
    metric.counter("character_requests_total").inc()
    arg = message.text.replace("/character", "", 1).strip()
    if not arg:
        p = get_user_character(message.from_user.id)
        bot.reply_to(message, f"Текущий персонаж: *{p['name']}*\n(сменить: /character <ID>)", parse_mode="Markdown")
        return
    if not arg.isdigit():
        bot.reply_to(message, "Использование: /character <ID из /characters>")
        return
    try:
        p = set_user_character(message.from_user.id, int(arg))
        bot.reply_to(message, f"Персонаж установлен: *{p['name']}*", parse_mode="Markdown")
    except ValueError:
        bot.reply_to(message, "Неизвестный ID персонажа. Сначала /characters.")


@bot.message_handler(commands=['whoami'])
def cmd_whoami(message: types.Message) -> None:
    metric.counter("commands_total").inc()
    metric.counter("whoami_requests_total").inc()
    model = get_active_model()
    character = get_user_character(message.from_user.id)
    text = (f"**Модель:** {model['label']}\n**Персонаж:** {character['name']}")
    bot.reply_to(message, text, parse_mode="Markdown")


# --- Админ-команды ---

@bot.message_handler(commands=['set_setting'])
def cmd_set_setting(message: types.Message) -> None:
    metric.counter("commands_total").inc()
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2 or "=" not in parts[1]:
        bot.reply_to(message, "Использование: /set_setting ключ=значение")
        return
    key, value = parts[1].split("=", 1)
    key, value = key.strip(), value.strip()
    if not key:
        bot.reply_to(message, "Ключ не может быть пустым.")
        return
    set_setting(key, value)
    bot.reply_to(message, f"Параметр '{key}' установлен в '{value}'")


@bot.message_handler(commands=['set_toggle'])
def cmd_set_toggle(message: types.Message) -> None:
    metric.counter("commands_total").inc()
    parts = message.text.split(maxsplit=2)
    if len(parts) < 3:
        bot.reply_to(message, "Использование: /set_toggle <имя> on|off")
        return
    name = parts[1].strip()
    state = parts[2].strip().lower()
    if state not in ("on", "off"):
        bot.reply_to(message, "Второй аргумент должен быть 'on' или 'off'.")
        return
    enabled = state == "on"
    set_feature_toggle(name, enabled)
    bot.reply_to(message, f"Feature-toggle '{name}' = {enabled}")


@bot.message_handler(commands=["debug_settings"])
def cmd_debug_settings(message: types.Message):
    metric.counter("commands_total").inc()
    if not is_feature_enabled("debug_settings", DEBUG_SETTINGS_SHOW):
        bot.reply_to(message, "Эта команда отключена.")
        return
    max_len = get_int_setting("max_prompt_chars", MAX_PROMPT_CHARS_DEFAULT)
    show_footer = get_bool_setting("show_model_footer", SHOW_MODEL_FOOTER_DEFAULT)
    model_cmds = is_feature_enabled("model_commands", CMD_MODEL_ID_ENABLED)
    text = (
        f"max_prompt_chars = {max_len}\n"
        f"show_model_footer = {show_footer}\n"
        f"feature: model_commands = {model_cmds}\n"
    )
    bot.reply_to(message, text)


# --- Обработчик кнопок (для погоды) ---

@bot.message_handler(func=lambda m: m.text == "Погода (Москва)")
def kb_weather_moscow(m: types.Message):
    metric.counter("commands_total").inc()
    metric.counter("weather_requests_total").inc()
    if not is_feature_enabled("weather_command_enabled", WEATHER_COMMAND_ENABLED):
        bot.reply_to(m, "Команда погоды временно отключена.")
        return
    # ... код для получения погоды ...
    bot.send_message(m.chat.id, "Функция погоды временно отключена для отладки.")


# =================================================================================
# -------------- ГЛАВНЫЙ ОБРАБОТЧИК ТЕКСТА (ДОЛЖЕН БЫТЬ ПОСЛЕДНИМ!) ---------------
# =================================================================================

@bot.message_handler(func=lambda message: True)
def on_text_message(message: types.Message):
    """Обрабатывает ЛЮБЫЕ текстовые сообщения как вопросы к LLM."""
    user_id = message.from_user.id
    q = message.text.strip()

    # Игнорируем команды, чтобы они не попадали в AI
    if q.startswith('/'):
        # Можно раскомментировать, если нужно сообщать о неизвестных командах
        # bot.reply_to(message, "Неизвестная команда. Используйте /help.")
        return

    if not is_feature_enabled("ask_enabled", ASK_ENABLED):
        return

    max_len = get_int_setting("max_prompt_chars", MAX_PROMPT_CHARS_DEFAULT)
    q = q[:max_len]

    try:
        bot.send_chat_action(message.chat.id, 'typing')
        msgs = _build_messages(user_id, q)
        model_key = get_active_model()["key"]
        temperature = float(get_setting_or_default("temperature", str(DEFAULT_TEMPERATURE)))
        timeout = get_int_setting("api_timeout", DEFAULT_API_TIMEOUT)
        response_text, ms = chat_once(msgs, model=model_key, temperature=temperature, timeout_s=timeout)

        add_to_chat_history(user_id, "user", q)
        add_to_chat_history(user_id, "assistant", response_text)

        show_footer = get_bool_setting("show_model_footer", SHOW_MODEL_FOOTER_DEFAULT)
        character = get_user_character(user_id)
        add_info = f"\n\n({ms} мс; модель: {model_key}; как: {character['name']})" if show_footer else ""

        bot.reply_to(message, f"{response_text}{add_info}", parse_mode="Markdown")

    except Exception as e:
        log.error(f"Ошибка в on_text_message: {e}", exc_info=True)
        bot.reply_to(message, f"Произошла ошибка: {e}")


# =================================================================================
# ----------------------------- НАСТРОЙКА И ЗАПУСК --------------------------------
# =================================================================================

def setup_bot_commands():
    """Регистрирует команды в меню клиента Telegram."""
    cmds = [
        types.BotCommand("start", "Помощь и описание"),
        types.BotCommand("ask_web", "Вопрос с поиском в интернете"),
        types.BotCommand("clear", "Очистить историю диалога"),
        types.BotCommand("summarize_and_save", "Сохранить итоги диалога"),
        types.BotCommand("models", "Список AI моделей"),
        types.BotCommand("model", "Сменить AI модель"),
        types.BotCommand("characters", "Список персонажей"),
        types.BotCommand("character", "Сменить персонажа"),
        types.BotCommand("whoami", "Текущие настройки"),
        types.BotCommand("stats", "Мониторинг бота"),
    ]
    if is_feature_enabled("debug_settings", DEBUG_SETTINGS_SHOW):
        cmds.append(types.BotCommand("debug_settings", "Отладка настроек"))
    bot.set_my_commands(cmds)


if __name__ == '__main__':
    log.info("Настройка меню команд...")
    try:
        init_db()
        setup_bot_commands()
        log.info("Меню команд успешно настроено.")
    except Exception as e:
        log.error(f"Не удалось выполнить предстартовую настройку: {e}", exc_info=True)

    log.info("Запуск long polling...")
    bot.infinity_polling(skip_pending=True)