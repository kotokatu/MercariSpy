#!/usr/bin/env python3.9

import sqlite3


DB_PATH = "mercari_products.db"


def column_exists(
    conn: sqlite3.Connection,
    table_name: str,
    column_name: str,
) -> bool:
    cursor = conn.execute(
        f"PRAGMA table_info({table_name})"
    )

    columns = cursor.fetchall()

    return any(
        column[1] == column_name
        for column in columns
    )


def main():
    conn = sqlite3.connect(DB_PATH)

    try:
        # ----------------------------------------------------------
        # products.updated_at
        # ----------------------------------------------------------

        if not column_exists(
            conn,
            "products",
            "updated_at",
        ):
            conn.execute(
                """
                ALTER TABLE products
                ADD COLUMN updated_at TEXT
                """
            )

            print("Added products.updated_at")

        # ----------------------------------------------------------
        # products.tracking
        # ----------------------------------------------------------

        if not column_exists(
            conn,
            "products",
            "tracking",
        ):
            conn.execute(
                """
                ALTER TABLE products
                ADD COLUMN tracking INTEGER NOT NULL DEFAULT 0
                """
            )

            print("Added products.tracking")

        # ----------------------------------------------------------
        # price_history
        # ----------------------------------------------------------

        conn.execute(
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

        conn.commit()

        print("Migration completed")

    finally:
        conn.close()


if __name__ == "__main__":
    main()