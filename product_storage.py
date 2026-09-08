#!/usr/bin/env python3.9

import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from logging_config import get_logger


class ProductStorage:
    """
    SQLite storage for Mercari products.

    Stores:
    - product information
    - current price
    - price history
    - price tracking status
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
        """
        Create database tables if they don't exist.

        Existing databases are migrated separately by migrate_db.py.
        """

        self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS products (
                id TEXT PRIMARY KEY,
                title TEXT,
                price INTEGER,
                url TEXT,
                image_url TEXT,
                added_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                tracking INTEGER NOT NULL DEFAULT 0
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

    def get_product(
        self,
        product_id: str,
    ) -> Optional[dict]:
        """
        Return product by Mercari ID.

        Returns None if the product is not known.
        """

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

    def is_product_known(
        self,
        product_id: str,
    ) -> bool:
        """
        Check whether product is already stored.
        """

        return self.get_product(product_id) is not None

    def add_product(
        self,
        product: dict,
    ):
        """
        Add a new product.

        Existing products are not overwritten.
        New products are not tracked by default.
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
                    updated_at,
                    tracking
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    str(product["id"]),
                    product.get("title", ""),
                    product.get("price", 0),
                    product.get("url", ""),
                    product.get("image_url", ""),
                    now,
                    now,
                    0,
                ),
            )

            self.conn.commit()

        except Exception as e:
            self.logger.error(
                "Failed adding product",
                error=str(e),
            )

    def update_product(
        self,
        product: dict,
    ) -> Optional[dict]:
        """
        Update an existing product.

        The current price is always stored.

        If the price changed, a record is added to price_history.

        Returns price change information if the price changed,
        otherwise None.
        """

        product_id = str(product["id"])

        old_product = self.get_product(product_id)

        if not old_product:
            self.add_product(product)
            return None

        old_price = old_product["price"]
        new_price = product.get("price", 0)

        now = datetime.now().isoformat()

        if old_price != new_price:

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

        if old_price == new_price:
            return None

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

    # ------------------------------------------------------------------
    # Price tracking
    # ------------------------------------------------------------------

    def set_tracking(
        self,
        product_id: str,
        tracking: bool,
    ) -> bool:
        """
        Enable or disable price tracking for a product.

        Returns True if the product exists and was updated.
        """

        product_id = str(product_id)

        cursor = self.conn.execute(
            """
            UPDATE products
            SET tracking = ?
            WHERE id = ?
            """,
            (
                1 if tracking else 0,
                product_id,
            ),
        )

        self.conn.commit()

        if cursor.rowcount == 0:
            self.logger.warning(
                "Cannot change tracking for unknown product",
                product_id=product_id,
                tracking=tracking,
            )

            return False

        self.logger.info(
            "Product tracking changed",
            product_id=product_id,
            tracking=tracking,
        )

        return True

    def is_tracking(
        self,
        product_id: str,
    ) -> bool:
        """
        Return True if price tracking is enabled for the product.
        """

        product = self.get_product(product_id)

        if not product:
            return False

        return bool(product["tracking"])

    # ------------------------------------------------------------------
    # Cleanup
    # ------------------------------------------------------------------

    def cleanup_old_products(self):
        """
        Remove old products that are not being tracked.

        Tracked products are kept regardless of their age.
        """

        cutoff = (
            datetime.now()
            - timedelta(days=self.max_storage_days)
        ).isoformat()

        cursor = self.conn.execute(
            """
            DELETE FROM products
            WHERE added_at < ?
              AND tracking = 0
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
        SQLite commits changes immediately, but this keeps
        compatibility with the existing application.
        """

        self.conn.commit()

    def close(self):
        """
        Close database connection.
        """

        try:
            self.conn.close()
        except Exception:
            pass