import os
import logging
import requests
from telebot import TeleBot, types
from dotenv import load_dotenv
from config3 import MAX_PROMPT_CHARS_DEFAULT, SHOW_MODEL_FOOTER_DEFAULT
from db import get_int_setting, get_bool_setting
from config3 import DEBUG_SETTINGS_SHOW, CMD_MODEL_ID_ENABLED
from db import is_feature_enabled
import db
from db import *
import random
from db import set_setting, set_feature_toggle # и другие
from logging_config import setup_logging
from metrics import metric, timed
log = logging.getLogger(__name__)
from openrouter_client import chat_once, OpenRouterError
from config import DEFAULT_TEMPERATURE, DEFAULT_API_TIMEOUT, WEATHER_COMMAND_ENABLED, ASK_ENABLED # и другие

# Настраиваем логирование ДО того, как делаем что-либо еще
setup_logging()

# Создаем логгер для текущего модуля
log = logging.getLogger(__name__)

log.info("Старт приложения (инициализация бота)")

# --- Заглушки для LLM (замените на вашу реализацию) ---
class OpenRouterError(Exception):
    pass

def chat_once(...):
    # main.py -> on_text_message (и другие)
    # Получаем динамические настройки
    temperature = float(get_setting_or_default("temperature", str(DEFAULT_TEMPERATURE)))
    timeout = get_int_setting("api_timeout", DEFAULT_API_TIMEOUT)
    # Вызываем chat_once с новыми параметрами
    text, ms = chat_once(msgs, model=model_key, temperature=temperature, timeout_s=timeout)
    logging.info(f"Имитация запроса к модели {model}")
    char_name = "Персонаж"
    try:
        # Пытаемся извлечь имя персонажа из системного промпта
        char_name = msgs[0]['content'].split('«')[1].split('»')[0]
    except (IndexError, KeyError):
        pass  # Если не получилось, используем имя по умолчанию

    user_question = msgs[-1]['content']
    mock_response = f"Я {char_name}. Ваш вопрос '{user_question}' очень интересен. Это имитация ответа."

    return mock_response, 500  # (текст ответа, время ответа в мс)


# Загрузка переменных окружения и инициализация бота
load_dotenv()
bot = TeleBot(os.getenv('TOKEN'))


# --- Функции для формирования сообщений для LLM ---

def _build_messages(user_id: int, user_text: str) -> list[dict]:
    """Формирует промпт для LLM с учетом персонажа пользователя."""
    p = get_user_character(user_id)
    system = (
        f"Ты отвечаешь строго в образе персонажа «{p['name']}».\n"
        f"{p['prompt']}\n"
        "Правила:\n"
        "1) Всегда держи стиль и манеру речи выбранного персонажа.\n"
        "2) Технические ответы давай корректно, но в характерной манере.\n"
        "3) Не раскрывай, что ты 'играешь роль'.\n"
        "4) Не используй длинные дословные цитаты из фильмов/книг (>10 слов).\n"
        "5) Если стиль персонажа выражен слабо - переформулируй ответ и усили характер персонажа, сохраняя фактическую точность.\n"
    )
    return [{"role": "system", "content": system}, {"role": "user", "content": user_text}]

def _build_messages_for_character(character: dict, user_text: str) -> list[dict]:
    """Формирует промпт для LLM для СЛУЧАЙНОГО персонажа."""
    system = (
        f"Ты отвечаешь строго в образе персонажа «{character['name']}».\n"
        f"{character['prompt']}\n"
        "Правила:\n"
        "1) Всегда держи стиль и манеру речи выбранного персонажа.\n"
        "2) Технические ответы давай корректно, но в характерной манере.\n"
        "3) Не раскрывай, что ты 'играешь роль'.\n"
        "4) Не используй длинные дословные цитаты из фильмов/книг (>10 слов).\n"
        "5) Если стиль персонажа выражен слабо - переформулируй ответ и усили характер персонажа, сохраняя фактическую точность.\n"
    )
    return [{"role": "system", "content": system}, {"role": "user", "content": user_text}]

# --- Вспомогательные функции ---

