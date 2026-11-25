"""Запросы к базе для корзины."""
from database.db import get_db

MAX_QTY = 20  # максимум штук одного товара в корзине


async def add_item(user_id: int, product_id: int):
    """Добавляет 1 шт. товара в корзину.
    Возвращает (название, новое количество) или None, если товара нет или он скрыт."""
    async with get_db() as db:
        cursor = await db.execute(
            "SELECT name FROM products WHERE id = ? AND is_active = 1", (product_id,)
        )
        product = await cursor.fetchone()
        if product is None:
            return None

        # Если товара в корзине ещё нет, создаём строку с количеством 1,
        # если уже есть, увеличиваем количество (но не больше MAX_QTY)
        await db.execute(
            "INSERT INTO cart_items (user_id, product_id, quantity) VALUES (?, ?, 1) "
            "ON CONFLICT(user_id, product_id) "
            "DO UPDATE SET quantity = MIN(quantity + 1, ?)",
            (user_id, product_id, MAX_QTY),
        )
        cursor = await db.execute(
            "SELECT quantity FROM cart_items WHERE user_id = ? AND product_id = ?",
            (user_id, product_id),
        )
        (quantity,) = await cursor.fetchone()
        await db.commit()
        return product["name"], quantity


async def get_quantity(user_id: int, product_id: int) -> int:
    """Сколько штук этого товара уже в корзине пользователя (0, если нет)."""
    async with get_db() as db:
        cursor = await db.execute(
            "SELECT quantity FROM cart_items WHERE user_id = ? AND product_id = ?",
            (user_id, product_id),
        )
        row = await cursor.fetchone()
        return row["quantity"] if row else 0


async def get_cart(user_id: int):
    """Все товары в корзине пользователя (только те, что ещё есть в каталоге)."""
    async with get_db() as db:
        cursor = await db.execute(
            "SELECT p.id AS product_id, p.name, p.price, c.quantity "
            "FROM cart_items c "
            "JOIN products p ON p.id = c.product_id "
            "WHERE c.user_id = ? AND p.is_active = 1 "
            "ORDER BY c.rowid",
            (user_id,),
        )
        return await cursor.fetchall()


async def change_quantity(user_id: int, product_id: int, delta: int):
    """Меняет количество на delta (+1 или -1).
    Возвращает (новое количество, упёрлись_в_максимум) или None, если товара нет в корзине.
    Новое количество 0 означает, что товар удалён из корзины."""
    async with get_db() as db:
        cursor = await db.execute(
            "SELECT quantity FROM cart_items WHERE user_id = ? AND product_id = ?",
            (user_id, product_id),
        )
        row = await cursor.fetchone()
        if row is None:
            return None

        wanted = row["quantity"] + delta
        capped = wanted > MAX_QTY
        new_quantity = min(wanted, MAX_QTY)

        if new_quantity <= 0:
            await db.execute(
                "DELETE FROM cart_items WHERE user_id = ? AND product_id = ?",
                (user_id, product_id),
            )
            new_quantity = 0
        else:
            await db.execute(
                "UPDATE cart_items SET quantity = ? WHERE user_id = ? AND product_id = ?",
                (new_quantity, user_id, product_id),
            )
        await db.commit()
        return new_quantity, capped


async def remove_item(user_id: int, product_id: int) -> None:
    """Убирает товар из корзины целиком."""
    async with get_db() as db:
        await db.execute(
            "DELETE FROM cart_items WHERE user_id = ? AND product_id = ?",
            (user_id, product_id),
        )
        await db.commit()


async def clear_cart(user_id: int) -> None:
    """Полностью очищает корзину пользователя."""
    async with get_db() as db:
        await db.execute("DELETE FROM cart_items WHERE user_id = ?", (user_id,))
        await db.commit()