"""Оформление заказа: имя -> телефон -> доставка -> адрес -> подтверждение.
На каждом шаге есть «⬅️ Назад» и «❌ Отмена»."""
import logging
from html import escape

from aiogram import F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message, ReplyKeyboardRemove

import config
from database import cart as cart_db
from database import orders as orders_db
from handlers.cart import send_cart
from keyboards.checkout import (
    BTN_BACK,
    BTN_CANCEL,
    confirm_kb,
    delivery_kb,
    name_kb,
    nav_kb,
    phone_kb,
)
from keyboards.main_menu import BTN_CART, BTN_CATALOG, BTN_ORDERS, main_menu_kb
from utils import format_items, format_price, normalize_phone

router = Router()

# Тексты кнопок главного меню: если человек вдруг пришлёт такой текст как «имя», не принимаем
MENU_BUTTONS = {BTN_CATALOG, BTN_CART, BTN_ORDERS}


class Checkout(StatesGroup):
    """Шаги оформления заказа."""
    name = State()
    phone = State()
    delivery = State()
    address = State()
    confirm = State()


# ---------- Вспомогательные функции ----------

async def _say(callback: CallbackQuery, text: str, **kwargs) -> None:
    """Отправляет новое сообщение в чат с пользователем (работает всегда, даже если
    исходное сообщение с кнопкой уже слишком старое)."""
    await callback.bot.send_message(callback.from_user.id, text, **kwargs)


async def _replace_text(callback: CallbackQuery, text: str) -> None:
    """Заменяет текст сообщения с кнопкой и убирает сами кнопки."""
    if isinstance(callback.message, Message):
        try:
            await callback.message.edit_text(text)
        except TelegramBadRequest:
            pass


async def _remove_buttons(callback: CallbackQuery) -> None:
    """Убирает кнопки под сообщением, чтобы нельзя было нажать повторно."""
    if isinstance(callback.message, Message):
        try:
            await callback.message.edit_reply_markup(reply_markup=None)
        except TelegramBadRequest:
            pass


# ---------- Показ шагов (используются и при движении вперёд, и при «Назад») ----------

async def _ask_name(bot, user_id: int, state: FSMContext) -> None:
    await state.set_state(Checkout.name)
    await bot.send_message(user_id, "Как вас зовут?", reply_markup=name_kb())


async def _ask_phone(bot, user_id: int, state: FSMContext, intro: str = "") -> None:
    await state.set_state(Checkout.phone)
    await bot.send_message(
        user_id,
        intro + "Укажите телефон для связи: нажмите «📱 Отправить мой номер» "
        "или введите его вручную.",
        reply_markup=phone_kb(),
    )


async def _ask_delivery(bot, user_id: int, state: FSMContext) -> None:
    await state.set_state(Checkout.delivery)
    await bot.send_message(user_id, "Как вы хотите получить заказ?", reply_markup=delivery_kb())


async def _ask_address(bot, user_id: int, state: FSMContext) -> None:
    await state.set_state(Checkout.address)
    await bot.send_message(
        user_id,
        "Введите адрес доставки (город, улица, дом, квартира):",
        reply_markup=nav_kb(),
    )


async def _show_summary(bot, user_id: int, state: FSMContext) -> None:
    """Показывает сводку заказа с кнопками «Подтвердить», «Назад», «Отмена»."""
    data = await state.get_data()
    items = await cart_db.get_cart(user_id)

    if not items:
        await state.clear()
        await bot.send_message(
            user_id,
            "Ваша корзина пуста, оформлять нечего.",
            reply_markup=main_menu_kb(),
        )
        return

    total = sum(item["price"] * item["quantity"] for item in items)

    if data["delivery_type"] == "pickup":
        delivery_line = f"🏪 Самовывоз: {escape(data['address'])}"
    else:
        delivery_line = f"🚚 Доставка: {escape(data['address'])}"

    await state.set_state(Checkout.confirm)
    await bot.send_message(
        user_id,
        "📋 <b>Проверьте ваш заказ</b>\n\n"
        f"{format_items(items)}\n\n"
        f"💰 <b>Итого: {format_price(total)}</b>\n\n"
        f"👤 {escape(data['name'])}\n"
        f"📞 {escape(data['phone'])}\n"
        f"{delivery_line}",
        reply_markup=confirm_kb(),
    )


async def _back_to_cart(bot, user_id: int, state: FSMContext) -> None:
    """«Назад» с первого шага: выходим из оформления и показываем корзину."""
    await state.clear()
    # Возвращаем главное меню (нижнюю клавиатуру)
    await bot.send_message(
        user_id,
        "↩️ Вы вернулись в корзину. Оформить заказ можно заново в любой момент.",
        reply_markup=main_menu_kb(),
    )
    await send_cart(bot, user_id)


