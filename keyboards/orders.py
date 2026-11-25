"""Кнопки раздела «Мои заказы»."""
from aiogram.filters.callback_data import CallbackData
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from utils import STATUS_LABELS, format_price


class OrderCb(CallbackData, prefix="ord"):
    id: int


def orders_list_kb(orders) -> InlineKeyboardMarkup:
    """Каждый заказ - отдельная кнопка: «№3 · 🆕 Новый · 540 ₽»."""
    rows = []
    for order in orders:
        status = STATUS_LABELS.get(order["status"], order["status"])
        rows.append([
            InlineKeyboardButton(
                text=f"№{order['id']} · {status} · {format_price(order['total'])}",
                callback_data=OrderCb(id=order["id"]).pack(),
            )
        ])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def order_detail_kb(order_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🔄 Обновить статус", callback_data=OrderCb(id=order_id).pack())],
            [InlineKeyboardButton(text="⬅️ К списку заказов", callback_data="my_orders")],
        ]
    )


def no_orders_kb() -> InlineKeyboardMarkup:
    """Кнопка под сообщением «У вас пока нет заказов»."""
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="🛍 В каталог", callback_data="to_catalog")]]
    )