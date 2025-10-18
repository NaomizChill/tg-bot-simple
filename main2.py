import os
from dotenv import load_dotenv
import telebot
import time
import db
from datetime import datetime

# Загрузка переменных окружения
load_dotenv()
TOKEN = os.getenv("TOKEN")
if not TOKEN:
    raise RuntimeError("В .env файле нет TOKEN")

bot = telebot.TeleBot(TOKEN)

# Инициализация базы данных при запуске
db.init_db()


@bot.message_handler(commands=['start'])
def start(message):
    welcome_text = f"""
👋 Привет, {message.from_user.first_name}!

Я бот для заметок. Я помогу тебе сохранять важную информацию.
Все твои заметки хранятся в базе данных и доступны только тебе.

Используй /help для списка команд.
"""
    bot.reply_to(message, welcome_text)


@bot.message_handler(commands=['help'])
def help_cmd(message):
    help_text = """
📝 **Доступные команды:**

/note\_add `<текст>` - Добавить заметку
/note\_list - Показать все заметки
/note\_find `<запрос>` - Найти заметку
/note\_show `<id>` - Показать полную заметку
/note\_edit `<id>` `<новый текст>` - Изменить заметку
/note\_del `<id>` - Удалить заметку

💡 **Примеры:**
/note\_add Купить молоко
/note\_find молоко
/note\_edit 5 Купить молоко и хлеб
/note\_del 5
"""
    bot.reply_to(message, help_text, parse_mode='Markdown')


@bot.message_handler(commands=['note_add'])
def note_add(message):
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2 or not parts[1].strip():
        bot.reply_to(message, "❌ Формат: /note_add <текст заметки>")
        return

    text = parts[1].strip()

    try:
        note_id = db.add_note(message.from_user.id, text)
        bot.reply_to(message, f"✅ Заметка #{note_id} добавлена:\n\n{text}")
    except Exception as e:
        bot.reply_to(message, f"❌ Ошибка при добавлении заметки: {str(e)}")


@bot.message_handler(commands=['note_list'])
def note_list(message):
    try:
        notes = db.list_notes(message.from_user.id)

        if not notes:
            bot.reply_to(message, "📭 У вас пока нет заметок.\nИспользуйте /note_add <текст> для добавления.")
            return

        response = f"📋 **Ваши заметки** (последние {len(notes)}):\n\n"

        for note in notes:
            # Форматируем дату
            created_at = datetime.fromisoformat(note['created_at']).strftime('%d.%m.%Y %H:%M')
            # Ограничиваем длину текста для списка
            text = note['text']
            display_text = text[:50] + "..." if len(text) > 50 else text
            response += f"#{note['id']} _{created_at}_\n{display_text}\n\n"

        # Telegram имеет лимит на длину сообщения
        if len(response) > 4000:
            response = response[:3900] + "\n\n... _список обрезан_"

        bot.reply_to(message, response, parse_mode='Markdown')
    except Exception as e:
        bot.reply_to(message, f"❌ Ошибка при получении заметок: {str(e)}")


@bot.message_handler(commands=['note_find'])
def note_find(message):
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        bot.reply_to(message, "❌ Формат: /note_find <поисковый запрос>")
        return

    query = parts[1].strip()

    try:
        notes = db.find_notes(message.from_user.id, query)

        if not notes:
            bot.reply_to(message, f"🔍 Заметки по запросу '{query}' не найдены.")
            return

        response = f"🔍 **Найдено заметок:** {len(notes)}\nПо запросу: _{query}_\n\n"

        for note in notes:
            created_at = datetime.fromisoformat(note['created_at']).strftime('%d.%m.%Y %H:%M')
            text = note['text']
            # Подсвечиваем найденный текст
            display_text = text[:100] + "..." if len(text) > 100 else text
            response += f"#{note['id']} _{created_at}_\n{display_text}\n\n"

        if len(response) > 4000:
            response = response[:3900] + "\n\n... _список обрезан_"

        bot.reply_to(message, response, parse_mode='Markdown')
    except Exception as e:
        bot.reply_to(message, f"❌ Ошибка при поиске: {str(e)}")


@bot.message_handler(commands=['note_show'])
def note_show(message):
    parts = message.text.split()
    if len(parts) < 2:
        bot.reply_to(message, "❌ Формат: /note_show <id>")
        return

    try:
        note_id = int(parts[1])
    except ValueError:
        bot.reply_to(message, "❌ ID должен быть числом.")
        return

    try:
        note = db.get_note_by_id(message.from_user.id, note_id)

        if note:
            created_at = datetime.fromisoformat(note['created_at']).strftime('%d.%m.%Y %H:%M')
            response = f"📝 **Заметка #{note['id']}**\n"
            response += f"_Создана: {created_at}_\n\n"
            response += note['text']
            bot.reply_to(message, response, parse_mode='Markdown')
        else:
            bot.reply_to(message, f"❌ Заметка #{note_id} не найдена.")
    except Exception as e:
        bot.reply_to(message, f"❌ Ошибка: {str(e)}")


@bot.message_handler(commands=['note_edit'])
def note_edit(message):
    parts = message.text.split(maxsplit=2)
    if len(parts) < 3:
        bot.reply_to(message, "❌ Формат: /note_edit <id> <новый текст>")
        return

    try:
        note_id = int(parts[1])
        new_text = parts[2].strip()
    except ValueError:
        bot.reply_to(message, "❌ ID должен быть числом.")
        return

    if not new_text:
        bot.reply_to(message, "❌ Текст заметки не может быть пустым.")
        return

    try:
        if db.update_note(message.from_user.id, note_id, new_text):
            bot.reply_to(message, f"✅ Заметка #{note_id} изменена:\n\n{new_text}")
        else:
            bot.reply_to(message, f"❌ Заметка #{note_id} не найдена или не принадлежит вам.")
    except Exception as e:
        bot.reply_to(message, f"❌ Ошибка при редактировании: {str(e)}")


@bot.message_handler(commands=['note_del'])
def note_del(message):
    parts = message.text.split()
    if len(parts) < 2:
        bot.reply_to(message, "❌ Формат: /note_del <id>")
        return

    try:
        note_id = int(parts[1])
    except ValueError:
        bot.reply_to(message, "❌ ID должен быть числом.")
        return

    try:
        if db.delete_note(message.from_user.id, note_id):
            bot.reply_to(message, f"✅ Заметка #{note_id} удалена.")
        else:
            bot.reply_to(message, f"❌ Заметка #{note_id} не найдена или не принадлежит вам.")
    except Exception as e:
        bot.reply_to(message, f"❌ Ошибка при удалении: {str(e)}")

@bot.message_handler(commands=['note_count'])
def note_count(message):
    try:
        count = db.count_notes(message.from_user.id)
        bot.reply_to(message, f"📊 У вас всего {count} заметок.")
    except Exception as e:
        bot.reply_to(message, f"❌ Ошибка при подсчете заметок: {str(e)}")


@bot.message_handler(func=lambda message: True)
def echo_all(message):
    bot.reply_to(message, "❓ Неизвестная команда. Используй /help для списка команд.")


if __name__ == "__main__":
    print("🤖 Бот запускается...")
    print("✅ База данных инициализирована")
    print(f"📁 Путь к БД: {os.getenv('DB_PATH', 'bot.db')}")
    print("📡 Начинаю получение обновлений...")

    while True:
        try:
            bot.polling(none_stop=True, interval=0, timeout=20)
        except Exception as e:
            print(f"❌ Ошибка: {e}")
            time.sleep(5)