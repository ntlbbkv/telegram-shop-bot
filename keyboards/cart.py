"""Кнопки корзины."""
from aiogram.filters.callback_data import CallbackData
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


class CartCb(CallbackData, prefix="cart"):
    action: str      # "inc" (+1), "dec" (-1), "del" (убрать товар)
    product_id: int


def cart_kb(items) -> InlineKeyboardMarkup:
    """Для каждого товара своя строка: ➖ номер и количество ➕ ❌, внизу общие кнопки."""
    rows = []
    for n, item in enumerate(items, start=1):
        product_id = item["product_id"]
        rows.append([
            InlineKeyboardButton(
                text="➖", callback_data=CartCb(action="dec", product_id=product_id).pack()
            ),
            InlineKeyboardButton(text=f"{n}. {item['quantity']} шт.", callback_data="noop"),
            InlineKeyboardButton(
                text="➕", callback_data=CartCb(action="inc", product_id=product_id).pack()
            ),
            InlineKeyboardButton(
                text="❌", callback_data=CartCb(action="del", product_id=product_id).pack()
            ),
        ])

    rows.append([InlineKeyboardButton(text="✅ Оформить заказ", callback_data="checkout")])
    rows.append([InlineKeyboardButton(text="🗑 Очистить корзину", callback_data="cart_clear")])
    rows.append([InlineKeyboardButton(text="🛍 В каталог", callback_data="to_catalog")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def empty_cart_kb() -> InlineKeyboardMarkup:
    """Кнопка под сообщением «Корзина пуста»."""
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="🛍 В каталог", callback_data="to_catalog")]]
    )