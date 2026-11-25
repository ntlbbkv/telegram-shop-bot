"""Обработчик команды /start: приветствие и главное меню."""
from html import escape

from aiogram import Router
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

import config
from keyboards.main_menu import main_menu_kb

router = Router()


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext) -> None:
    # Сбрасываем любое незаконченное действие (например, оформление заказа)
    await state.clear()

    name = escape(message.from_user.full_name)
    shop = escape(config.SHOP_NAME)
    text = (
        f"Привет, <b>{name}</b>! 👋\n\n"
        f"Добро пожаловать в <b>{shop}</b>.\n"
        "Выберите раздел в меню ниже 👇"
    )

    # Подсказка только для администратора
    if message.from_user.id == config.ADMIN_ID:
        text += "\n\n🛠 Вы администратор. Панель управления заказами: /admin"

    await message.answer(text, reply_markup=main_menu_kb())