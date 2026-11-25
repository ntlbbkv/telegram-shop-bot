"""Каталог: список категорий, карточки товаров, листание, добавление в корзину."""
from html import escape
from pathlib import Path

from aiogram import F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import (
    CallbackQuery,
    FSInputFile,
    InlineKeyboardMarkup,
    InputMediaPhoto,
    Message,
)

from database import cart as cart_db
from database import products as db
from keyboards.catalog import (
    AddToCartCb,
    CategoryCb,
    ChangeQtyCb,
    PageCb,
    categories_kb,
    product_kb,
)
from keyboards.main_menu import BTN_CATALOG
from utils import find_product_photo, format_price

router = Router()

# Память бота: файл фото -> его id в Telegram.
# Первый раз фото загружается с компьютера, потом Telegram отдаёт его мгновенно по id.
# После перезапуска бота память очищается, это нормально.
_file_ids: dict[str, str] = {}


def _photo_source(path: Path):
    return _file_ids.get(str(path)) or FSInputFile(path)


def _remember_photo(path: Path, sent) -> None:
    if isinstance(sent, Message) and sent.photo:
        _file_ids[str(path)] = sent.photo[-1].file_id


def _card_text(product, in_cart: int = 0) -> str:
    text = (
        f"<b>{escape(product['name'])}</b>\n\n"
        f"{escape(product['description'])}\n\n"
        f"💰 <b>{format_price(product['price'])}</b>"
    )
    if in_cart > 0:
        text += (
            f"\n\n🛒 В корзине: <b>{in_cart} шт.</b>\n"
            "<i>Открыть корзину можно кнопкой «🛒 Корзина» в главном меню внизу.</i>"
        )
    return text


async def _get_message(callback: CallbackQuery) -> Message | None:
    """Telegram не даёт редактировать слишком старые сообщения, проверяем это."""
    message = callback.message
    if isinstance(message, Message):
        return message
    await callback.answer("Сообщение устарело. Нажмите «🛍 Каталог» ещё раз.", show_alert=True)
    return None


async def _show_text(message: Message, text: str, kb: InlineKeyboardMarkup) -> None:
    """Показывает текст на месте текущего сообщения."""
    if message.photo:
        # Фото-сообщение нельзя превратить в текстовое, поэтому удаляем и отправляем новое
        await message.delete()
        await message.answer(text, reply_markup=kb)
    else:
        await message.edit_text(text, reply_markup=kb)


async def _show_product(message: Message, user_id: int, category_id: int, page: int) -> None:
    """Показывает карточку товара на месте текущего сообщения."""
    total = await db.count_products(category_id)
    if total == 0:
        categories = await db.get_categories()
        await _show_text(message, "В этой категории пока нет товаров.", categories_kb(categories))
        return

    page %= total  # листание по кругу: после последнего снова первый
    product = await db.get_product_by_offset(category_id, page)
    in_cart = await cart_db.get_quantity(user_id, product["id"])

    text = _card_text(product, in_cart)
    kb = product_kb(category_id, page, total, product["id"], in_cart)
    photo_path = find_product_photo(product["id"], product["photo"])

    try:
        if photo_path and message.photo:
            # Было фото -> стало фото: плавно подменяем картинку и подпись
            sent = await message.edit_media(
                InputMediaPhoto(media=_photo_source(photo_path), caption=text, parse_mode="HTML"),
                reply_markup=kb,
            )
        elif not photo_path and not message.photo:
            # Было без фото -> стало без фото: меняем текст
            sent = await message.edit_text(text, reply_markup=kb)
        else:
            # Тип сообщения меняется (текст <-> фото): удаляем старое и шлём новое
            await message.delete()
            if photo_path:
                sent = await message.answer_photo(
                    photo=_photo_source(photo_path), caption=text, reply_markup=kb
                )
            else:
                sent = await message.answer(text, reply_markup=kb)
    except TelegramBadRequest as e:
        # Такое бывает, если содержимое не изменилось, это не ошибка
        if "message is not modified" not in str(e):
            raise
    else:
        if photo_path:
            _remember_photo(photo_path, sent)


