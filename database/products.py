"""Запросы к базе для каталога: категории и товары."""
from database.db import get_db


async def get_categories():
    """Все категории по порядку."""
    async with get_db() as db:
        cursor = await db.execute(
            "SELECT id, name FROM categories ORDER BY sort_order, id"
        )
        return await cursor.fetchall()


async def count_products(category_id: int) -> int:
    """Сколько активных товаров в категории."""
    async with get_db() as db:
        cursor = await db.execute(
            "SELECT COUNT(*) FROM products WHERE category_id = ? AND is_active = 1",
            (category_id,),
        )
        (count,) = await cursor.fetchone()
        return count


async def get_product_by_offset(category_id: int, offset: int):
    """Один товар категории по порядковому номеру (0 - первый, 1 - второй и т.д.)."""
    async with get_db() as db:
        cursor = await db.execute(
            "SELECT id, name, description, price, photo "
            "FROM products "
            "WHERE category_id = ? AND is_active = 1 "
            "ORDER BY id LIMIT 1 OFFSET ?",
            (category_id, offset),
        )
        return await cursor.fetchone()


async def get_product(product_id: int):
    """Один товар по номеру (только если он виден в каталоге)."""
    async with get_db() as db:
        cursor = await db.execute(
            "SELECT id, name, description, price, photo "
            "FROM products WHERE id = ? AND is_active = 1",
            (product_id,),
        )
        return await cursor.fetchone()