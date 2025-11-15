# tests/test_db.py
import pytest


def test_character_upsert(db_module):
    """Тест проверяет, что создание и обновление персонажа пользователя работает (UPSERT)."""
    db = db_module
    uid = 12345
    characters = db.list_characters()
    assert characters, "Список персонажей не должен быть пустым. Проверьте init_db."

    # 1. Устанавливаем первого персонажа
    char1_id = characters[0]["id"]
    db.set_user_character(uid, char1_id)
    p1 = db.get_user_character(uid)
    assert p1["id"] == char1_id, "Персонаж не установился"

    # 2. Устанавливаем другого персонажа для того же пользователя
    char2_id = characters[1]["id"]
    db.set_user_character(uid, char2_id)
    p2 = db.get_user_character(uid)
    assert p2["id"] == char2_id, "Персонаж не обновился, а должен был"


def test_get_user_character_falls_back_to_default(db_module):
    """Тест проверяет, что для нового пользователя возвращается персонаж по умолчанию."""
    db = db_module
    uid_new = 999999  # Пользователь, которого точно нет в БД

    # Вызов без предварительного set_user_character
    ch = db.get_user_character(uid_new)

    all_chars = db.list_characters()
    all_ids = {c["id"] for c in all_chars}

    assert ch is not None, "Должен вернуться хоть какой-то персонаж"
    assert ch["id"] in all_ids, "Возвращаемый персонаж должен быть из списка существующих"


# tests/test_db.py

def test_set_user_character_raises_error_for_unknown_id(db_module):
    """
    Тест проверяет, что set_user_character выбрасывает ValueError
    при попытке установить несуществующий ID персонажа.
    """
    db = db_module
    unknown_id = 99999  # ID, которого гарантированно нет в базе
    user_id = 123

    # Мы ожидаем, что код внутри этого блока вызовет ошибку ValueError.
    # Если ошибка произойдет, тест будет считаться пройденным.
    # Если ошибки не будет (или будет другая ошибка), тест упадет.
    with pytest.raises(ValueError) as excinfo:
        db.set_user_character(user_id, unknown_id)

    # Это необязательная, но очень полезная проверка:
    # убедимся, что текст ошибки именно тот, который мы ожидаем.
    assert "Неизвестный ID персонажа" in str(excinfo.value)