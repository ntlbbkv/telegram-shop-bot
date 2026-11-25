"""Корзина: просмотр, изменение количества, удаление, очистка."""
from html import escape

from aiogram import Bot, F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, Message

from database import cart as db
from database import products as products_db
from database.cart import MAX_QTY
from keyboards.cart import CartCb, cart_kb, empty_cart_kb
from keyboards.catalog import categories_kb
from keyboards.main_menu import BTN_CART
from utils import format_price

router = Router()

# Номер последнего сообщения с корзиной у каждого человека: {user_id: message_id}.
# Нужен, чтобы при повторном открытии корзины удалять старую.
# После перезапуска бота память очищается, это нормально.
_cart_messages: dict[int, int] = {}


async def _render_cart(user_id: int) -> tuple[str, InlineKeyboardMarkup]:
    """Собирает текст и кнопки корзины."""
    items = await db.get_cart(user_id)

    if not items:
        return (
            "🛒 <b>Корзина пуста</b>\n\nЗагляните в каталог и выберите что-нибудь вкусное.",
            empty_cart_kb(),
        )

    blocks = []
    total = 0
    for n, item in enumerate(items, start=1):
        line_total = item["price"] * item["quantity"]
        total += line_total
        blocks.append(
            f"{n}. <b>{escape(item['name'])}</b>\n"
            f"    {item['quantity']} × {format_price(item['price'])} = {format_price(line_total)}"
        )

    text = (
        "🛒 <b>Ваша корзина</b>\n\n"
        + "\n\n".join(blocks)
        + f"\n\n💰 <b>Итого: {format_price(total)}</b>"
    )
    return text, cart_kb(items)


async def send_cart(bot: Bot, user_id: int) -> None:
    """Показывает корзину новым сообщением, а ранее открытую корзину удаляет.
    Эту функцию используют и кнопка «🛒 Корзина», и «Назад» при оформлении заказа."""
    old_id = _cart_messages.pop(user_id, None)

    text, kb = await _render_cart(user_id)
    sent = await bot.send_message(user_id, text, reply_markup=kb)
    _cart_messages[user_id] = sent.message_id

    if old_id is not None:
        try:
            await bot.delete_message(user_id, old_id)
        except TelegramBadRequest:
            pass  # сообщение уже удалено или слишком старое, ничего страшного


async def _refresh_cart(callback: CallbackQuery) -> None:
    """Перерисовывает сообщение с корзиной после изменения."""
    message = callback.message
    if not isinstance(message, Message):
        await callback.answer("Сообщение устарело. Нажмите «🛒 Корзина» ещё раз.", show_alert=True)
        return

    text, kb = await _render_cart(callback.from_user.id)
    try:
        await message.edit_text(text, reply_markup=kb)
    except TelegramBadRequest as e:
        # «Не изменилось» бывает, если нажали ➕ на максимуме, это не ошибка
        if "message is not modified" not in str(e):
            raise


# ---------- Обработчики ----------

@router.message(F.text == BTN_CART)
async def open_cart(message: Message) -> None:
    await send_cart(message.bot, message.from_user.id)


@router.callback_query(F.data == "go_cart")
async def old_go_cart_button(callback: CallbackQuery) -> None:
    """Кнопка «Перейти в корзину» осталась только на очень старых карточках."""
    await callback.answer(
        "Корзина открывается кнопкой «🛒 Корзина» в главном меню внизу.",
        show_alert=True,
    )


@router.callback_query(CartCb.filter())
async def change_cart(callback: CallbackQuery, callback_data: CartCb) -> None:
    user_id = callback.from_user.id
    product_id = callback_data.product_id

    if callback_data.action == "del":
        await db.remove_item(user_id, product_id)
        await callback.answer("Товар убран")
    else:
        delta = 1 if callback_data.action == "inc" else -1
        result = await db.change_quantity(user_id, product_id, delta)
        if result is not None and result[1]:  # упёрлись в максимум
            await callback.answer(f"Максимум {MAX_QTY} шт. одного товара", show_alert=True)
        else:
            await callback.answer()

    await _refresh_cart(callback)


@router.callback_query(F.data == "cart_clear")
async def clear_cart(callback: CallbackQuery) -> None:
    await db.clear_cart(callback.from_user.id)
    await callback.answer("Корзина очищена")
    await _refresh_cart(callback)


@router.callback_query(F.data == "to_catalog")
async def cart_to_catalog(callback: CallbackQuery) -> None:
    """Кнопка «В каталог» под корзиной: показываем список категорий на месте корзины."""
    message = callback.message
    if not isinstance(message, Message):
        await callback.answer("Нажмите «🛍 Каталог» в меню.", show_alert=True)
        return

    categories = await products_db.get_categories()
    await message.edit_text("Выберите категорию:", reply_markup=categories_kb(categories))

    # Это сообщение теперь каталог, а не корзина: забываем его,
    # иначе следующее открытие корзины удалило бы каталог
    if _cart_messages.get(callback.from_user.id) == message.message_id:
        _cart_messages.pop(callback.from_user.id, None)

    await callback.answer()