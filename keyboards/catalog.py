"""Кнопки каталога: список категорий и карточка товара."""
from aiogram.filters.callback_data import CallbackData
from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder


# Данные, которые «прячутся» в кнопке и приходят боту при нажатии.
class CategoryCb(CallbackData, prefix="cat"):
    id: int


class PageCb(CallbackData, prefix="pg"):
    category_id: int
    page: int


class AddToCartCb(CallbackData, prefix="add"):
    """Первое добавление товара в корзину (кнопка «🛒 В корзину»)."""
    product_id: int
    category_id: int   # нужны, чтобы после добавления обновить именно эту карточку
    page: int


class ChangeQtyCb(CallbackData, prefix="qty"):
    """Изменение количества на карточке (кнопки ➖ и ➕)."""
    action: str        # "inc" (+1) или "dec" (-1)
    product_id: int
    category_id: int
    page: int


def categories_kb(categories) -> InlineKeyboardMarkup:
    """Список категорий: по одной кнопке в строке."""
    builder = InlineKeyboardBuilder()
    for category in categories:
        builder.button(text=category["name"], callback_data=CategoryCb(id=category["id"]))
    builder.adjust(1)
    return builder.as_markup()


def product_kb(
    category_id: int, page: int, total: int, product_id: int, in_cart: int = 0
) -> InlineKeyboardMarkup:
    """Кнопки под карточкой: листание, «В корзину» или ➖ N шт. ➕, «К категориям»."""
    builder = InlineKeyboardBuilder()
    sizes = []  # сколько кнопок в каждой строке

    if total > 1:
        builder.button(text="◀️", callback_data=PageCb(category_id=category_id, page=page - 1))
        builder.button(text=f"{page + 1} / {total}", callback_data="noop")
        builder.button(text="▶️", callback_data=PageCb(category_id=category_id, page=page + 1))
        sizes.append(3)

    if in_cart == 0:
        # Товара ещё нет в корзине: одна кнопка добавления
        builder.button(
            text="🛒 В корзину",
            callback_data=AddToCartCb(product_id=product_id, category_id=category_id, page=page),
        )
        sizes.append(1)
    else:
        # Товар уже в корзине: ряд для изменения количества
        builder.button(
            text="➖",
            callback_data=ChangeQtyCb(
                action="dec", product_id=product_id, category_id=category_id, page=page
            ),
        )
        builder.button(text=f"🛒 {in_cart} шт.", callback_data="noop")
        builder.button(
            text="➕",
            callback_data=ChangeQtyCb(
                action="inc", product_id=product_id, category_id=category_id, page=page
            ),
        )
        sizes.append(3)

    builder.button(text="⬅️ К категориям", callback_data="cats")
    sizes.append(1)

    builder.adjust(*sizes)
    return builder.as_markup()