async def _go_back(bot, user_id: int, state: FSMContext) -> None:
    """Возвращает на предыдущий шаг в зависимости от того, где сейчас человек."""
    current = await state.get_state()
    data = await state.get_data()

    if current == Checkout.name.state:
        await _back_to_cart(bot, user_id, state)
    elif current == Checkout.phone.state:
        await _ask_name(bot, user_id, state)
    elif current == Checkout.delivery.state:
        await _ask_phone(bot, user_id, state)
    elif current == Checkout.address.state:
        await _ask_delivery(bot, user_id, state)
    elif current == Checkout.confirm.state:
        # При самовывозе адрес не вводили, поэтому возвращаемся к выбору способа получения
        if data.get("delivery_type") == "delivery":
            await _ask_address(bot, user_id, state)
        else:
            await _ask_delivery(bot, user_id, state)
    else:
        await _ask_name(bot, user_id, state)


def _admin_text(order_id: int, user, data: dict, items: list, total: int) -> str:
    """Текст уведомления владельцу о новом заказе."""
    if user.username:
        contact = f"@{escape(user.username)}"
    else:
        contact = f'<a href="tg://user?id={user.id}">профиль в Telegram</a>'

    if data["delivery_type"] == "pickup":
        delivery_line = f"🏪 Самовывоз: {escape(data['address'])}"
    else:
        delivery_line = f"🚚 Доставка: {escape(data['address'])}"

    return (
        f"🆕 <b>Новый заказ №{order_id}</b>\n\n"
        f"{format_items(items)}\n\n"
        f"💰 <b>Итого: {format_price(total)}</b>\n\n"
        f"👤 {escape(data['name'])}\n"
        f"📞 {escape(data['phone'])}\n"
        f"💬 {contact}\n"
        f"{delivery_line}"
    )


# ---------- Отмена и «Назад» (регистрируем первыми, чтобы сработали на любом шаге) ----------

