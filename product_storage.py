#!/usr/bin/env python3.9

import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Optional

from logging_config import get_logger


class ProductStorage:
    """
    SQLite storage for Mercari products.
    """

    def __init__(
        self,
        storage_path: str = "mercari_products.db",
        max_storage_days: int = 7,
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
                added_at TEXT NOT NULL
            )
            """
        )

        self.conn.commit()


    def is_product_known(self, product_id: str) -> bool:
        cursor = self.conn.execute(
            """
            SELECT 1 FROM products WHERE id = ?
            """,
            (str(product_id),),
        )

        return cursor.fetchone() is not None


    def add_product(self, product: dict):
        """
        Add product if it does not exist.
        """
        product_id = str(product["id"])

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
                    added_at
                )
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    product_id,
                    product.get("title", ""),
                    product.get("price", 0),
                    product.get("url", ""),
                    product.get("image_url", ""),
                    datetime.now().isoformat(),
                ),
            )

            self.conn.commit()

        except Exception as e:
            self.logger.error(
                "Failed adding product",
                error=str(e),
            )


    def get_product(self, product_id: str) -> Optional[dict]:
        cursor = self.conn.execute(
            """
            SELECT * FROM products WHERE id = ?
            """,
            (str(product_id),),
        )

        row = cursor.fetchone()

        if row:
            return dict(row)

        return None


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
        SQLite commits immediately.
        """
        self.conn.commit()


    def close(self):
        try:
            self.conn.close()
        except Exception:
            pass