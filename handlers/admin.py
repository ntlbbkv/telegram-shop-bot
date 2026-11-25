"""Админ-панель (только для ADMIN_ID): список заказов и смена статусов."""
import logging
from html import escape
from math import ceil

from aiogram import F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import Command
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, Message

import config
from database import orders as db
from keyboards.admin import (
    FILTERS,
    AdmListCb,
    AdmOrderCb,
    AdmSetCb,
    admin_list_kb,
    admin_menu_kb,
    admin_order_kb,
    back_to_menu_kb,
)
from utils import STATUS_LABELS, format_dt, format_items, format_price

router = Router()

# Защита: все обработчики этого файла работают ТОЛЬКО для администратора.
# Для остальных людей эти события просто пропускаются, бот молчит.
router.message.filter(F.from_user.id == config.ADMIN_ID)
router.callback_query.filter(F.from_user.id == config.ADMIN_ID)

PER_PAGE = 8
FILTER_TITLES = dict(FILTERS)
ALLOWED_STATUSES = {"processing", "ready", "completed", "cancelled"}


# ---------- Сборка экранов ----------

async def _render_menu() -> tuple[str, InlineKeyboardMarkup]:
    counts = await db.get_status_counts()
    total = await db.count_orders()
    text = (
        "🛠 <b>Админ-панель</b>\n\n"
        f"Всего заказов: <b>{total}</b>\n"
        "Выберите раздел:"
    )
    return text, admin_menu_kb(counts, total)


async def _render_list(f: str, page: int) -> tuple[str, InlineKeyboardMarkup]:
    status = None if f == "all" else f
    total = await db.count_orders(status)

    if total == 0:
        title = FILTER_TITLES.get(f, "Заказы")
        return f"<b>{title}</b>\n\nЗаказов в этом разделе нет.", back_to_menu_kb()

    pages = ceil(total / PER_PAGE)
    page %= pages  # листание по кругу
    orders = await db.get_orders_page(status, PER_PAGE, page * PER_PAGE)

    text = (
        f"<b>{FILTER_TITLES.get(f, 'Заказы')}</b>\n\n"
        f"Всего: {total}. Нажмите на заказ, чтобы открыть:"
    )
    return text, admin_list_kb(orders, f, page, pages)


async def _render_order(order_id: int, f: str, page: int) -> tuple[str, InlineKeyboardMarkup] | None:
    order = await db.get_order(order_id)
    if order is None:
        return None

    items = await db.get_order_items(order_id)
    status = STATUS_LABELS.get(order["status"], order["status"])

    if order["username"]:
        contact = f"@{escape(order['username'])}"
    else:
        contact = f'<a href="tg://user?id={order["user_id"]}">профиль в Telegram</a>'

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
        f"💬 {contact}\n"
        f"{delivery_line}"
    )
    return text, admin_order_kb(order["id"], order["status"], f, page)


def _client_text(order, status: str) -> str:
    """Сообщение клиенту при смене статуса его заказа."""
    order_id = order["id"]
    address = escape(order["address"] or "")

    if status == "processing":
        return f"🔧 <b>Заказ №{order_id} принят в работу</b>\n\nМы уже готовим ваш заказ."

    if status == "ready":
        if order["delivery_type"] == "pickup":
            tail = f"Можно забирать по адресу: {address}"
        else:
            tail = f"Скоро он будет доставлен по адресу: {address}"
        return f"✅ <b>Заказ №{order_id} готов!</b>\n\n{tail}"

    if status == "completed":
        return f"📦 <b>Заказ №{order_id} выполнен</b>\n\nСпасибо за покупку! Будем рады видеть вас снова 🙌"

    return (
        f"❌ <b>Заказ №{order_id} отменён</b>\n\n"
        "Если это произошло по ошибке, свяжитесь с нами."
    )


async def _edit(callback: CallbackQuery, text: str, kb: InlineKeyboardMarkup) -> bool:
    """Заменяет текст сообщения. Возвращает False, если сообщение слишком старое."""
    message = callback.message
    if not isinstance(message, Message):
        await callback.answer("Сообщение устарело. Отправьте /admin ещё раз.", show_alert=True)
        return False
    try:
        await message.edit_text(text, reply_markup=kb)
    except TelegramBadRequest as e:
        if "message is not modified" not in str(e):
            raise
    return True


# ---------- Обработчики ----------

@router.message(Command("admin"))
async def open_admin(message: Message) -> None:
    text, kb = await _render_menu()
    await message.answer(text, reply_markup=kb)


@router.callback_query(F.data == "adm_menu")
async def back_to_menu(callback: CallbackQuery) -> None:
    text, kb = await _render_menu()
    if await _edit(callback, text, kb):
        await callback.answer()


@router.callback_query(AdmListCb.filter())
async def open_list(callback: CallbackQuery, callback_data: AdmListCb) -> None:
    text, kb = await _render_list(callback_data.f, callback_data.page)
    if await _edit(callback, text, kb):
        await callback.answer()


@router.callback_query(AdmOrderCb.filter())
async def open_order(callback: CallbackQuery, callback_data: AdmOrderCb) -> None:
    rendered = await _render_order(callback_data.id, callback_data.f, callback_data.page)
    if rendered is None:
        await callback.answer("Заказ не найден", show_alert=True)
        return
    text, kb = rendered
    if await _edit(callback, text, kb):
        await callback.answer()


@router.callback_query(AdmSetCb.filter())
async def change_status(callback: CallbackQuery, callback_data: AdmSetCb) -> None:
    new_status = callback_data.new
    if new_status not in ALLOWED_STATUSES:
        await callback.answer("Неизвестный статус", show_alert=True)
        return

    order = await db.get_order(callback_data.id)
    if order is None:
        await callback.answer("Заказ не найден", show_alert=True)
        return

    # Отменённый заказ изменить нельзя. Это защита от нажатий на старые карточки,
    # которые были открыты ДО отмены и всё ещё показывают кнопки.
    if order["status"] == "cancelled":
        rendered = await _render_order(callback_data.id, callback_data.f, callback_data.page)
        if rendered is not None:
            text, kb = rendered
            if not await _edit(callback, text, kb):  # карточка обновится, кнопки пропадут
                return
        await callback.answer("Заказ уже отменён, менять его статус нельзя", show_alert=True)
        return

    changed = await db.set_order_status(callback_data.id, new_status)

    if not changed:
        note, alert = "Заказ уже в этом статусе", False
    else:
        # Уведомляем клиента. Если не вышло (например, он заблокировал бота),
        # статус всё равно изменён, а админу сообщаем об этом.
        try:
            await callback.bot.send_message(order["user_id"], _client_text(order, new_status))
            note, alert = "Статус изменён, клиент уведомлён ✅", False
        except Exception as e:
            logging.warning("Не удалось уведомить клиента по заказу №%s: %s", order["id"], e)
            note = "Статус изменён, но клиент не получил уведомление (возможно, он заблокировал бота)"
            alert = True

    rendered = await _render_order(callback_data.id, callback_data.f, callback_data.page)
    if rendered is not None:
        text, kb = rendered
        if not await _edit(callback, text, kb):
            return

    await callback.answer(note, show_alert=alert)