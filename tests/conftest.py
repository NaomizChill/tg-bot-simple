# tests/conftest.py
import importlib
import pytest

@pytest.fixture(scope="session")
def tmp_db_path(tmp_path_factory):
    """Фикстура, создающая путь к временной БД для одной сессии тестов."""
    return str(tmp_path_factory.mktemp("data") / "bot_test.db")

@pytest.fixture()
def db_module(tmp_db_path, monkeypatch):
    """
    Фикстура для тестов БД.
    Подменяет путь к БД на временный и инициализирует чистую БД перед каждым тестом.
    """
    # Динамически импортируем модуль db, чтобы monkeypatch успел сработать
    db = importlib.import_module("db")
    # Подменяем глобальную переменную DB_PATH в модуле db
    monkeypatch.setattr(db, "DB_PATH", tmp_db_path)
    # Инициализируем схему БД
    db.init_db()
    return db

@pytest.fixture()
def main_module(db_module, monkeypatch):
    """
    Фикстура для тестов основной логики.
    Импортирует модуль main после того, как уже настроена временная БД.
    """
    # Подменяем токен, чтобы бот не пытался реально подключиться к Telegram
    monkeypatch.setenv("TOKEN", "123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11")
    main = importlib.import_module("main")
    # Перезагружаем, чтобы он подхватил fake-token
    importlib.reload(main)
    return main