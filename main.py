import os
from dotenv import load_dotenv
import telebot

load_dotenv()

TOKEN = os.getenv("TOKEN")
if not TOKEN:
    raise RuntimeError ("В.env нет TOKEN")

# Команда старт
bot = telebot.TeleBot(TOKEN)
@bot.message_handler(commands=['start'])
def start(message):
    bot.reply_to (message, "Привет! Я твой первый бот! Напиши /help")

# Команда help
@bot.message_handler(commands=['help'])
def help_cmd(message):
    bot.reply_to(message, "/start - начать\n/help - помощь")

# Команда about (Первое дз, обязательная часть)
@bot.message_handler(commands=['about'])
def about(message):
    bot.reply_to(message, "Это мой первый телеграм-бот, созданный в рамках практического семинара. Автор: Колонтырский Илья Русланович 1132237378")

# Команда ping (Первое дз, опциональная часть)
@bot.message_handler(commands=['ping'])
def ping(message):
    bot.reply_to(message, "Понг!")

# Логгирование (Первое дз, опциональная часть)
import logging

logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                    filename='bot.log')

if __name__=="__main__":
    bot.infinity_polling(skip_pending=True)