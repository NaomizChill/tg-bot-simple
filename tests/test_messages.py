# tests/test_messages.py

def test_build_messages_includes_character_and_rules(db_module, main_module):
    """
    Тест проверяет, что system-промпт правильно включает имя персонажа,
    его описание и правила.
    """
    db = db_module
    main = main_module
    uid = 42001

    # Устанавливаем персонажа
    # Сначала получаем краткую информацию (ID и имя), чтобы узнать ID
    char_info = db.list_characters()[0]
    char_id_to_set = char_info["id"]

    # Устанавливаем персонажа для пользователя
    db.set_user_character(uid, char_id_to_set)

    # А теперь получаем ПОЛНУЮ информацию о персонаже для проверки
    target_char = db.get_character_by_id(char_id_to_set)
    # Генерируем сообщение
    msgs = main._build_messages(uid, "Какой-то вопрос")

    # Проверяем структуру
    assert isinstance(msgs, list) and len(msgs) == 2
    assert msgs[0]["role"] == "system"
    assert msgs[1]["role"] == "user"

    # Проверяем содержимое
    system_prompt = msgs[0]["content"]
    assert target_char["name"] in system_prompt
    assert target_char["prompt"] in system_prompt
    assert "Правила:" in system_prompt  # Проверяем, что правила на месте
    assert "Какой-то вопрос" in msgs[1]["content"]