def parse_ints_from_text(text: str) -> list[int]:
    """
    Извлекает целые числа из текста, поддерживая разные разделители.
    Игнорирует команды, начинающиеся с '/'.
    """
    # Заменяем запятые на пробелы для унификации
    text = text.replace(",", " ")
    # Разбиваем текст на токены и отфильтровываем команды
    tokens = [t for t in text.split() if not t.startswith("/")]

    nums = []
    for t in tokens:
        # Убираем возможный знак минуса для проверки на число
        cleaned_token = t.strip().lstrip("-")
        if cleaned_token.isdigit():  # Проверяем, является ли токен числом
            nums.append(int(t))
    return nums


def make_main_kb() -> types.ReplyKeyboardMarkup:
    """Создает основную Reply-клавиатуру с кнопками."""
    # Создаём клавиатуру с автоподгонкой размера
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    # Добавляем кнопки по рядам
    kb.row("О боте", "Сумма", "Погода (Москва)")
    # НОВЫЕ КНОПКИ ИЗ ДОМАШНЕГО ЗАДАНИЯ
    kb.row("/show", "/hide")
    kb.row("/help")
    return kb


# Словарь для кодов погоды от Open-Meteo
WMO_DESC = {
    0: "Ясно", 1: "В осн. ясно", 2: "Переменная облачность", 3: "Пасмурно",
    45: "Туман", 48: "Изморозь", 51: "Морось", 53: "Морось", 55: "Сильная морось",
    61: "Дождь", 63: "Дождь", 65: "Сильный дождь", 71: "Снег",
    80: "Ливни", 95: "Гроза"
}

@timed("weather_api_ms", logger=log)
def fetch_weather_moscow_open_meteo() -> str:
    """Запрашивает и форматирует данные о погоде для Москвы."""
    url = "https://api.open-meteo.com/v1/forecast"
    params = {
        "latitude": 55.7558, "longitude": 37.6173,
        "current": "temperature_2m,weather_code",
        "timezone": "Europe/Moscow"
    }
    try:
        r = requests.get(url, params=params, timeout=5)
        r.raise_for_status()
        data = r.json()
        cur = data["current"]
        temp = round(cur["temperature_2m"])
        code = int(cur.get("weather_code", 0))
        return f"Москва: сейчас {temp}°C, {WMO_DESC.get(code, 'нет данных о погоде')}"
    except requests.exceptions.RequestException:
        return "Не удалось получить погоду (сеть)."
    except (KeyError, TypeError, ValueError):
        return "Ответ погоды в неожидаемом формате."


# --- Обработчики команд и сообщений ---

@bot.message_handler(commands=['start', 'help'])
def start_help(m: types.Message):
    metric.counter("commands_total").inc()
    metric.counter("character_requests_total").inc()
    """Отправляет приветствие и описание новых команд."""
    welcome_text = (
        "Привет! Я бот с разными AI-персонажами.\n\n"
        "**Основные команды:**\n"
        "/models - Список AI-моделей\n"
        "/model `<ID>` - Установить активную модель\n\n"
        "/characters - Список персонажей\n"
        "/character `<ID>` - Установить активного персонажа\n\n"
        "/whoami - Текущие модель и персонаж\n"
        "/ask_random `<вопрос>` - Вопрос случайному персонажу\n"
        "/ask_model `<ID> <вопрос>` - Вопрос конкретной модели\n\n"
        "Чтобы задать вопрос вашему персонажу, **просто напишите мне сообщение**."
    )
    bot.send_message(m.chat.id, welcome_text, reply_markup=make_main_kb(), parse_mode="Markdown")


@bot.message_handler(commands=["stats"])
def handle_stats(message: types.Message) -> None:
    """Показывает все накопленные метрики."""
    log.info(f"Команда /stats от user_id={message.from_user.id}")
    stats = metric.snapshot()
    counters = stats["counters"]
    latencies = stats["latencies"]

    lines = ["**Статистика бота**\n"]
    lines.append("**Счетчики:**")
    if counters:
        for name, value in sorted(counters.items()):
            lines.append(f"- `{name}`: {value}")
    else:
        lines.append("- нет данных")

    lines.append("\n**Замеры времени (мс):**")
    if latencies:
        for name, data in sorted(latencies.items()):
            lines.append(f"- `{name}`: count={data['count']}, avg={data['avg_ms']:.0f}, "
                         f"min={data['min_ms']}, max={data['max_ms']}")
    else:
        lines.append("- нет данных")

    bot.reply_to(message, "\n".join(lines), parse_mode="Markdown")