@router.message(StateFilter(Checkout), F.text == BTN_CANCEL)
async def cancel_by_button(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer(
        "Оформление отменено. Ваша корзина сохранена 🛒",
        reply_markup=main_menu_kb(),
    )


@router.message(StateFilter(Checkout), F.text == BTN_BACK)
async def back_by_button(message: Message, state: FSMContext) -> None:
    await _go_back(message.bot, message.from_user.id, state)


@router.callback_query(StateFilter(Checkout), F.data == "order_cancel")
async def cancel_by_inline(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await callback.answer()
    await _remove_buttons(callback)
    await _say(
        callback,
        "Оформление отменено. Ваша корзина сохранена 🛒",
        reply_markup=main_menu_kb(),
    )


@router.callback_query(StateFilter(Checkout), F.data == "order_back")
async def back_by_inline(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    await _remove_buttons(callback)  # у этого сообщения кнопки больше не нужны
    await _go_back(callback.bot, callback.from_user.id, state)


# ---------- Шаг 0: старт оформления (кнопка в корзине) ----------

@router.callback_query(F.data == "checkout")
async def start_checkout(callback: CallbackQuery, state: FSMContext) -> None:
    items = await cart_db.get_cart(callback.from_user.id)
    if not items:
        await callback.answer("Корзина пуста", show_alert=True)
        return

    await callback.answer()
    await state.clear()
    await state.set_state(Checkout.name)
    await _say(
        callback,
        "📝 <b>Оформление заказа</b>\n\nКак вас зовут?",
        reply_markup=name_kb(),
    )


# ---------- Шаг 1: имя ----------

@router.message(Checkout.name, F.text)
async def got_name(message: Message, state: FSMContext) -> None:
    text = message.text.strip()
    if text in MENU_BUTTONS or text.startswith("/") or not 2 <= len(text) <= 50:
        await message.answer(
            "Пожалуйста, введите имя (от 2 до 50 символов) "
            "или воспользуйтесь кнопками «⬅️ Назад» и «❌ Отмена»."
        )
        return

    await state.update_data(name=text)
    await _ask_phone(
        message.bot,
        message.from_user.id,
        state,
        intro=f"Приятно познакомиться, <b>{escape(text)}</b>! 🙂\n\n",
    )


# ---------- Шаг 2: телефон ----------

async def _accept_phone(
    message: Message, state: FSMContext, raw: str, from_contact: bool = False
) -> None:
    phone = normalize_phone(raw, from_contact=from_contact)
    if phone is None:
        await message.answer(
            "Не получилось распознать номер 🤔\n\n"
            "Введите его полностью, например:\n"
            "<code>+7 999 123-45-67</code> или <code>8 999 123-45-67</code>\n\n"
            "Для номера другой страны начните с «+» и кода страны, "
            "например <code>+380 50 123 45 67</code>.\n"
            "Или нажмите «📱 Отправить мой номер»."
        )
        return

    await state.update_data(phone=phone)
    # Убираем нижнюю клавиатуру: дальше управляем кнопками под сообщениями
    await message.answer(
        f"📞 Номер принят: <b>{escape(phone)}</b>",
        reply_markup=ReplyKeyboardRemove(),
    )
    await _ask_delivery(message.bot, message.from_user.id, state)


@router.message(Checkout.phone, F.contact)
async def got_phone_contact(message: Message, state: FSMContext) -> None:
    await _accept_phone(message, state, message.contact.phone_number, from_contact=True)


@router.message(Checkout.phone, F.text)
async def got_phone_text(message: Message, state: FSMContext) -> None:
    await _accept_phone(message, state, message.text)


# ---------- Шаг 3: доставка или самовывоз ----------

@router.callback_query(Checkout.delivery, F.data.in_({"dlv_delivery", "dlv_pickup"}))
async def got_delivery(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()

    if callback.data == "dlv_pickup":
        await state.update_data(delivery_type="pickup", address=config.PICKUP_ADDRESS)
        await _replace_text(callback, "Способ получения: 🏪 Самовывоз")
        await _show_summary(callback.bot, callback.from_user.id, state)
    else:
        await state.update_data(delivery_type="delivery")
        await _replace_text(callback, "Способ получения: 🚚 Доставка")
        await _ask_address(callback.bot, callback.from_user.id, state)


# ---------- Шаг 4: адрес (только для доставки) ----------

@router.message(Checkout.address, F.text)
async def got_address(message: Message, state: FSMContext) -> None:
    text = message.text.strip()
    if text in MENU_BUTTONS or text.startswith("/") or not 5 <= len(text) <= 200:
        await message.answer(
            "Адрес должен быть от 5 до 200 символов. "
            "Введите его ещё раз или воспользуйтесь кнопками «⬅️ Назад» и «❌ Отмена»."
        )
        return

    await state.update_data(address=text)
    await _show_summary(message.bot, message.from_user.id, state)


# ---------- Шаг 5: подтверждение ----------

@router.callback_query(Checkout.confirm, F.data == "order_confirm")
async def confirm_order(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    data = await state.get_data()
    user = callback.from_user

    result = await orders_db.create_order(
        user_id=user.id,
        username=user.username,
        customer_name=data["name"],
        phone=data["phone"],
        delivery_type=data["delivery_type"],
        address=data["address"],
    )

    # Сразу сбрасываем состояние: повторное нажатие кнопки уже ничего не создаст
    await state.clear()
    await _remove_buttons(callback)

    if result is None:
        await _say(
            callback,
            "Ваша корзина оказалась пуста, заказ не создан.",
            reply_markup=main_menu_kb(),
        )
        return

    order_id, items, total = result

    # Сообщение клиенту (заодно возвращаем главное меню)
    await _say(
        callback,
        f"✅ <b>Заказ №{order_id} оформлен!</b>\n\n"
        "Спасибо за заказ! Мы свяжемся с вами по телефону, если понадобится "
        "что-то уточнить.\n"
        "Следить за статусом можно в разделе «📦 Мои заказы».",
        reply_markup=main_menu_kb(),
    )

    # Уведомление владельцу. Если не получилось, заказ всё равно сохранён.
    try:
        await callback.bot.send_message(
            config.ADMIN_ID, _admin_text(order_id, user, data, items, total)
        )
    except Exception as e:
        logging.error("Не удалось уведомить админа о заказе №%s: %s", order_id, e)


# ---------- Запасные обработчики (должны быть в самом конце файла) ----------

@router.message(StateFilter(Checkout))
async def unexpected_message(message: Message) -> None:
    """Сработает, если на шаге оформления прислали что-то неожиданное (фото, стикер...)."""
    await message.answer(
        "Пожалуйста, ответьте на вопрос выше или воспользуйтесь кнопками "
        "«⬅️ Назад» и «❌ Отмена»."
    )


@router.callback_query(
    F.data.in_({"dlv_delivery", "dlv_pickup", "order_confirm", "order_cancel", "order_back"})
)
async def stale_button(callback: CallbackQuery) -> None:
    """Кнопки от старого оформления (например, после перезапуска бота)."""
    await callback.answer("Это сообщение устарело.", show_alert=True)
    await _remove_buttons(callback)
    # Нижнее меню могло быть убрано во время оформления, возвращаем его
    await callback.bot.send_message(
        callback.from_user.id,
        "Это оформление заказа устарело (возможно, бот перезапускался). "
        "Откройте «🛒 Корзина» и оформите заказ заново.",
        reply_markup=main_menu_kb(),
    )