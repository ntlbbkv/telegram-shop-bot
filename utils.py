"""Вспомогательные функции, которые нужны в разных частях бота."""
import re
from datetime import datetime, timedelta, timezone
from html import escape
from pathlib import Path

import config

PHOTO_EXTENSIONS = (".jpg", ".jpeg", ".png", ".webp")

# Статусы заказа: как они хранятся в базе -> как показываются людям
STATUS_LABELS = {
    "new": "🆕 Новый",
    "processing": "🔧 В работе",
    "ready": "✅ Готов",
    "completed": "📦 Выполнен",
    "cancelled": "❌ Отменён",
}


def format_price(value: int) -> str:
    """1500 -> '1 500 ₽'"""
    return f"{value:,}".replace(",", " ") + " ₽"


def format_dt(value: str) -> str:
    """Время из базы (UTC) -> '23.11.2026 15:30' в часовом поясе из настроек."""
    try:
        moment = datetime.strptime(value, "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
    except (ValueError, TypeError):
        return str(value)
    local = moment.astimezone(timezone(timedelta(hours=config.TIMEZONE_OFFSET)))
    return local.strftime("%d.%m.%Y %H:%M")


def format_items(items) -> str:
    """Список позиций заказа или корзины в виде текста.
    Каждая позиция должна иметь поля name, price, quantity."""
    lines = []
    for item in items:
        line_total = item["price"] * item["quantity"]
        lines.append(
            f"• {escape(item['name'])} — {item['quantity']} × "
            f"{format_price(item['price'])} = {format_price(line_total)}"
        )
    return "\n".join(lines)


def normalize_phone(raw: str, from_contact: bool = False) -> str | None:
    """Проверяет номер телефона и приводит к виду +79991234567.
    Возвращает None, если на номер не похоже.

    Бот ничего не «додумывает» и не дописывает лишних цифр:
    - номер, начинающийся с «+», считается международным и остаётся как есть
      (для кода +7 нужно ровно 11 цифр);
    - 8 999 123-45-67 или 7 999 123-45-67 (11 цифр) -> +79991234567;
    - 999 123-45-67 (10 цифр, начинается с 9)       -> +79991234567;
    - номер без «+», 11-15 цифр, не на 7 и не на 8  -> просто добавляем «+»;
    - всё остальное не принимаем, пусть человек введёт номер полностью.

    from_contact=True: номер пришёл из кнопки «Отправить мой номер», Telegram
    присылает его уже полным (иногда без «+»), поэтому доверяем ему.
    """
    raw = raw.strip()
    if not re.fullmatch(r"\+?[\d\s\-()]+", raw):
        return None

    digits = re.sub(r"\D", "", raw)
    if not digits:
        return None

    if from_contact:
        return "+" + digits if 8 <= len(digits) <= 15 else None

    if raw.startswith("+"):
        if digits[0] == "7":
            return "+" + digits if len(digits) == 11 else None
        if digits[0] == "8" and len(digits) == 11:
            return None  # «+8 999...» почти наверняка опечатка
        return "+" + digits if 8 <= len(digits) <= 15 else None

    if len(digits) == 11 and digits[0] in "78":
        return "+7" + digits[1:]
    if len(digits) == 10 and digits[0] == "9":
        return "+7" + digits
    if 11 <= len(digits) <= 15 and digits[0] not in "78":
        return "+" + digits
    return None


def find_product_photo(product_id: int, photo_name: str | None = None) -> Path | None:
    """Ищет фото товара в папке media/products.

    1) Если в базе у товара указано имя файла (колонка photo), берём его.
    2) Иначе ищем файл с номером товара: 1.jpg, 1.png, 1.webp и т.д.
    Если ничего не нашли, возвращаем None, и карточка покажется без фото.
    """
    if photo_name:
        path = config.PHOTOS_DIR / photo_name
        if path.is_file():
            return path

    for ext in PHOTO_EXTENSIONS:
        path = config.PHOTOS_DIR / f"{product_id}{ext}"
        if path.is_file():
            return path

    return None