@bot.message_handler(commands=['set_setting'])
def cmd_set_setting(message: types.Message) -> None:
    metric.counter("commands_total").inc()
    metric.counter("character_requests_total").inc()
    """Админ-команда: установить динамический параметр. Формат: /set_setting ключ=значение"""
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2 or "=" not in parts[1]:
        bot.reply_to(message, "Использование: /set_setting ключ=значение")
        return

    key, value = parts[1].split("=", 1)
    key, value = key.strip(), value.strip()

    if not key:
        bot.reply_to(message, "Ключ параметра не может быть пустым.")
        return

    set_setting(key, value)
    bot.reply_to(message, f"Параметр '{key}' установлен в '{value}'")


@bot.message_handler(commands=['set_toggle'])
def cmd_set_toggle(message: types.Message) -> None:
    metric.counter("commands_total").inc()
    metric.counter("character_requests_total").inc()
    """Админ-команда: включить/выключить фиче-тоггл. Формат: /set_toggle имя on/off"""
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


# --- НОВАЯ КОМАНДА /max ИЗ ДОМАШНЕГО ЗАДАНИЯ ---
@bot.message_handler(commands=['max'])
def cmd_max(m: types.Message):
    metric.counter("commands_total").inc()
    metric.counter("character_requests_total").inc()
    """Находит максимальное число из переданных."""
    logging.info(f"/max от {m.from_user.first_name} ({m.from_user.id}): {m.text}")
    nums = parse_ints_from_text(m.text)
    logging.info(f"Распознаны числа: {nums}")

    if not nums:
        bot.reply_to(m, "Пожалуйста, укажите числа через пробел или запятую. Пример: /max 2 3 10")
    else:
        bot.reply_to(m, f"Максимум: {max(nums)}")


@bot.message_handler(commands=['sum'])
def cmd_sum(m: types.Message):
    metric.counter("commands_total").inc()
    metric.counter("character_requests_total").inc()
    """Суммирует числа, переданные в сообщении."""
    logging.info(f"/sum от {m.from_user.first_name} ({m.from_user.id}): {m.text}")
    nums = parse_ints_from_text(m.text)
    logging.info(f"Распознаны числа: {nums}")
    bot.reply_to(m, f"Сумма: {sum(nums)}" if nums else "Пример: /sum 2 3 10")


# --- ОБНОВЛЕННЫЕ КОМАНДЫ ДЛЯ РАБОТЫ С КЛАВИАТУРОЙ ---
@bot.message_handler(commands=['hide'])
def hide_kb(m: types.Message):
    metric.counter("commands_total").inc()
    metric.counter("character_requests_total").inc()
    """Прячет Reply-клавиатуру."""
    rm = types.ReplyKeyboardRemove()
    bot.send_message(m.chat.id, "Спрятал клавиатуру.", reply_markup=rm)


@bot.message_handler(commands=['show'])
def show_kb(m: types.Message):
    metric.counter("commands_total").inc()
    metric.counter("character_requests_total").inc()
    """Показывает Reply-клавиатуру."""
    bot.send_message(m.chat.id, "Вот клавиатура:", reply_markup=make_main_kb())


# --- ОБНОВЛЕННАЯ КОМАНДА /confirm ИЗ ДОМАШНЕГО ЗАДАНИЯ ---
@bot.message_handler(commands=['confirm'])
def confirm_cmd(m: types.Message):
    metric.counter("commands_total").inc()
    metric.counter("character_requests_total").inc()
    """Отправляет Inline-кнопки для подтверждения."""
    kb = types.InlineKeyboardMarkup()
    kb.add(
        types.InlineKeyboardButton("Да", callback_data="save:yes"),
        types.InlineKeyboardButton("Нет", callback_data="save:no"),
        # Новая кнопка "Отмена"
        types.InlineKeyboardButton("Отмена", callback_data="save:later"),
    )
    # Обновленный текст сообщения
    bot.send_message(m.chat.id, "Сохранить изменения?", reply_markup=kb)


