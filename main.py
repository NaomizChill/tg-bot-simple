import os
import logging
import requests
from telebot import TeleBot, types
from dotenv import load_dotenv

import db
from db import *
import random


# --- Заглушки для LLM (замените на вашу реализацию) ---

class OpenRouterError(Exception):
    pass


def chat_once(msgs: list[dict], model: str, temperature: float = 0.2, max_tokens: int = 400) -> tuple[str, int]:
    """
    Эта функция-заглушка имитирует обращение к LLM.
    """
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

# Настройка логирования для отслеживания действий бота
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)


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


# --- НОВАЯ КОМАНДА /max ИЗ ДОМАШНЕГО ЗАДАНИЯ ---
@bot.message_handler(commands=['max'])
def cmd_max(m: types.Message):
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
    """Суммирует числа, переданные в сообщении."""
    logging.info(f"/sum от {m.from_user.first_name} ({m.from_user.id}): {m.text}")
    nums = parse_ints_from_text(m.text)
    logging.info(f"Распознаны числа: {nums}")
    bot.reply_to(m, f"Сумма: {sum(nums)}" if nums else "Пример: /sum 2 3 10")


# --- ОБНОВЛЕННЫЕ КОМАНДЫ ДЛЯ РАБОТЫ С КЛАВИАТУРОЙ ---
@bot.message_handler(commands=['hide'])
def hide_kb(m: types.Message):
    """Прячет Reply-клавиатуру."""
    rm = types.ReplyKeyboardRemove()
    bot.send_message(m.chat.id, "Спрятал клавиатуру.", reply_markup=rm)


@bot.message_handler(commands=['show'])
def show_kb(m: types.Message):
    """Показывает Reply-клавиатуру."""
    bot.send_message(m.chat.id, "Вот клавиатура:", reply_markup=make_main_kb())


# --- ОБНОВЛЕННАЯ КОМАНДА /confirm ИЗ ДОМАШНЕГО ЗАДАНИЯ ---
@bot.message_handler(commands=['confirm'])
def confirm_cmd(m: types.Message):
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
    bot.reply_to(m, "Я умею: /start, /help, /sum, /max, /hide, /show, /confirm")


@bot.message_handler(func=lambda m: m.text == "Сумма")
def kb_sum(m: types.Message):
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
    """Отправляет погоду для Москвы по нажатию кнопки."""
    bot.send_message(m.chat.id, fetch_weather_moscow_open_meteo())

@bot.message_handler(commands=["models"])
def cmd_models(message: types.Message) -> None:
    items = list_models()
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
    arg = message.text.replace("/model" , "" , 1).strip()
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
    """Показывает активную модель и персонажа."""
    model = get_active_model()
    character = get_user_character(message.from_user.id)
    text = (
        f"**Модель:** {model['label']} [{model['key']}]\n"
        f"**Персонаж:** {character['name']}"
    )
    bot.reply_to(message, text, parse_mode="Markdown")


@bot.message_handler(commands=['ask_random'])
def cmd_ask_random(message: types.Message) -> None:
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
        bot.reply_to(message, f"{text}\n\n_({ms} мс; как: {character['name']})_", parse_mode="Markdown")
    except Exception as e:
        bot.reply_to(message, f"Ошибка: {e}")


# --- Команда из домашнего задания ---
@bot.message_handler(commands=['ask_model'])
def cmd_ask_model(message: types.Message) -> None:
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
        character = get_user_character(message.from_user.id)
        bot.reply_to(message, f"{text}\n\n_({ms} мс; модель: {model_key}; как: {character['name']})_",
                     parse_mode="Markdown")
    except Exception as e:
        bot.reply_to(message, f"Ошибка: {e}")


@bot.message_handler(func=lambda message: True)
def on_text_message(message: types.Message):
    """Обрабатывает текстовые сообщения как вопросы к LLM."""
    # Игнорируем команды
    if message.text.startswith('/'):
        # Можно добавить сообщение о неизвестной команде, если нужно
        return

    try:
        bot.send_chat_action(message.chat.id, 'typing')
        msgs = _build_messages(message.from_user.id, message.text[:600])
        model_key = get_active_model()["key"]
        text, ms = chat_once(msgs, model=model_key)
        character = get_user_character(message.from_user.id)
        bot.reply_to(message, f"{text}\n\n_({ms} мс; как: {character['name']})_", parse_mode="Markdown")
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
    ]
    bot.set_my_commands(cmds)


# --- Основной цикл ---
if __name__ == '__main__':
    logging.info("Бот запущен")
    db.init_db()  # <-- Важно! Инициализируем базу данных
    setup_bot_commands() # <-- Устанавливаем команды в меню
    bot.infinity_polling(skip_pending=True)