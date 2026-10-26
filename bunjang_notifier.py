
#!/usr/bin/env python3.9
"""Telegram notifier dedicated to Bunjang."""

import os
from typing import Dict

from logging_config import get_logger
from telegram_notifier import TelegramNotifier


class BunjangTelegramNotifier(TelegramNotifier):
    """Reuse Telegram methods with a separate bot and chat."""

    def __init__(self, config: dict):
        self.config = config
        self.logger = get_logger("BunjangTelegramNotifier")

        self.bot_token = os.getenv("BUNJANG_BOT_TOKEN")
        self.chat_id = os.getenv("BUNJANG_CHAT_ID")

        if not self.bot_token or not self.chat_id:
            raise ValueError(
                "BUNJANG_BOT_TOKEN and BUNJANG_CHAT_ID are missing"
            )

        # Direct Telegram API, independent of the Mercari bot proxy.
        self.base_url = (
            f"https://morning-dream-7e18.kotokatu320.workers.dev/"
            f"bot{self.bot_token}"
        )

    def format_query(self, query: dict) -> str:
        parts = []

        if query.get("keyword"):
            parts.append(str(query["keyword"]))
        if query.get("category_id"):
            parts.append(str(query["category_id"]))
        if query.get("price_min") is not None:
            parts.append(f"min:₩{int(query['price_min']):,}")
        if query.get("price_max") is not None:
            parts.append(f"max:₩{int(query['price_max']):,}")

        return ", ".join(parts) or "Bunjang search"

    def _format_price_message(self, price: int) -> str:
        return f"₩{int(price):,}"

    def _format_product_message(
        self, product: Dict, query: dict
    ) -> str:
        title = self.escape_markdown_v2(
            str(product.get("title", ""))
        )
        query_text = self.escape_markdown_v2(
            self.format_query(query)
        )
        url = str(product.get("url", "")).replace(")", r"\)")

        return (
            "🟢 *New Bunjang listing*\n\n"
            f"*{title}*\n"
            f"{self._format_price_message(product.get('price', 0))}\n\n"
            f"Query: `{query_text}`\n"
        )

    def _format_price_change_message(
        self, product: Dict, query: dict
    ) -> str:
        title = self.escape_markdown_v2(
            str(product.get("title", ""))
        )
        query_text = self.escape_markdown_v2(
            self.format_query(query)
        )
        url = str(product.get("url", "")).replace(")", r"\)")
        old_price = int(product.get("old_price", 0))
        new_price = int(product.get("new_price", 0))

        return (
            "💰 *Bunjang price decreased*\n\n"
            f"*{title}*\n\n"
            f"₩{old_price:,} ⬇️\n"
            f"₩{new_price:,}\n\n"
            f"Query: `{query_text}`\n"
        )

    def _tracking_keyboard(
        self,
        product_id: str,
        tracking: bool = False,
        product_url: str = None,
    ) -> dict:
        product_id = str(product_id)

        if tracking:
            track_button = {
                "text": "🔔 Tracking",
                "callback_data": f"btrack:{product_id}",
            }
            stop_button = {
                "text": "🗑 Stop",
                "callback_data": f"bstop:{product_id}",
            }
        else:
            track_button = {
                "text": "❤️ Track price",
                "callback_data": f"btrack:{product_id}",
            }
            stop_button = {
                "text": "🗑 Stop tracking",
                "callback_data": f"bstop:{product_id}",
            }

        keyboard = [[track_button, stop_button]]

        if product_url:
            keyboard.append([{
                "text": "↗ Open on Bunjang",
                "url": product_url,
            }])

        return {"inline_keyboard": keyboard}
