import os
from dotenv import load_dotenv
import telebot
from telebot import types
from typing import List
import requests

load_dotenv()

TOKEN = os.getenv("TOKEN")
if not TOKEN:
    raise RuntimeError ("В.env нет TOKEN")

# Команда старт
bot = telebot.TeleBot(TOKEN)

def parse_ints_from_text(text: str) -> List[int]:
    """Выделяет из текста целые числа: нормализует запятые, игнорирует токены-команды."""
    text = text.replace(",", " ")
    tokens = [tok for tok in text.split() if not tok.startswith("/")]
    return [int(tok) for tok in tokens if is_int_token(tok)]

def is_int_token(t: str) -> bool:
    """Проверка токена на целое число (с поддержкой знака минус)."""
    if not t:
        return False
    t = t.strip()
    if t in {"-", ""}:
        return False
    return t.lstrip("-").isdigit()

# Приветственное сообщение
@bot.message_handler(commands=['start'])
def start(message):
    bot.reply_to (message, "Привет! Я твой первый бот! Напиши /help", reply_markup=make_main_kb())

# Клавиатура
def make_main_kb() -> types.ReplyKeyboardMarkup:
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)

    kb.row("/about", "Сумма")
    kb.row("/help","/hide")
    kb.row("Погода")

    return kb

# Команда help
@bot.message_handler(commands=['help'])
def help_cmd(message):
    bot.reply_to(message, "/start - начать\n/help - помощь\n/about - информация о боте\n/ping - простая проверка работоспособности бота\n/sum - суммирование чисел\n/weather - погода в Москве")

# Команда about (Первое дз, обязательная часть)
@bot.message_handler(commands=['about'])
def about(message):
    bot.reply_to(message, "Это мой первый телеграм-бот, созданный в рамках практического семинара. Автор: Колонтырский Илья Русланович 1132237378")

# Команда ping (Первое дз, опциональная часть)
@bot.message_handler(commands=['ping'])
def ping(message):
    bot.reply_to(message, "Понг!")

# Комманад sum:
@bot.message_handler(func=lambda m: m.text == "Сумма")
def kb_sum(m):
    bot.send_message(m.chat.id, "Введи числа через пробел или запятую:")
    bot.register_next_step_handler(m, on_sum_numbers)

def on_sum_numbers(m: types.Message) -> None:
    nums = parse_ints_from_text(m.text)
    #logging.info("KB-sum next step from id=%s text=%r -> %r", m.from_user.id if m.from_user else "?", m.text, nums)
    if not nums:
        bot.reply_to(m, "Не вижу чисел. Пример: 2 3 10")
    else:
        bot.reply_to(m, f"Сумма: {sum(nums)}")

# Обработчик нажатия кнопки weather
@bot.message_handler(func=lambda m: m.text == "Погода")
def kb_weather(m):
    bot.send_message(m.chat.id, fetch_weather_moscow_open_meteo())

# Скрытие клавиатуры
@bot.message_handler(commands=['hide'])
def hide_kb(m):
    rm =types.ReplyKeyboardRemove()
    bot.send_message(m.chat.id, "Спрятал клавиатуру.", reply_markup=rm)

#Погода
def fetch_weather_moscow_open_meteo() -> str:
    url = "https://api.open-meteo.com/v1/forecast"
    params = {
        "latitude": 55.7558,
        "longitude": 37.6173,
        "current": "temperature_2m",
        "timezone": "Europe/Moscow"
    }
    try:
        r = requests.get(url, params=params, timeout=5)
        r.raise_for_status()
        t = r.json()["current"]["temperature_2m"]
        return f"Москва: сейчас {round(t)}°C"
    except Exception:
        return "Не удалось получить погоду."

@bot.message_handler(commands=['weather'])
def weather_cmd(m):
    bot.reply_to(m, fetch_weather_moscow_open_meteo())

# Inline кнопки создание
@bot.message_handler(commands=['confirm'])
def confirm_cmd(m):
    kb = types.InlineKeyboardMarkup()
    kb.add(
        types.InlineKeyboardButton("Да", callback_data="confirm:yes"),
        types.InlineKeyboardButton("Нет", callback_data="confirm:no"),
    )
    bot.send_message(m.chat.id, "Подтвердить действие?", reply_markup=kb)

# Обратоботка callback от inline кнопок
@bot.callback_query_handler(func=lambda c: c.data.startswith("confirm:"))
def on_confirm(c):
    # Извлекаем выбор пользователя
    choice = c.data.split(":", 1)[1] # "yes" иnи "no"
    # Показываем "тик" на нажатой кнопке
    bot.answer_callback_query(c.id, "Принято")
    # Убираем inline-кнопки
    bot.edit_message_reply_markup(c.message.chat.id, c.message.message_id, reply_markup=None)
    # Отправляем результат
    bot.send_message(c.message.chat.id, "Готово!" if choice == "yes" else "Отменено.")

# Логгирование (Первое дз, опциональная часть)
import logging

logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                    filename='bot.log')
@bot.message_handler(commands=['sum'])
def cmd_sum(m):
    #Логируем входящую команду
    logging.info(f"/sum от {m.from_user.first_name}{m.from_user.id}:{m.text}")

    nums = parse_ints_from_text(m.text)

    #Логируем результаты парсинга
    logging.info(f"распознаны числа: {nums}")


if __name__=="__main__":
    bot.infinity_polling(skip_pending=True)