# --- ОБНОВЛЕННЫЙ ОБРАБОТЧИК ДЛЯ INLINE-КНОПОК ---
@bot.callback_query_handler(func=lambda c: c.data.startswith("save:"))
def on_confirm(c: types.CallbackQuery):
    """Обрабатывает нажатия на Inline-кнопки."""
    # Извлекаем выбор пользователя
    choice = c.data.split(":", 1)[1]

    # Отправляем "часики" на нажатой кнопке
    bot.answer_callback_query(c.id, "Принято!")

    # Убираем inline-кнопки из сообщения
    bot.edit_message_reply_markup(c.message.chat.id, c.message.message_id, reply_markup=None)

    # Отправляем результат в зависимости от выбора
    if choice == "yes":
        bot.send_message(c.message.chat.id, "Готово!")
    elif choice == "no":
        bot.send_message(c.message.chat.id, "Отменено.")
    elif choice == "later":
        bot.send_message(c.message.chat.id, "Отложено.")


# --- Обработчики кнопок Reply-клавиатуры ---
@bot.message_handler(func=lambda m: m.text == "О боте")
def kb_about(m: types.Message):
    metric.counter("commands_total").inc()
    metric.counter("character_requests_total").inc()
    bot.reply_to(m, "Я умею: /start, /help, /sum, /max, /hide, /show, /confirm")


@bot.message_handler(func=lambda m: m.text == "Сумма")
def kb_sum(m: types.Message):
    metric.counter("commands_total").inc()
    metric.counter("character_requests_total").inc()
    """Запускает сценарий суммирования чисел."""
    bot.send_message(m.chat.id, "Введите числа через пробел или запятую:")
    bot.register_next_step_handler(m, on_sum_numbers)


def on_sum_numbers(m: types.Message):
    """Получает числа и считает сумму."""
    nums = parse_ints_from_text(m.text)
    if not nums:
        bot.reply_to(m, "Не вижу чисел. Пример: 2 3 10 или 2, 3, -5")
    else:
        bot.reply_to(m, f"Сумма: {sum(nums)}")


@bot.message_handler(func=lambda m: m.text == "Погода (Москва)")
def kb_weather_moscow(m: types.Message):
    if not is_feature_enabled("weather_command_enabled", WEATHER_COMMAND_ENABLED):
        bot.reply_to(message, "Команда погоды временно отключена.")
        return
    metric.counter("commands_total").inc()
    metric.counter("character_requests_total").inc()
    """Отправляет погоду для Москвы по нажатию кнопки."""
    bot.send_message(m.chat.id, fetch_weather_moscow_open_meteo())

@bot.message_handler(commands=["models"])
def cmd_models(message: types.Message) -> None:
    metric.counter("commands_total").inc()
    metric.counter("character_requests_total").inc()
    items = list_models()
    if not is_feature_enabled("model_commands", CMD_MODEL_ID_ENABLED):
        bot.reply_to(message, "Команда временно отключена.")
        return
    if not items:
        bot.reply_to(message, "Список моделей пуст.")
        return
    lines = ["Доступные модели:"]
    for m in items:
        star = "★" if m["active"] else " "
        lines.append(f"{star} {m['id']}. {m['label']}  [{m['key']}]")
    lines.append("\nАктивировать: /model <ID>")
    bot.reply_to(message, "\n".join(lines))

@bot.message_handler(commands=['model'])
def cmd_model(message: types.Message)->None:
    metric.counter("commands_total").inc()
    metric.counter("character_requests_total").inc()
    arg = message.text.replace("/model" , "" , 1).strip()
    if not is_feature_enabled("model_commands", CMD_MODEL_ID_ENABLED):
        bot.reply_to(message, "Команда временно отключена.")
        return
    if not arg:
        active = get_active_model()
        bot.reply_to(message , f"Текущая активная моедль: {active['label']} [{active['key']}]\n(сменить: /model <ID> или /models)")
        return
    if not arg.isdigit():
        bot.reply_to(message, "Использование: /model <ID из /models>")
        return
    try:
        active = set_active_model(int(arg))
        bot.reply_to(message, f"Активная модель переключена: {active['label']} [{active["key"]}]")
    except ValueError:
        bot.reply_to(message, "Неизвестный ID модели. Сначала /models.")


