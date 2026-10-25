
#!/usr/bin/env python3.9
"""Standalone entry point for Bunjang Monitor."""

import json
import time

from dotenv import load_dotenv

from bunjang_monitor import BunjangMonitor
from logging_config import get_logger


def main():
    load_dotenv()
    logger = get_logger("BunjangMain")

    with open("config.json", encoding="utf-8") as file:
        config = json.load(file)

    monitor = BunjangMonitor(config)
    notifier = monitor.notifier
    next_search = 0
    offset = None

    logger.info("Bunjang Monitor started")

    try:
        while True:
            now = time.monotonic()

            if now >= next_search:
                monitor.run_once()
                interval = max(
                    10,
                    int(config["timing"]["search_interval"]),
                )
                next_search = time.monotonic() + interval

            # Poll only the NEW Bunjang bot.
            updates = notifier.get_updates(
                offset=offset,
                timeout=5,
            )

            for update in updates:
                offset = update["update_id"] + 1

                try:
                    handled = monitor.process_telegram_callback(
                        update
                    )
                    if not handled:
                        logger.debug(
                            "Ignoring unrelated Telegram update"
                        )
                except Exception as exc:
                    logger.error(
                        "Failed to process Bunjang callback",
                        error=str(exc),
                    )

    except KeyboardInterrupt:
        logger.info("Bunjang Monitor stopped by user")

    finally:
        monitor.close()


if __name__ == "__main__":
    main()
