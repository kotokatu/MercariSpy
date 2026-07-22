#!/usr/bin/env python3.9

import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from logging_config import get_logger


class ProductStorage:
    """
    SQLite storage for Mercari products.
    Tracks products and price changes.
    """

    def __init__(
        self,
        storage_path: str = "mercari_products.db",
        max_storage_days: int = 365,
    ):
        self.storage_path = Path(storage_path)
        self.logger = get_logger("ProductStorage")
        self.max_storage_days = max_storage_days

        self.conn = sqlite3.connect(
            self.storage_path,
            timeout=30,
        )

        self.conn.row_factory = sqlite3.Row

        self._create_tables()

        self.logger.info(
            "SQLite storage initialized",
            path=str(self.storage_path.absolute()),
        )


    def _create_tables(self):
        self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS products (
                id TEXT PRIMARY KEY,
                title TEXT,
                price INTEGER,
                url TEXT,
                image_url TEXT,
                added_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )

        self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS price_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                product_id TEXT NOT NULL,
                old_price INTEGER,
                new_price INTEGER,
                changed_at TEXT NOT NULL
            )
            """
        )

        self.conn.commit()


    def get_product(self, product_id: str) -> Optional[dict]:
        cursor = self.conn.execute(
            """
            SELECT *
            FROM products
            WHERE id = ?
            """,
            (str(product_id),),
        )

        row = cursor.fetchone()

        return dict(row) if row else None


    def is_product_known(self, product_id: str) -> bool:
        return self.get_product(product_id) is not None


    def add_product(self, product: dict):
        """
        Add new product.
        Existing products are not overwritten.
        """

        now = datetime.now().isoformat()

        try:
            self.conn.execute(
                """
                INSERT OR IGNORE INTO products
                (
                    id,
                    title,
                    price,
                    url,
                    image_url,
                    added_at,
                    updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    str(product["id"]),
                    product.get("title", ""),
                    product.get("price", 0),
                    product.get("url", ""),
                    product.get("image_url", ""),
                    now,
                    now,
                ),
            )

            self.conn.commit()

        except Exception as e:
            self.logger.error(
                "Failed adding product",
                error=str(e),
            )


    def update_product_price(self, product: dict) -> Optional[dict]:
        """
        Update price if changed.
        Returns old/new price info or None.
        """

        product_id = str(product["id"])
        old_product = self.get_product(product_id)

        if not old_product:
            self.add_product(product)
            return None


        old_price = old_product["price"]
        new_price = product.get("price", 0)


        if old_price - new_price < 1000:
            return None


        now = datetime.now().isoformat()


        self.conn.execute(
            """
            INSERT INTO price_history
            (
                product_id,
                old_price,
                new_price,
                changed_at
            )
            VALUES (?, ?, ?, ?)
            """,
            (
                product_id,
                old_price,
                new_price,
                now,
            ),
        )


        self.conn.execute(
            """
            UPDATE products
            SET
                price = ?,
                title = ?,
                url = ?,
                image_url = ?,
                updated_at = ?
            WHERE id = ?
            """,
            (
                new_price,
                product.get("title", ""),
                product.get("url", ""),
                product.get("image_url", ""),
                now,
                product_id,
            ),
        )


        self.conn.commit()


        self.logger.info(
            "Product price changed",
            product_id=product_id,
            old_price=old_price,
            new_price=new_price,
        )


        return {
            "id": product_id,
            "title": product.get("title", ""),
            "old_price": old_price,
            "new_price": new_price,
            "url": product.get("url", ""),
            "image_url": product.get("image_url", ""),
        }


    def cleanup_old_products(self):

        cutoff = (
            datetime.now() -
            timedelta(days=self.max_storage_days)
        ).isoformat()


        cursor = self.conn.execute(
            """
            DELETE FROM products
            WHERE added_at < ?
            """,
            (cutoff,),
        )

        self.conn.commit()

        removed = cursor.rowcount


        if removed:
            self.logger.info(
                "Cleaned old products",
                count=removed,
            )

        return removed


    def save_products(self):
        """
        Compatibility method.
        """
        self.conn.commit()


    def close(self):
        try:
            self.conn.close()
        except Exception:
            pass