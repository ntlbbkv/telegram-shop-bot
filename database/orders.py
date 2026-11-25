"""Запросы к базе для заказов."""
from database.db import get_db


async def create_order(
    *,
    user_id: int,
    username: str | None,
    customer_name: str,
    phone: str,
    delivery_type: str,
    address: str,
):
    """Создаёт заказ из корзины пользователя и очищает корзину.
    Возвращает (номер_заказа, позиции, итоговая_сумма) или None, если корзина пуста."""
    async with get_db() as db:
        # Цены берём из базы прямо сейчас, а не из памяти бота, чтобы их нельзя было подменить
        cursor = await db.execute(
            "SELECT p.id AS product_id, p.name, p.price, c.quantity "
            "FROM cart_items c "
            "JOIN products p ON p.id = c.product_id "
            "WHERE c.user_id = ? AND p.is_active = 1 "
            "ORDER BY c.rowid",
            (user_id,),
        )
        rows = await cursor.fetchall()
        if not rows:
            return None

        items = [dict(row) for row in rows]
        total = sum(item["price"] * item["quantity"] for item in items)

        cursor = await db.execute(
            "INSERT INTO orders "
            "(user_id, username, customer_name, phone, delivery_type, address, total) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (user_id, username, customer_name, phone, delivery_type, address, total),
        )
        order_id = cursor.lastrowid

        await db.executemany(
            "INSERT INTO order_items (order_id, product_id, name, price, quantity) "
            "VALUES (?, ?, ?, ?, ?)",
            [
                (order_id, item["product_id"], item["name"], item["price"], item["quantity"])
                for item in items
            ],
        )

        await db.execute("DELETE FROM cart_items WHERE user_id = ?", (user_id,))
        await db.commit()
        return order_id, items, total


async def get_user_orders(user_id: int, limit: int = 10):
    """Последние заказы клиента, новые сверху."""
    async with get_db() as db:
        cursor = await db.execute(
            "SELECT id, total, status, created_at "
            "FROM orders WHERE user_id = ? "
            "ORDER BY id DESC LIMIT ?",
            (user_id, limit),
        )
        return await cursor.fetchall()


async def get_user_order(order_id: int, user_id: int):
    """Один заказ клиента. Чужой заказ не вернётся, даже если подставить его номер."""
    async with get_db() as db:
        cursor = await db.execute(
            "SELECT * FROM orders WHERE id = ? AND user_id = ?",
            (order_id, user_id),
        )
        return await cursor.fetchone()


async def get_order_items(order_id: int):
    """Позиции заказа (название и цена на момент заказа)."""
    async with get_db() as db:
        cursor = await db.execute(
            "SELECT name, price, quantity FROM order_items WHERE order_id = ? ORDER BY id",
            (order_id,),
        )
        return await cursor.fetchall()


# ---------- Для админ-панели ----------

async def get_status_counts() -> dict[str, int]:
    """Сколько заказов в каждом статусе: {'new': 2, 'ready': 1, ...}."""
    async with get_db() as db:
        cursor = await db.execute("SELECT status, COUNT(*) AS n FROM orders GROUP BY status")
        rows = await cursor.fetchall()
        return {row["status"]: row["n"] for row in rows}


async def count_orders(status: str | None = None) -> int:
    """Сколько заказов всего или в указанном статусе."""
    async with get_db() as db:
        if status is None:
            cursor = await db.execute("SELECT COUNT(*) FROM orders")
        else:
            cursor = await db.execute("SELECT COUNT(*) FROM orders WHERE status = ?", (status,))
        (count,) = await cursor.fetchone()
        return count


async def get_orders_page(status: str | None, limit: int, offset: int):
    """Страница заказов для админа, новые сверху. status=None означает «все»."""
    async with get_db() as db:
        if status is None:
            cursor = await db.execute(
                "SELECT id, customer_name, total, status FROM orders "
                "ORDER BY id DESC LIMIT ? OFFSET ?",
                (limit, offset),
            )
        else:
            cursor = await db.execute(
                "SELECT id, customer_name, total, status FROM orders "
                "WHERE status = ? ORDER BY id DESC LIMIT ? OFFSET ?",
                (status, limit, offset),
            )
        return await cursor.fetchall()


async def get_order(order_id: int):
    """Любой заказ по номеру (только для админа)."""
    async with get_db() as db:
        cursor = await db.execute("SELECT * FROM orders WHERE id = ?", (order_id,))
        return await cursor.fetchone()


async def set_order_status(order_id: int, status: str) -> bool:
    """Меняет статус заказа. Возвращает False, если заказа нет или статус уже такой."""
    async with get_db() as db:
        cursor = await db.execute(
            "UPDATE orders SET status = ? WHERE id = ? AND status != ?",
            (status, order_id, status),
        )
        await db.commit()
        return cursor.rowcount > 0