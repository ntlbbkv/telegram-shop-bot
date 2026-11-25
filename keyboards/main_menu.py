"""Главное меню: постоянные кнопки внизу экрана."""
from aiogram.types import KeyboardButton, ReplyKeyboardMarkup

# Тексты кнопок вынесены в константы: по ним же обработчики ловят нажатия.
# Так текст кнопки меняется в одном месте, и ничего не ломается.
BTN_CATALOG = "🛍 Каталог"
BTN_CART = "🛒 Корзина"
BTN_ORDERS = "📦 Мои заказы"


def main_menu_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=BTN_CATALOG)],
            [KeyboardButton(text=BTN_CART), KeyboardButton(text=BTN_ORDERS)],
        ],
        resize_keyboard=True,  # кнопки не огромные, а нормального размера
        input_field_placeholder="Выберите раздел меню",
    )