@bot.message_handler(commands=['start', 'help'])
def cmd_start(message: types.Message) -> None:
    metric.counter("commands_total").inc()
    metric.counter("character_requests_total").inc()
    """

    """
    text = (
        "привет! это заметочник на SQLite. \n\n"
        "команда: \n"
        "/note_add <текст>\n"
        "/note_list [N]\n"
        "/note_find <подстрока>\n"
        "/note_edit <id> <текст>\n"
        "/note_del <id>\n"
        "/note_count\n"
        "/note_export\n"
        "note_stats [days]\n"
        "/models\n"
        "/model <id>\n"
    )


# --- Новые команды для работы с персонажами и моделями ---

@bot.message_handler(commands=['characters'])
def cmd_characters(message: types.Message) -> None:
    metric.counter("commands_total").inc()
    metric.counter("character_requests_total").inc()
    """Показывает список персонажей."""
    items = list_characters()
    if not items:
        bot.reply_to(message, "Каталог персонажей пуст.")
        return

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
    """Устанавливает активного персонажа."""
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
    metric.counter("character_requests_total").inc()
    """Показывает активную модель и персонажа."""
    model = get_active_model()
    character = get_user_character(message.from_user.id)
    text = (
        f"**Модель:** {model['label']} [{model['key']}]\n"
        f"**Персонаж:** {character['name']}"
    )
    bot.reply_to(message, text, parse_mode="Markdown")


@bot.message_handler(commands=["debug_settings"])
def cmd_debug_settings(message: types.Message):
    metric.counter("commands_total").inc()
    metric.counter("character_requests_total").inc()
    """Показывает настройки, если фиче-тоггл debug_settings включен."""
    # ---> Эта команда полностью управляется фиче-тогглом <---
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


@bot.message_handler(commands=['ask_random'])
def cmd_ask_random(message: types.Message) -> None:
    metric.counter("commands_total").inc()
    metric.counter("character_requests_total").inc()
    """Задает вопрос случайному персонажу."""
    q = message.text.replace("/ask_random", "", 1).strip()
    if not q:
        bot.reply_to(message, "Использование: /ask_random <вопрос>")
        return

    try:
        chosen = random.choice(list_characters())
        character = get_character_by_id(chosen["id"])
        bot.send_chat_action(message.chat.id, 'typing')
        msgs = _build_messages_for_character(character, q[:600])
        model_key = get_active_model()["key"]
        text, ms = chat_once(msgs, model=model_key)
        # main.py -> on_text_message (и другие)
        # Получаем динамические настройки
        temperature = float(get_setting_or_default("temperature", str(DEFAULT_TEMPERATURE)))
        timeout = get_int_setting("api_timeout", DEFAULT_API_TIMEOUT)
        # Вызываем chat_once с новыми параметрами
        text, ms = chat_once(msgs, model=model_key, temperature=temperature, timeout_s=timeout)
        bot.reply_to(message, f"{text}\n\n_({ms} мс; как: {character['name']})_", parse_mode="Markdown")
    except Exception as e:
        bot.reply_to(message, f"Ошибка: {e}")


# --- Команда из домашнего задания ---
@bot.message_handler(commands=['ask_model'])
def cmd_ask_model(message: types.Message) -> None:
    metric.counter("commands_total").inc()
    metric.counter("character_requests_total").inc()
    """Задает вопрос конкретной модели без смены активной."""
    parts = message.text.split(maxsplit=2)
    if len(parts) < 3:
        bot.reply_to(message, "Формат: /ask_model <ID модели> <вопрос>")
        return

    model_id_str, q = parts[1], parts[2]
    if not model_id_str.isdigit():
        bot.reply_to(message, "ID модели должен быть числом. Список: /models")
        return

    try:
        all_models = {m['id']: m for m in list_models()}
        if int(model_id_str) not in all_models:
            bot.reply_to(message, "Неизвестный ID модели. Сначала /models.")
            return

        model_key = all_models[int(model_id_str)]['key']
        bot.send_chat_action(message.chat.id, 'typing')
        msgs = _build_messages(message.from_user.id, q[:600])
        text, ms = chat_once(msgs, model=model_key)
        # main.py -> on_text_message (и другие)
        # Получаем динамические настройки
        temperature = float(get_setting_or_default("temperature", str(DEFAULT_TEMPERATURE)))
        timeout = get_int_setting("api_timeout", DEFAULT_API_TIMEOUT)
        # Вызываем chat_once с новыми параметрами
        text, ms = chat_once(msgs, model=model_key, temperature=temperature, timeout_s=timeout)
        character = get_user_character(message.from_user.id)
        bot.reply_to(message, f"{text}\n\n_({ms} мс; модель: {model_key}; как: {character['name']})_",
                     parse_mode="Markdown")
    except Exception as e:
        bot.reply_to(message, f"Ошибка: {e}")