async def _update_card(
    message: Message, user_id: int, product_id: int, category_id: int, page: int
) -> None:
    """Обновляет подпись и кнопки карточки на месте. Фото при этом не перезагружается."""
    product = await db.get_product(product_id)
    total = await db.count_products(category_id)
    if product is None or total == 0:
        return

    page %= total
    in_cart = await cart_db.get_quantity(user_id, product_id)
    text = _card_text(product, in_cart)
    kb = product_kb(category_id, page, total, product_id, in_cart)

    try:
        if message.photo:
            await message.edit_caption(caption=text, reply_markup=kb)
        else:
            await message.edit_text(text, reply_markup=kb)
    except TelegramBadRequest as e:
        # Например, нажали кнопку, а текст не изменился: это не ошибка
        if "message is not modified" not in str(e):
            raise


# ---------- Обработчики ----------

@router.message(F.text == BTN_CATALOG)
async def open_catalog(message: Message) -> None:
    categories = await db.get_categories()
    if not categories:
        await message.answer("Каталог пока пуст 😔")
        return
    await message.answer("Выберите категорию:", reply_markup=categories_kb(categories))


@router.callback_query(F.data == "cats")
async def back_to_categories(callback: CallbackQuery) -> None:
    message = await _get_message(callback)
    if message is None:
        return
    categories = await db.get_categories()
    await _show_text(message, "Выберите категорию:", categories_kb(categories))
    await callback.answer()


@router.callback_query(CategoryCb.filter())
async def open_category(callback: CallbackQuery, callback_data: CategoryCb) -> None:
    message = await _get_message(callback)
    if message is None:
        return
    await _show_product(message, callback.from_user.id, callback_data.id, 0)
    await callback.answer()


@router.callback_query(PageCb.filter())
async def turn_page(callback: CallbackQuery, callback_data: PageCb) -> None:
    message = await _get_message(callback)
    if message is None:
        return
    await _show_product(message, callback.from_user.id, callback_data.category_id, callback_data.page)
    await callback.answer()


@router.callback_query(AddToCartCb.filter())
async def add_to_cart(callback: CallbackQuery, callback_data: AddToCartCb) -> None:
    """Кнопка «🛒 В корзину»: добавляет 1 шт., кнопки на карточке меняются на ➖ и ➕."""
    user_id = callback.from_user.id

    result = await cart_db.add_item(user_id, callback_data.product_id)
    if result is None:
        await callback.answer("Этот товар больше недоступен", show_alert=True)
        return

    name, quantity = result
    await callback.answer(f"✅ {name}: в корзине {quantity} шт.")

    message = callback.message
    if isinstance(message, Message):
        await _update_card(
            message, user_id, callback_data.product_id, callback_data.category_id, callback_data.page
        )


@router.callback_query(ChangeQtyCb.filter())
async def change_qty(callback: CallbackQuery, callback_data: ChangeQtyCb) -> None:
    """Кнопки ➖ и ➕ на карточке: меняют количество товара в корзине на 1."""
    user_id = callback.from_user.id
    product_id = callback_data.product_id

    if callback_data.action == "inc":
        current = await cart_db.get_quantity(user_id, product_id)
        if current >= cart_db.MAX_QTY:
            await callback.answer(
                f"Максимум {cart_db.MAX_QTY} шт. одного товара", show_alert=True
            )
            return

        result = await cart_db.add_item(user_id, product_id)
        if result is None:
            await callback.answer("Этот товар больше недоступен", show_alert=True)
            return
        await callback.answer()
    else:
        result = await cart_db.change_quantity(user_id, product_id, -1)
        if result is not None and result[0] == 0:
            await callback.answer("Товар убран из корзины")
        else:
            await callback.answer()

    message = callback.message
    if isinstance(message, Message):
        await _update_card(message, user_id, product_id, callback_data.category_id, callback_data.page)


@router.callback_query(F.data.startswith("add:"))
async def stale_add_button(callback: CallbackQuery) -> None:
    """Кнопка «В корзину» со старой карточки (до обновления бота)."""
    await callback.answer("Карточка устарела. Откройте каталог заново.", show_alert=True)


@router.callback_query(F.data == "noop")
async def page_counter_pressed(callback: CallbackQuery) -> None:
    """Кнопки «1 / 6» и «🛒 2 шт.» ничего не делают, просто убираем «часики» на кнопке."""
    await callback.answer()