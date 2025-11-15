# tests/test_main.py
import responses
import pytest

@responses.activate
def test_fetch_weather_success(main_module):
    """Тест успешного получения погоды."""
    main = main_module
    # 1. Готовим фейковый успешный ответ от API
    mock_url = "https://api.open-meteo.com/v1/forecast"
    mock_json = {
        "current": {
            "temperature_2m": 15.5,
            "weather_code": 3
        }
    }
    responses.add(responses.GET, mock_url, json=mock_json, status=200)

    # 2. Вызываем нашу функцию
    result = main.fetch_weather_moscow_open_meteo()

    # 3. Проверяем, что результат отформатирован правильно
    assert "Москва: сейчас 16°C, Пасмурно" in result

@responses.activate
def test_fetch_weather_network_error(main_module):
    """Тест обработки сетевой ошибки."""
    main = main_module
    mock_url = "https://api.open-meteo.com/v1/forecast"
    # Имитируем ошибку 500 (сервер недоступен)
    responses.add(responses.GET, mock_url, status=500)

    result = main.fetch_weather_moscow_open_meteo()
    assert "Не удалось получить погоду (сеть)" in result


# --- Новые тесты для домашней работы ---

def test_parse_ints_from_text_basic(main_module):
    """
    Тест 1: Проверяет базовый случай с положительными числами,
    разделенными пробелами.
    """
    main = main_module
    text = "/sum 10 5 15"
    expected = [10, 5, 15]
    result = main.parse_ints_from_text(text)
    assert result == expected, "Функция должна правильно извлекать положительные числа"

def test_parse_ints_from_text_with_negatives_and_commas(main_module):
    """
    Тест 2: Проверяет работу с отрицательными числами, запятыми
    и лишним текстом.
    """
    main = main_module
    text = "посчитай -5, 100, котики и -1"
    expected = [-5, 100, -1]
    result = main.parse_ints_from_text(text)
    assert result == expected, "Функция должна обрабатывать отрицательные числа, запятые и текст"

def test_parse_ints_from_text_empty_on_no_numbers(main_module):
    """
    Тест 3: Проверяет, что функция возвращает пустой список,
    если в тексте нет чисел.
    """
    main = main_module
    text = "здесь совсем нет чисел"
    expected = []
    result = main.parse_ints_from_text(text)
    assert result == expected, "Функция должна возвращать пустой список, если чисел нет"