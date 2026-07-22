#!/usr/bin/env python3.9
"""
Mercari.jp Monitoring Tool
Main orchestrator for automated product monitoring and notification system.
"""

import json
import time
from pathlib import Path

from dotenv import load_dotenv

from logging_config import get_logger
from mercari_scraper import MercariScraper
from telegram_notifier import TelegramNotifier
from product_storage import ProductStorage

# Load environment variables
load_dotenv()

# Initialize logger
logger = get_logger(__name__)


class MercariMonitor:
    """Main orchestrator for the Mercari monitoring system."""

    def __init__(self, config_path: str = "config.json"):
        self.config_path = Path(config_path)
        self.config = self.load_config()

        # Initialize components
        self.logger = get_logger("MercariMonitor")
        self.storage = ProductStorage(
            max_storage_days=self.config["storage"]["cleanup_after_days"]
        )
        self.scraper = MercariScraper(self.config)
        self.notifier = TelegramNotifier(self.config)

        self.logger.info("Mercari Monitor initialized")

    def load_config(self) -> dict:
        """Load configuration from JSON file."""
        try:
            with open(self.config_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.error("Failed to load config", error=str(e))
            raise

    def load_search_queries(self) -> list:
        """Load search queries from JSON file."""
        try:
            queries_file = Path("queries.json")
            if not queries_file.exists():
                self.logger.warning(
                    "queries.json not found, creating empty file"
                )
                queries_file.write_text("[]", encoding="utf-8")
                return []

            with open(queries_file, encoding="utf-8") as f:
                queries = json.load(f)

            self.logger.info(
                "Loaded search queries",
                query_count=len(queries),
            )
            return queries

        except Exception as e:
            self.logger.error("Failed to load search queries", error=str(e))
            return []

    def process_query(self, query) -> None:
        """Process a single search query and notify of new products."""
        try:
            self.logger.info("Processing query", query=query)

            products = self.scraper.search_products(query)

            self.logger.debug(
                "Products found by scraper",
                count=len(products),
                query=query,
            )

            new_products = []
            price_changes = []


            for product in products:

                if not self.storage.is_product_known(product["id"]):
                    new_products.append(product)
                    self.storage.add_product(product)

                else:
                    change = self.storage.update_product_price(product)

                    if change:
                        price_changes.append(change)

            if new_products:
                self.logger.info(
                    "Found new products",
                    count=len(new_products),
                    query=query,
                )
                self.notifier.send_notifications(
                    new_products,
                    query
                )
            elif price_changes:
                self.logger.info(
                    "Found price changes",
                    count=len(price_changes),
                    query=query,
                )
                self.notifier.send_price_change_notifications(
                    price_changes,
                    query
                )
            else:
                self.logger.debug(
                    "No new products for query",
                    query=query,
                )

        except Exception:
            self.logger.log_exception(
                "A critical error occurred during process_query",
                query=query,
            )

    def run_once(self) -> None:
        """Run monitoring once for all queries."""
        try:
            queries = self.load_search_queries()

            if not queries:
                self.logger.warning(
                    "No search queries configured. Skipping run."
                )
                return

            self.logger.info("Starting monitoring cycle")

            for query in queries:
                self.process_query(query)
                time.sleep(self.config["timing"]["search_delay"])

            self.storage.cleanup_old_products()
            self.logger.info("Monitoring cycle completed")

        except Exception as e:
            self.logger.error(
                "Monitoring cycle failed",
                error=str(e),
            )

    def close(self):
        """Cleanup resources and save data."""
        try:
            self.logger.info("Saving product database...")
            self.storage.save_products()
            self.scraper.close()
            self.logger.info("Mercari Monitor closed")
        except Exception as e:
            self.logger.error(
                "Error during cleanup",
                error=str(e),
            )


def main():
    """Main entry point."""
    import argparse

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
        monitor = MercariMonitor(args.config)
        monitor.run_once()
    except Exception:
        logger.log_exception("A fatal error occurred in main:")
    finally:
        if monitor:
            monitor.close()


if __name__ == "__main__":
    main()