@bot.message_handler(func=lambda message: True)
def on_text_message(message: types.Message):
    if not is_feature_enabled("ask_enabled", ASK_ENABLED):
        # Можно ничего не отвечать или написать "Функция временно отключена"
        return
    metric.counter("commands_total").inc()
    metric.counter("character_requests_total").inc()
    """Обрабатывает текстовые сообщения как вопросы к LLM."""
    if message.text.startswith('/'):
        bot.reply_to(message, "Неизвестная команда. Используйте /help для списка команд.")
        return

    max_len = get_int_setting("max_prompt_chars", MAX_PROMPT_CHARS_DEFAULT)
    show_footer = get_bool_setting("show_model_footer", SHOW_MODEL_FOOTER_DEFAULT)

    q = message.text.strip()[:max_len]

    try:
        bot.send_chat_action(message.chat.id, 'typing')
        msgs = _build_messages(message.from_user.id, q)
        model_key = get_active_model()["key"]
        text, ms = chat_once(msgs, model=model_key)
        # main.py -> on_text_message (и другие)
        # Получаем динамические настройки
        temperature = float(get_setting_or_default("temperature", str(DEFAULT_TEMPERATURE)))
        timeout = get_int_setting("api_timeout", DEFAULT_API_TIMEOUT)
        # Вызываем chat_once с новыми параметрами
        text, ms = chat_once(msgs, model=model_key, temperature=temperature, timeout_s=timeout)
        character = get_user_character(message.from_user.id)

        add_info = f"\n\n_({ms} мс; модель: {model_key}; как: {character['name']})_" if show_footer else ""
        bot.reply_to(message, f"{text}{add_info}", parse_mode="Markdown")

    except Exception as e:
        bot.reply_to(message, f"Произошла ошибка: {e}")



# --- Меню команд в клиенте ---
def setup_bot_commands():
    """Регистрирует команды в меню клиента Telegram (удобно для новичков)."""
    cmds = [
        types.BotCommand("start", "Помощь и описание"),
        types.BotCommand("models", "Список AI моделей"),
        types.BotCommand("model", "Сменить AI модель"),
        types.BotCommand("characters", "Список персонажей"),
        types.BotCommand("character", "Сменить персонажа"),
        types.BotCommand("whoami", "Текущие настройки"),
        types.BotCommand("ask_random", "Вопрос случайному персонажу"),
        types.BotCommand("ask_model", "Вопрос конкретной модели"),
        types.BotCommand("stats", "Мониторинг бота"),
    ]
    if is_feature_enabled("debug_settings", DEBUG_SETTINGS_SHOW):
        cmds.append(types.BotCommand("debug_settings", "Показать настройки бота"))

    bot.set_my_commands(cmds)



# --- Основной цикл ---
if __name__ == '__main__':
    log.info("Настройка меню команд...")
    try:
        # Инициализируем базу данных перед настройкой команд
        init_db()
        # Настраиваем меню с учетом фиче-тогглов
        setup_bot_commands()
        log.info("Меню команд успешно настроено.")
    except Exception as e:
        # Используем наш новый логгер для записи ошибок
        log.error(f"Не удалось выполнить предстартовую настройку: {e}", exc_info=True)

    log.info("Запуск long polling...")
    # Эта команда заставляет бота работать бесконечно
    bot.infinity_polling(skip_pending=True)