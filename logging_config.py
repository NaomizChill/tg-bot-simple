import logging
import os
import time
from logging.handlers import RotatingFileHandler
from dotenv import load_dotenv

load_dotenv()


class DotTimeFormatter(logging.Formatter):
    """Кастомный форматтер времени для логов."""

    def formatTime(self, record, datefmt=None):
        t = time.localtime(record.created)
        datetime_str = time.strftime("%Y-%m-%d %H:%M:%S", t)
        return f"{datetime_str}.{int(record.msecs):03d}"


def setup_logging():
    """Инициализируем корневой логгер."""
    log_dir = os.getenv("LOG_DIR", "logs")
    log_file_name = os.getenv("LOG_FILE", "bot.log")
    log_encoding = os.getenv("LOG_ENCODING", "utf-8")
    log_max_bytes = int(os.getenv("LOG_MAX_BYTES", "5000000"))
    log_backup_count = int(os.getenv("LOG_BACKUP_COUNT", "5"))
    log_level_name = os.getenv("LOG_LEVEL", "INFO").upper()
    log_level = getattr(logging, log_level_name, logging.INFO)

    os.makedirs(log_dir, exist_ok=True)
    log_path = os.path.join(log_dir, log_file_name)

    fmt = "%(asctime)s [%(threadName)s] %(levelname)s %(name)s: %(message)s"
    formatter = DotTimeFormatter(fmt)

    # Консольный хендлер
    console = logging.StreamHandler()
    console.setLevel(log_level)
    console.setFormatter(formatter)

    # Файловый хендлер с ротацией
    file_handler = RotatingFileHandler(
        log_path,
        maxBytes=log_max_bytes,
        backupCount=log_backup_count,
        encoding=log_encoding,
    )
    file_handler.setLevel(log_level)
    file_handler.setFormatter(formatter)

    # Чистим старые хендлеры и настраиваем basicConfig
    logging.root.handlers.clear()
    logging.basicConfig(
        level=log_level,
        handlers=[console, file_handler],
    )