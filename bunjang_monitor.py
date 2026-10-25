#!/usr/bin/env python3.9
"""Bunjang monitor component, intended to run inside the existing Mercari process."""

import json
from pathlib import Path

from logging_config import get_logger
from product_storage import ProductStorage
from bunjang_scraper import BunjangScraper
from bunjang_notifier import BunjangTelegramNotifier


class BunjangMonitor:
    def __init__(self, config: dict, queries_path: str = "bunjang_queries.json"):
        self.config = config
        self.queries_path = Path(queries_path)
        self.logger = get_logger("BunjangMonitor")
        self.storage = ProductStorage(
            storage_path="bunjang.db",
            max_storage_days=config["storage"]["cleanup_after_days"],
        )
        self.scraper = BunjangScraper()
        self.notifier = BunjangTelegramNotifier(config)

    def load_search_queries(self) -> list:
        if not self.queries_path.exists():
            self.queries_path.write_text(
                json.dumps([{"keyword": "kolon"}], ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            self.logger.info("Created default Bunjang query file", path=str(self.queries_path))
        try:
            with self.queries_path.open(encoding="utf-8") as f:
                queries = json.load(f)
            if not isinstance(queries, list):
                raise ValueError("bunjang_queries.json must contain a JSON array")
            return queries
        except Exception as exc:
            self.logger.error("Failed to load Bunjang queries", error=str(exc))
            return []

    def process_query(self, query: dict) -> None:
        try:
            products = self.scraper.search_products(query)
            new_products = []
            price_changes = []

            for product in products:
                product_id = str(product["id"])
                stored = self.storage.get_product(product_id)

                if stored is None:
                    self.storage.add_product(product)
                    new_products.append(product)
                    continue

                old_price = stored["price"]
                new_price = product.get("price", 0)
                tracking = bool(stored["tracking"])
                price_change = self.storage.update_product(product)

                if (
                    tracking
                    and old_price is not None
                    and new_price < old_price
                    and price_change
                ):
                    price_changes.append(price_change)

            if new_products:
                self.notifier.send_notifications(new_products, query)
            if price_changes:
                self.notifier.send_price_change_notifications(price_changes, query)

            self.logger.info(
                "Processed Bunjang query",
                query=query,
                new_count=len(new_products),
                price_decrease_count=len(price_changes),
            )
        except Exception:
            self.logger.log_exception("Error processing Bunjang query", query=query)

    def run_once(self) -> None:
        queries = self.load_search_queries()
        if not queries:
            self.logger.warning("No Bunjang search queries configured")
            return

        for index, query in enumerate(queries):
            self.process_query(query)
            if index < len(queries) - 1:
                import time
                time.sleep(self.config["timing"]["search_delay"])

        removed = self.storage.cleanup_old_products()
        if removed:
            self.logger.info("Cleaned old Bunjang products", count=removed)

    def process_telegram_callback(self, update: dict) -> bool:
        callback = update.get("callback_query") or {}
        data = callback.get("data", "")
        if not (data.startswith("btrack:") or data.startswith("bstop:")):
            return False

        action, product_id = data.split(":", 1)
        callback_id = callback.get("id")
        tracking = action == "btrack"

        product = self.storage.get_product(product_id)
        product_url = product.get("url") if product else None

        updated = self.storage.set_tracking(product_id, tracking)
        if callback_id:
            if not updated:
                callback_text = "❌ Product is no longer in database"
            elif tracking:
                callback_text = "✅ Price tracking enabled"
            else:
                callback_text = "🛑 Price tracking disabled"
            self.notifier.answer_callback(callback_id, callback_text)

        if not updated:
            return True

        message = callback.get("message") or {}
        chat = message.get("chat") or {}
        message_id = message.get("message_id")
        if chat.get("id") is not None and message_id is not None:
            self.notifier.edit_tracking_buttons(
                chat_id=str(chat["id"]),
                message_id=message_id,
                product_id=product_id,
                tracking=tracking,
                product_url=product_url,
            )
        return True

    def close(self):
        try:
            self.storage.save_products()
        except Exception:
            pass
        try:
            self.storage.close()
        except Exception:
            pass
        try:
            self.scraper.close()
        except Exception:
            pass
