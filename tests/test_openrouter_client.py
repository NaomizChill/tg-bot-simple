import pytest
import responses  # Библиотека для мокирования сетевых запросов
import json
from openrouter_client import chat_once, OpenRouterError


# Используем декоратор, который "перехватывает" все HTTP-запросы
@responses.activate
def test_chat_once_success():
    """
    Тест 1: Проверяет успешный вызов chat_once.
    Мы имитируем успешный ответ от сервера OpenRouter.
    """
    # 1. Готовим фейковый ответ от API
    mock_url = "https://openrouter.ai/api/v1/chat/completions"
    mock_response_payload = {
        "id": "gen-123",
        "choices": [{
            "message": {
                "content": "Hello there!"
            }
        }]
    }
    # Регистрируем наш фейковый ответ: любой POST-запрос на этот URL
    # вернет наш JSON с кодом 200 OK.
    responses.add(responses.POST, mock_url, json=mock_response_payload, status=200)

    # 2. Выполняем действие: вызываем нашу функцию
    # (Она не пойдет в интернет, а получит наш фейковый ответ)
    text, ms = chat_once(
        msgs=[{"role": "user", "content": "ping"}],
        model="test-model:free"
    )

    # 3. Проверяем результат
    assert text == "Hello there!"
    assert ms > 0  # Проверяем, что время замерилось

    # 4. (Бонус) Проверяем, что именно было "отправлено"
    sent_request = responses.calls[0].request
    sent_payload = json.loads(sent_request.body)

    assert sent_payload["model"] == "test-model:free"
    assert sent_payload["messages"][0]["content"] == "ping"


    @responses.activate
    def test_chat_once_handles_503_error():
        """
        Тест 2: Проверяет, что chat_once правильно обрабатывает ошибку 503
        и выбрасывает наше кастомное исключение OpenRouterError.
        """
        # 1. Готовим фейковый ответ с ошибкой
        mock_url = "https://openrouter.ai/api/v1/chat/completions"
        responses.add(responses.POST, mock_url, status=503)  # Имитируем ошибку "Сервис недоступен"

        # 2. Проверяем, что функция выбросит ожидаемое исключение
        with pytest.raises(OpenRouterError) as excinfo:
            chat_once(
                msgs=[{"role": "user", "content": "ping"}],
                model="test-model:free"
            )

        # 3. Проверяем текст ошибки и статус-код
        assert "Сервер OpenRouter перегружен" in str(excinfo.value)
        assert excinfo.value.status_code == 503