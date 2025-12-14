# openrouter_client.py
import os
import requests
import logging
import json
import time
from dotenv import load_dotenv

# Загружаем переменные окружения (включая OPENROUTER_API_KEY)
load_dotenv()

# Получаем логгер для этого модуля
log = logging.getLogger(__name__)

# --- Константы ---
OPENROUTER_API_URL = "https://openrouter.ai/api/v1/chat/completions"
# 1. Ключ API вычитывается из переменных окружения
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")


# --- Класс для ошибок API ---
class OpenRouterError(Exception):
    def __init__(self, message, status_code=None):
        super().__init__(message)
        self.status_code = status_code


# --- Функция для "дружелюбного" описания ошибок ---
def _get_friendly_error(status_code: int) -> str:
    error_map = {
        400: "Неверный формат запроса к API.",
        401: "Ключ OpenRouter API отклонен. Проверьте переменную OPENROUTER_API_KEY в .env файле.",
        429: "Превышены лимиты бесплатной модели. Попробуйте позже.",
        # 3. Обработка кодов 5xx
        500: "Внутренняя ошибка сервера OpenRouter. Попробуйте позже.",
        502: "Сервер OpenRouter временно недоступен (Bad Gateway).",
        503: "Сервер OpenRouter перегружен (Service Unavailable). Попробуйте позже.",
        504: "Сервер OpenRouter не ответил вовремя (Gateway Timeout)."
    }
    return error_map.get(status_code, f"Неизвестная ошибка API (код: {status_code}).")


# --- Основная функция ---
def chat_once(msgs: list[dict], model: str, temperature: float = 0.7, max_tokens: int = 1024, timeout_s: int = 30) -> \
tuple[str, int]:
    """Отправляет один запрос к OpenRouter и возвращает ответ."""
    if not OPENROUTER_API_KEY:
        msg = "Отсутствует ключ OPENROUTER_API_KEY в .env файле."
        log.error(msg)
        raise OpenRouterError(msg, status_code=401)

    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": model,
        "messages": msgs,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }

    log.debug(f"Запрос к OpenRouter: model={model}, temp={temperature}, max_tokens={max_tokens}")
    t0 = time.perf_counter()

    try:
        r = requests.post(OPENROUTER_API_URL, headers=headers, json=payload, timeout=timeout_s)
        dt_ms = int((time.perf_counter() - t0) * 1000)

        # Проверяем статус ответа
        if r.status_code != 200:
            error_msg = _get_friendly_error(r.status_code)
            log.error(f"Ошибка от OpenRouter API (статус {r.status_code}): {r.text}")
            raise OpenRouterError(error_msg, status_code=r.status_code)

        data = r.json()
        text = data["choices"][0]["message"]["content"]
        return text.strip(), dt_ms

    except requests.exceptions.RequestException as e:
        log.error(f"Сетевая ошибка при обращении к OpenRouter: {e}")
        raise OpenRouterError(f"Не удалось подключиться к OpenRouter: {e}")
    except (KeyError, IndexError, json.JSONDecodeError) as e:
        log.error(f"Неожиданная структура ответа от OpenRouter: {e}")
        raise OpenRouterError("Получен некорректный ответ от API.")