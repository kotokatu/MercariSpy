import sqlite3

conn = sqlite3.connect("mercari_products.db")

conn.execute("""
CREATE TABLE IF NOT EXISTS price_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    product_id TEXT NOT NULL,
    old_price INTEGER,
    new_price INTEGER,
    changed_at TEXT NOT NULL
)
""")

try:
    conn.execute(
        "ALTER TABLE products ADD COLUMN updated_at TEXT"
    )
except sqlite3.OperationalError:
    pass

conn.commit()
conn.close()

print("Migration completed")