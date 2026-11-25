"""Точка входа: запуск бота-магазина."""
import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

import config
from database.db import init_db
from handlers import admin, cart, catalog, checkout, orders, start


async def on_startup(bot: Bot) -> None:
    """Выполняется один раз при запуске: сообщает админу, что бот работает."""
    try:
        await bot.send_message(config.ADMIN_ID, "✅ Бот-магазин запущен\nПанель администратора: /admin")
    except Exception as e:
        # Если админ ещё не нажимал /start у этого бота, Telegram не даст написать первым
        logging.warning("Не удалось отправить сообщение админу: %s", e)


async def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )

    # Создаём таблицы (если их ещё нет) и заполняем демо-данными
    await init_db()

    bot = Bot(
        token=config.BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dp = Dispatcher()

    # Подключаем роутеры. Порядок важен: Telegram проверяет их сверху вниз.
    dp.include_router(start.router)
    dp.include_router(admin.router)
    dp.include_router(checkout.router)
    dp.include_router(catalog.router)
    dp.include_router(cart.router)
    dp.include_router(orders.router)

    dp.startup.register(on_startup)

    # Сбрасываем накопившиеся, пока бот был выключен, сообщения
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logging.info("Бот остановлен")