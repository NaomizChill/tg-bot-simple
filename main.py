import os
import logging
import requests
from telebot import TeleBot, types
from dotenv import load_dotenv

# Загрузка переменных окружения и инициализация бота
load_dotenv()
bot = TeleBot(os.getenv('TELEGRAM_BOT_TOKEN'))

# Настройка логирования для отслеживания действий бота
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)


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
    """Обработчик команд /start и /help, отправляет приветствие и клавиатуру."""
    welcome_text = (
        "Привет! Я тестовый бот. "
        "Нажми на одну из кнопок в меню для взаимодействия."
    )
    bot.send_message(m.chat.id, welcome_text, reply_markup=make_main_kb())


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


# --- Основной цикл ---
if __name__ == '__main__':
    logging.info("Бот запущен")
    bot.infinity_polling(skip_pending=True)