"""Раздел «Мои заказы»: список заказов клиента и подробности по каждому."""
from html import escape

from aiogram import F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, Message

from database import orders as db
from keyboards.main_menu import BTN_ORDERS
from keyboards.orders import OrderCb, no_orders_kb, order_detail_kb, orders_list_kb
from utils import STATUS_LABELS, format_dt, format_items, format_price

router = Router()


async def _render_list(user_id: int) -> tuple[str, InlineKeyboardMarkup]:
    orders = await db.get_user_orders(user_id)
    if not orders:
        return (
            "📦 <b>Мои заказы</b>\n\nУ вас пока нет заказов. "
            "Загляните в каталог, там много вкусного!",
            no_orders_kb(),
        )
    return (
        "📦 <b>Мои заказы</b>\n\nПоследние заказы. "
        "Нажмите на заказ, чтобы посмотреть подробности:",
        orders_list_kb(orders),
    )


async def _render_order(user_id: int, order_id: int) -> tuple[str, InlineKeyboardMarkup] | None:
    order = await db.get_user_order(order_id, user_id)
    if order is None:
        return None

    items = await db.get_order_items(order_id)
    status = STATUS_LABELS.get(order["status"], order["status"])

    if order["delivery_type"] == "pickup":
        delivery_line = f"🏪 Самовывоз: {escape(order['address'] or '')}"
    else:
        delivery_line = f"🚚 Доставка: {escape(order['address'] or '')}"

    text = (
        f"📦 <b>Заказ №{order['id']}</b>\n"
        f"🕒 {format_dt(order['created_at'])}\n"
        f"Статус: <b>{status}</b>\n\n"
        f"{format_items(items)}\n\n"
        f"💰 <b>Итого: {format_price(order['total'])}</b>\n\n"
        f"👤 {escape(order['customer_name'])}\n"
        f"📞 {escape(order['phone'])}\n"
        f"{delivery_line}"
    )
    return text, order_detail_kb(order["id"])


# ---------- Обработчики ----------

@router.message(F.text == BTN_ORDERS)
async def open_orders(message: Message) -> None:
    text, kb = await _render_list(message.from_user.id)
    await message.answer(text, reply_markup=kb)


@router.callback_query(F.data == "my_orders")
async def back_to_list(callback: CallbackQuery) -> None:
    message = callback.message
    if not isinstance(message, Message):
        await callback.answer("Нажмите «📦 Мои заказы» в меню.", show_alert=True)
        return

    text, kb = await _render_list(callback.from_user.id)
    try:
        await message.edit_text(text, reply_markup=kb)
    except TelegramBadRequest as e:
        if "message is not modified" not in str(e):
            raise
    await callback.answer()


@router.callback_query(OrderCb.filter())
async def open_order(callback: CallbackQuery, callback_data: OrderCb) -> None:
    message = callback.message
    if not isinstance(message, Message):
        await callback.answer("Нажмите «📦 Мои заказы» в меню.", show_alert=True)
        return

    rendered = await _render_order(callback.from_user.id, callback_data.id)
    if rendered is None:
        await callback.answer("Заказ не найден", show_alert=True)
        return

    text, kb = rendered
    try:
        await message.edit_text(text, reply_markup=kb)
    except TelegramBadRequest as e:
        if "message is not modified" in str(e):
            # Нажали «Обновить», а статус тот же
            await callback.answer("Статус не изменился")
            return
        raise
    await callback.answer()