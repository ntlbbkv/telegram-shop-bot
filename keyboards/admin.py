"""Кнопки админ-панели."""
from aiogram.filters.callback_data import CallbackData
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from utils import STATUS_LABELS, format_price

# Разделы списка заказов: (ключ, название). Ключ "all" означает «все заказы».
FILTERS = [
    ("new", "🆕 Новые"),
    ("processing", "🔧 В работе"),
    ("ready", "✅ Готовые"),
    ("completed", "📦 Выполненные"),
    ("cancelled", "❌ Отменённые"),
    ("all", "📋 Все заказы"),
]

# Кнопки смены статуса в карточке заказа: (новый статус, текст кнопки)
ACTIONS = [
    ("processing", "🔧 В работу"),
    ("ready", "✅ Готов"),
    ("completed", "📦 Выполнен"),
    ("cancelled", "❌ Отменить заказ"),
]


class AdmListCb(CallbackData, prefix="al"):
    f: str      # какой раздел открыт (ключ из FILTERS)
    page: int   # номер страницы (с нуля)


class AdmOrderCb(CallbackData, prefix="ao"):
    id: int
    f: str      # запоминаем раздел и страницу, чтобы вернуться на то же место
    page: int


class AdmSetCb(CallbackData, prefix="as"):
    id: int
    new: str    # новый статус
    f: str
    page: int


def admin_menu_kb(counts: dict[str, int], total: int) -> InlineKeyboardMarkup:
    """Главный экран админки: разделы со счётчиками."""
    builder = InlineKeyboardBuilder()
    for key, label in FILTERS:
        n = total if key == "all" else counts.get(key, 0)
        builder.button(text=f"{label} ({n})", callback_data=AdmListCb(f=key, page=0))
    builder.adjust(2, 2, 2)
    return builder.as_markup()


def back_to_menu_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="⬅️ В админ-панель", callback_data="adm_menu")]]
    )


def admin_list_kb(orders, f: str, page: int, pages: int) -> InlineKeyboardMarkup:
    """Страница списка: заказы, листание (если страниц больше одной) и возврат."""
    builder = InlineKeyboardBuilder()

    for order in orders:
        emoji = STATUS_LABELS.get(order["status"], "•").split(" ")[0]
        name = order["customer_name"]
        if len(name) > 18:
            name = name[:17] + "…"
        builder.button(
            text=f"{emoji} №{order['id']} · {name} · {format_price(order['total'])}",
            callback_data=AdmOrderCb(id=order["id"], f=f, page=page),
        )

    if pages > 1:
        builder.button(text="◀️", callback_data=AdmListCb(f=f, page=page - 1))
        builder.button(text=f"{page + 1} / {pages}", callback_data="noop")
        builder.button(text="▶️", callback_data=AdmListCb(f=f, page=page + 1))

    builder.button(text="⬅️ В админ-панель", callback_data="adm_menu")

    sizes = [1] * len(orders) + ([3] if pages > 1 else []) + [1]
    builder.adjust(*sizes)
    return builder.as_markup()


def admin_order_kb(order_id: int, current_status: str, f: str, page: int) -> InlineKeyboardMarkup:
    """Кнопки в карточке заказа: смена статуса (кроме текущего) и возврат к списку.
    У отменённого заказа статус менять нельзя, остаётся только возврат к списку."""
    builder = InlineKeyboardBuilder()

    count = 0
    if current_status != "cancelled":
        for status, label in ACTIONS:
            if status != current_status:
                builder.button(
                    text=label,
                    callback_data=AdmSetCb(id=order_id, new=status, f=f, page=page),
                )
                count += 1

    builder.button(text="⬅️ К списку", callback_data=AdmListCb(f=f, page=page))

    sizes = [2] * (count // 2) + ([1] if count % 2 else []) + [1]
    builder.adjust(*sizes)
    return builder.as_markup()