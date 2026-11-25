"""Работа с базой данных SQLite: подключение, создание таблиц, демо-данные."""
import logging
from contextlib import asynccontextmanager

import aiosqlite

import config

# Статусы заказа: 'new' -> 'processing' -> 'ready' -> 'completed' (или 'cancelled')
SCHEMA = """
CREATE TABLE IF NOT EXISTS categories (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    name       TEXT NOT NULL,
    sort_order INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS products (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    category_id INTEGER NOT NULL REFERENCES categories(id) ON DELETE CASCADE,
    name        TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    price       INTEGER NOT NULL,          -- цена целым числом (в рублях)
    photo       TEXT,                      -- имя файла фото или NULL, если фото нет
    is_active   INTEGER NOT NULL DEFAULT 1 -- 1 = виден в каталоге, 0 = скрыт
);

CREATE TABLE IF NOT EXISTS cart_items (
    user_id    INTEGER NOT NULL,
    product_id INTEGER NOT NULL REFERENCES products(id) ON DELETE CASCADE,
    quantity   INTEGER NOT NULL DEFAULT 1,
    PRIMARY KEY (user_id, product_id)
);

CREATE TABLE IF NOT EXISTS orders (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id       INTEGER NOT NULL,
    username      TEXT,
    customer_name TEXT NOT NULL,
    phone         TEXT NOT NULL,
    delivery_type TEXT NOT NULL,           -- 'delivery' или 'pickup'
    address       TEXT,
    total         INTEGER NOT NULL,
    status        TEXT NOT NULL DEFAULT 'new',
    created_at    TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS order_items (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id   INTEGER NOT NULL REFERENCES orders(id) ON DELETE CASCADE,
    product_id INTEGER,
    name       TEXT NOT NULL,
    price      INTEGER NOT NULL,
    quantity   INTEGER NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_products_category ON products(category_id);
CREATE INDEX IF NOT EXISTS idx_orders_user ON orders(user_id);
"""

# Демо-каталог: (категория, название, описание, цена)
DEMO_CATEGORIES = ["Кофе", "Чай", "Десерты"]

DEMO_PRODUCTS = [
    ("Кофе", "Эспрессо", "Классический крепкий кофе, 30 мл.", 150),
    ("Кофе", "Американо", "Эспрессо с горячей водой, 250 мл.", 180),
    ("Кофе", "Капучино", "Эспрессо с воздушной молочной пенкой, 250 мл.", 220),
    ("Кофе", "Латте", "Нежный кофе с большим количеством молока, 300 мл.", 240),
    ("Кофе", "Раф", "Сливочный кофе с ванильным сахаром, 300 мл.", 280),
    ("Кофе", "Флэт уайт", "Двойной эспрессо с бархатным молоком, 200 мл.", 260),
    ("Чай", "Зелёный чай", "Листовой зелёный чай, чайничек 500 мл.", 170),
    ("Чай", "Чёрный чай", "Крепкий чёрный чай с бергамотом, 500 мл.", 170),
    ("Чай", "Имбирный чай", "Имбирь, лимон и мёд, 500 мл.", 210),
    ("Чай", "Матча латте", "Японский порошковый чай с молоком, 300 мл.", 290),
    ("Десерты", "Чизкейк", "Классический Нью-Йорк с ягодным соусом, 120 г.", 320),
    ("Десерты", "Круассан", "Свежий круассан с миндальным кремом, 90 г.", 190),
    ("Десерты", "Эклер", "Заварное пирожное с ванильным кремом, 80 г.", 160),
    ("Десерты", "Тирамису", "Итальянский десерт с маскарпоне, 130 г.", 340),
]


@asynccontextmanager
async def get_db():
    """Открывает соединение с базой. Использование:  async with get_db() as db: ..."""
    async with aiosqlite.connect(config.DB_PATH) as db:
        db.row_factory = aiosqlite.Row            # строки доступны по имени колонки
        await db.execute("PRAGMA foreign_keys = ON")  # включаем проверку связей
        yield db


async def init_db() -> None:
    """Создаёт папку и таблицы, при первом запуске добавляет демо-товары."""
    config.DB_PATH.parent.mkdir(parents=True, exist_ok=True)

    async with get_db() as db:
        await db.executescript(SCHEMA)

        cursor = await db.execute("SELECT COUNT(*) FROM categories")
        (count,) = await cursor.fetchone()

        if count == 0:
            category_ids = {}
            for order, name in enumerate(DEMO_CATEGORIES):
                cursor = await db.execute(
                    "INSERT INTO categories (name, sort_order) VALUES (?, ?)",
                    (name, order),
                )
                category_ids[name] = cursor.lastrowid

            for category, name, description, price in DEMO_PRODUCTS:
                await db.execute(
                    "INSERT INTO products (category_id, name, description, price) "
                    "VALUES (?, ?, ?, ?)",
                    (category_ids[category], name, description, price),
                )
            logging.info("Добавлены демо-категории и товары")

        await db.commit()

    logging.info("База данных готова: %s", config.DB_PATH)