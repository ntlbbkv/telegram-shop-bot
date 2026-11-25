"""Кнопки оформления заказа."""
from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
)

BTN_CANCEL = "❌ Отмена"
BTN_BACK = "⬅️ Назад"
BTN_SEND_PHONE = "📱 Отправить мой номер"


def name_kb() -> ReplyKeyboardMarkup:
    """Шаг «Имя»: вместо главного меню показываем «Назад» (в корзину) и «Отмена»."""
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=BTN_BACK), KeyboardButton(text=BTN_CANCEL)]],
        resize_keyboard=True,
    )


def phone_kb() -> ReplyKeyboardMarkup:
    """Шаг «Телефон»: «Отправить номер» (Telegram сам подставит номер), «Назад» и «Отмена».
    Кнопку «Отправить номер» Telegram позволяет делать только на нижней клавиатуре."""
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=BTN_SEND_PHONE, request_contact=True)],
            [KeyboardButton(text=BTN_BACK), KeyboardButton(text=BTN_CANCEL)],
        ],
        resize_keyboard=True,
        input_field_placeholder="Или введите номер вручную",
    )


def nav_kb() -> InlineKeyboardMarkup:
    """Кнопки «Назад» и «Отмена» под сообщением (шаг «Адрес»)."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text=BTN_BACK, callback_data="order_back"),
                InlineKeyboardButton(text=BTN_CANCEL, callback_data="order_cancel"),
            ]
        ]
    )


def delivery_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🚚 Доставка", callback_data="dlv_delivery")],
            [InlineKeyboardButton(text="🏪 Самовывоз", callback_data="dlv_pickup")],
            [
                InlineKeyboardButton(text=BTN_BACK, callback_data="order_back"),
                InlineKeyboardButton(text=BTN_CANCEL, callback_data="order_cancel"),
            ],
        ]
    )


def confirm_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="✅ Подтвердить заказ", callback_data="order_confirm")],
            [
                InlineKeyboardButton(text=BTN_BACK, callback_data="order_back"),
                InlineKeyboardButton(text=BTN_CANCEL, callback_data="order_cancel"),
            ],
        ]
    )