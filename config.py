"""Настройки проекта. Всё секретное берётся из файла .env"""
import os
from pathlib import Path

from dotenv import load_dotenv

# Папка, где лежит этот файл (корень проекта)
BASE_DIR = Path(__file__).resolve().parent

# Загружаем переменные из .env в окружение
load_dotenv(BASE_DIR / ".env")


def _require(name: str) -> str:
    """Берёт обязательную переменную из .env или останавливает программу с понятной ошибкой."""
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(
            f"В файле .env не заполнена переменная {name}. "
            f"Проверь, что файл .env лежит в корне проекта."
        )
    return value


BOT_TOKEN: str = _require("BOT_TOKEN")

try:
    ADMIN_ID: int = int(_require("ADMIN_ID"))
except ValueError:
    raise RuntimeError("ADMIN_ID в файле .env должен быть числом, например 123456789")

# Путь к базе данных (относительно корня проекта)
DB_PATH: Path = BASE_DIR / os.getenv("DB_PATH", "database/shop.db")

# Название магазина (если в .env не указано, берётся значение по умолчанию)
SHOP_NAME: str = os.getenv("SHOP_NAME", "").strip() or "Demo Coffee"

# Адрес самовывоза (если в .env не указан, берётся значение по умолчанию)
PICKUP_ADDRESS: str = os.getenv("PICKUP_ADDRESS", "").strip() or "ул. Примерная, 1"

# Сдвиг времени от UTC в часах (для показа даты и времени заказов)
try:
    TIMEZONE_OFFSET: int = int(os.getenv("TIMEZONE_OFFSET", "3").strip())
except ValueError:
    raise RuntimeError("TIMEZONE_OFFSET в файле .env должен быть целым числом, например 3")

# Папка с фотографиями товаров
PHOTOS_DIR: Path = BASE_DIR / "media" / "products"