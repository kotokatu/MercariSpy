#!/usr/bin/env python3.9

"""
Mercari.jp Monitoring Tool

Main orchestrator for:
- Mercari search
- product storage
- new product notifications
- price tracking
- Telegram callback handling
"""

import argparse
import json
import time
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv

from logging_config import get_logger
from mercari_scraper import MercariScraper
from telegram_notifier import TelegramNotifier
from product_storage import ProductStorage


load_dotenv()

logger = get_logger(__name__)


class MercariMonitor:
    """
    Main orchestrator for Mercari monitoring.
    """

    def __init__(
        self,
        config_path: str = "config.json",
    ):
        self.config_path = Path(config_path)
        self.config = self.load_config()

        self.logger = get_logger("MercariMonitor")

        self.storage = ProductStorage(
            max_storage_days=self.config["storage"]["cleanup_after_days"]
        )

        self.scraper = MercariScraper(
            self.config
        )

        self.notifier = TelegramNotifier(
            self.config
        )

        self.telegram_offset: Optional[int] = None

        self.logger.info(
            "Mercari Monitor initialized"
        )

    # ------------------------------------------------------------------
    # Configuration
    # ------------------------------------------------------------------

    def load_config(self) -> dict:
        try:
            with open(
                self.config_path,
                "r",
                encoding="utf-8",
            ) as f:
                return json.load(f)

        except Exception as e:
            logger.error(
                "Failed to load config",
                error=str(e),
            )
            raise

    def load_search_queries(self) -> list:
        queries_file = Path("queries.json")

        try:
            if not queries_file.exists():
                self.logger.warning(
                    "queries.json not found, creating empty file"
                )

                queries_file.write_text(
                    "[]",
                    encoding="utf-8",
                )

                return []

            with open(
                queries_file,
                encoding="utf-8",
            ) as f:
                queries = json.load(f)

            self.logger.info(
                "Loaded search queries",
                query_count=len(queries),
            )

            return queries

        except Exception as e:
            self.logger.error(
                "Failed to load search queries",
                error=str(e),
            )

            return []

    # ------------------------------------------------------------------
    # Query processing
    # ------------------------------------------------------------------

    def process_query(
        self,
        query: dict,
    ) -> None:
        """
        Process one Mercari search query.

        New product:
            save -> notify

        Existing product:
            if tracking is enabled and price decreased:
                notify

            current price is always updated.
        """

        try:
            self.logger.info(
                "Processing query",
                query=query,
            )

            products = self.scraper.search_products(
                query
            )

            self.logger.debug(
                "Products found",
                count=len(products),
                query=query,
            )

            new_products = []
            price_changes = []

            for product in products:
                product_id = str(product["id"])

                stored_product = self.storage.get_product(
                    product_id
                )

                # ------------------------------------------------------
                # New product
                # ------------------------------------------------------

                if stored_product is None:
                    self.storage.add_product(
                        product
                    )

                    new_products.append(
                        product
                    )

                    continue

                # ------------------------------------------------------
                # Existing product
                # ------------------------------------------------------

                old_price = stored_product["price"]
                new_price = product.get("price", 0)

                tracking = bool(
                    stored_product["tracking"]
                )

                # Save current product data and price.
                price_change = self.storage.update_product(
                    product
                )

                # Notify only about price decreases for tracked items.
                if (
                    tracking
                    and old_price is not None
                    and new_price < old_price
                    and price_change
                ):
                    price_changes.append(
                        price_change
                    )

            # ----------------------------------------------------------
            # New product notifications
            # ----------------------------------------------------------

            if new_products:
                self.logger.info(
                    "New products found",
                    count=len(new_products),
                    query=query,
                )

                self.notifier.send_notifications(
                    new_products,
                    query,
                )

            # ----------------------------------------------------------
            # Price change notifications
            # ----------------------------------------------------------

            if price_changes:
                self.logger.info(
                    "Tracked price decreases found",
                    count=len(price_changes),
                    query=query,
                )

                self.notifier.send_price_change_notifications(
                    price_changes,
                    query,
                )

            if not new_products and not price_changes:
                self.logger.debug(
                    "Nothing changed",
                    query=query,
                )

        except Exception:
            self.logger.log_exception(
                "Error processing query",
                query=query,
            )

    # ------------------------------------------------------------------
    # Telegram callbacks
    # ------------------------------------------------------------------

    def process_telegram_updates(self) -> None:
        """
        Process Telegram callback queries.

        Supported callbacks:

            track:<product_id>
            stop:<product_id>
        """

        try:
            updates = self.notifier.get_updates(
                offset=self.telegram_offset,
                timeout=0,
            )

            for update in updates:
                update_id = update.get("update_id")

                if update_id is not None:
                    self.telegram_offset = update_id + 1

                parsed = self.notifier.parse_callback(
                    update
                )

                if not parsed:
                    continue

                action, product_id, callback_query_id = parsed

                # ------------------------------------------------------
                # Determine desired state
                # ------------------------------------------------------

                if action == "track":
                    tracking = True
                    callback_text = (
                        "✅ Price tracking enabled"
                    )

                elif action == "stop":
                    tracking = False
                    callback_text = (
                        "🛑 Price tracking disabled"
                    )

                else:
                    continue

                # ------------------------------------------------------
                # Update database
                # ------------------------------------------------------

                updated = self.storage.set_tracking(
                    product_id,
                    tracking,
                )

                if not updated:
                    self.notifier.answer_callback(
                        callback_query_id,
                        "❌ Product is no longer in database",
                    )

                    continue

                # ------------------------------------------------------
                # Answer callback immediately
                # ------------------------------------------------------

                self.notifier.answer_callback(
                    callback_query_id,
                    callback_text,
                )

                # ------------------------------------------------------
                # Update inline buttons
                # ------------------------------------------------------

                callback_message = update.get(
                    "callback_query",
                    {},
                ).get(
                    "message"
                )

                if not callback_message:
                    continue

                chat = callback_message.get(
                    "chat"
                )

                message_id = callback_message.get(
                    "message_id"
                )

                if not chat or not message_id:
                    continue

                chat_id = str(
                    chat["id"]
                )

                self.notifier.edit_tracking_buttons(
                    chat_id=chat_id,
                    message_id=message_id,
                    product_id=product_id,
                    tracking=tracking,
                )

                self.logger.info(
                    "Telegram tracking action processed",
                    action=action,
                    product_id=product_id,
                )

        except Exception:
            self.logger.log_exception(
                "Error processing Telegram updates"
            )

    # ------------------------------------------------------------------
    # Monitoring
    # ------------------------------------------------------------------

    def run_once(self) -> None:
        """
        Run one complete Mercari search cycle.
        """

        queries = self.load_search_queries()

        if not queries:
            self.logger.warning(
                "No search queries configured"
            )

            return

        self.logger.info(
            "Starting monitoring cycle"
        )

        for query in queries:
            # Check Telegram before every Mercari query.
            # This prevents callback requests from waiting
            # through the whole search cycle.
            self.process_telegram_updates()

            self.process_query(
                query
            )

            time.sleep(
                self.config["timing"]["search_delay"]
            )

        removed = self.storage.cleanup_old_products()

        if removed:
            self.logger.info(
                "Old products removed",
                count=removed,
            )

        self.logger.info(
            "Monitoring cycle completed"
        )

    def run_forever(self) -> None:
        """
        Run monitor continuously.

        Telegram callbacks are checked frequently between
        Mercari search cycles.
        """

        # Run the first search immediately.
        next_search = 0

        try:
            while True:
                # Telegram callbacks should be processed
                # independently from Mercari searches.
                self.process_telegram_updates()

                now = time.time()

                if now >= next_search:
                    self.run_once()

                    search_interval = (
                        self.config["timing"]["search_interval"]
                    )

                    next_search = (
                        time.time()
                        + search_interval
                    )

                # Short sleep keeps Telegram responsive
                # without busy-looping.
                time.sleep(1)

        except KeyboardInterrupt:
            self.logger.info(
                "Stopped by user"
            )

    # ------------------------------------------------------------------
    # Shutdown
    # ------------------------------------------------------------------

    def close(self):
        self.logger.info(
            "Closing Mercari Monitor"
        )

        try:
            self.storage.save_products()

        except Exception as e:
            self.logger.error(
                "Failed saving storage",
                error=str(e),
            )

        try:
            self.storage.close()

        except Exception:
            pass

        try:
            self.scraper.close()

        except Exception:
            pass

        self.logger.info(
            "Mercari Monitor closed"
        )


def main():
    parser = argparse.ArgumentParser(
        description="Mercari.jp product monitor"
    )

    parser.add_argument(
        "--config",
        default="config.json",
        help="Configuration file path",
    )

    args = parser.parse_args()

    monitor = None

    try:
        monitor = MercariMonitor(
            args.config
        )

        monitor.run_forever()

    except KeyboardInterrupt:
        logger.info(
            "Stopped by user"
        )

    except Exception:
        logger.log_exception(
            "Fatal error in main"
        )

    finally:
        if monitor:
            monitor.close()


if __name__ == "__main__":
    main()