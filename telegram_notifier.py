#!/usr/bin/env python3.9

import os
import time
import json
import requests
from typing import List, Dict, Optional, Tuple

from logging_config import get_logger


class TelegramNotifier:
    """
    Telegram bot notification system.

    Supports:
    - new product notifications
    - price change notifications
    - inline buttons for price tracking
    - callback queries from inline buttons
    """

    def __init__(self, config: dict):
        self.config = config
        self.logger = get_logger("TelegramNotifier")

        self.bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
        self.chat_id = os.getenv("TELEGRAM_CHAT_ID")

        if not self.bot_token or not self.chat_id:
            raise ValueError(
                "TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID are missing"
            )

        self.base_url = (
            f"https://morning-dream-7e18.kotokatu320.workers.dev/"
            f"bot{self.bot_token}"
        )

    # ------------------------------------------------------------------
    # Formatting
    # ------------------------------------------------------------------

    def format_query(self, query: dict) -> str:
        parts = []

        if query.get("keyword"):
            parts.append(query["keyword"])

        if query.get("brand_id"):
            parts.append(f"brand:{query['brand_id']}")

        if query.get("category_id"):
            parts.append(f"category:{query['category_id']}")

        if query.get("price_min"):
            parts.append(f"min:{query['price_min']}¥")

        if query.get("price_max"):
            parts.append(f"max:{query['price_max']}¥")

        return ", ".join(parts)

    def escape_markdown_v2(self, text: str) -> str:
        if not isinstance(text, str):
            text = str(text)

        chars = r'_*[]()~`>#+-=|{}.!'

        for char in chars:
            text = text.replace(char, "\\" + char)

        return text

    def _format_price_message(self, price: int) -> str:
        return f"¥{price:,}"

    def _format_product_message(
        self,
        product: Dict,
        query: dict,
    ) -> str:
        price_msg = self._format_price_message(product["price"])

        title = self.escape_markdown_v2(
            str(product["title"])
        )

        query_text = self.escape_markdown_v2(
            self.format_query(query)
        )

        url = product["url"].replace(
            ")",
            "\\)",
        )

        return (
            "🚀 *New Product Found*\n\n"
            f"*{title}*\n"
            f"{price_msg}\n\n"
            f"Query: `{query_text}`\n"
            f"[View on Mercari]({url})"
        )

    def _format_price_change_message(
        self,
        product: Dict,
        query: dict,
    ) -> str:
        old_price = product["old_price"]
        new_price = product["new_price"]

        title = self.escape_markdown_v2(
            product.get("title", "")
        )

        query_text = self.escape_markdown_v2(
            self.format_query(query)
        )

        url = product.get("url", "").replace(
            ")",
            "\\)",
        )

        return (
            "💰 *Price changed*\n\n"
            f"*{title}*\n\n"
            f"¥{old_price:,} "
            "⬇️\n"
            f"¥{new_price:,}\n\n"
            f"Query: `{query_text}`\n"
            f"[View on Mercari]({url})"
        )

    # ------------------------------------------------------------------
    # Inline keyboards
    # ------------------------------------------------------------------

    def _tracking_keyboard(
        self,
        product_id: str,
        tracking: bool = False,
    ) -> dict:
        """
        Build inline keyboard for a product.

        Not tracked:
            ❤️ Track price
            🗑 Stop tracking

        Tracked:
            🔔 Tracking
            🗑 Stop
        """

        product_id = str(product_id)

        if tracking:
            track_button = {
                "text": "🔔 Tracking",
                "callback_data": f"track:{product_id}",
            }

            stop_button = {
                "text": "🗑 Stop",
                "callback_data": f"stop:{product_id}",
            }

        else:
            track_button = {
                "text": "❤️ Track price",
                "callback_data": f"track:{product_id}",
            }

            stop_button = {
                "text": "🗑 Stop tracking",
                "callback_data": f"stop:{product_id}",
            }

        return {
            "inline_keyboard": [
                [
                    track_button,
                    stop_button,
                ]
            ]
        }

    # ------------------------------------------------------------------
    # Telegram API
    # ------------------------------------------------------------------

    def send_telegram_message(
        self,
        message: str,
        photo_url: str = None,
        reply_markup: Optional[dict] = None,
    ) -> bool:
        time.sleep(
            self.config["notifications"]["rate_limit_delay"]
        )

        payload = {
            "chat_id": self.chat_id,
            "parse_mode": "MarkdownV2",
        }

        if reply_markup:
            payload["reply_markup"] = reply_markup

        try:
            if photo_url:
                photo_payload = payload.copy()

                photo_payload.update({
                    "photo": photo_url,
                    "caption": message[:1024],
                })

                response = requests.post(
                    f"{self.base_url}/sendPhoto",
                    json=photo_payload,
                    timeout=60,
                )

                if response.status_code == 200:
                    return True

                self.logger.warning(
                    "Failed to send photo, fallback to text",
                    status=response.status_code,
                    response=response.text[:500],
                )

            text_payload = payload.copy()

            text_payload["text"] = message[:4096]

            response = requests.post(
                f"{self.base_url}/sendMessage",
                json=text_payload,
                timeout=60,
            )

            if response.status_code == 200:
                return True

            self.logger.error(
                "Failed to send Telegram message",
                error=response.text,
            )

            return False

        except Exception as e:
            self.logger.error(
                "Telegram exception",
                error=str(e),
            )

            return False

    # ------------------------------------------------------------------
    # Product notifications
    # ------------------------------------------------------------------

    def send_notification(
        self,
        product: Dict,
        query: dict,
    ) -> bool:
        """
        Send new product notification with tracking buttons.
        """

        try:
            message = self._format_product_message(
                product,
                query,
            )

            reply_markup = self._tracking_keyboard(
                product["id"],
                tracking=False,
            )

            return self.send_telegram_message(
                message,
                product.get("image_url"),
                reply_markup,
            )

        except Exception as e:
            self.logger.error(
                "Error formatting notification",
                error=str(e),
            )

            return False

    def send_notifications(
        self,
        products: List[Dict],
        query: dict,
    ):
        if not products:
            return

        self.logger.info(
            "Sending notifications",
            count=len(products),
            query=str(query),
        )

        for product in products:
            self.send_notification(
                product,
                query,
            )

    def send_price_change_notification(
        self,
        product: Dict,
        query: dict,
    ) -> bool:
        """
        Send notification about a price decrease.

        Price-change notifications don't need tracking buttons,
        because the product is already being tracked.
        """

        try:
            message = self._format_price_change_message(
                product,
                query,
            )

            reply_markup = self._tracking_keyboard(
                product["id"],
                tracking=True,
            )

            return self.send_telegram_message(
                message,
                product.get("image_url"),
                reply_markup,
            )

        except Exception as e:
            self.logger.error(
                "Error formatting price change notification",
                error=str(e),
            )

            return False

    def send_price_change_notifications(
        self,
        products: List[Dict],
        query: dict,
    ):
        if not products:
            return

        self.logger.info(
            "Sending price change notifications",
            count=len(products),
            query=str(query),
        )

        for product in products:
            self.send_price_change_notification(
                product,
                query,
            )

    # ------------------------------------------------------------------
    # Callback queries
    # ------------------------------------------------------------------

    def get_updates(
        self,
        offset: Optional[int] = None,
        timeout: int = 0,
    ) -> List[dict]:
        """
        Get updates from Telegram.

        Callback queries from inline buttons are returned here.
        """

        params = {
            "timeout": timeout,
        }

        if offset is not None:
            params["offset"] = offset

        try:
            response = requests.get(
                f"{self.base_url}/getUpdates",
                params=params,
                timeout=max(timeout + 10, 30),
            )

            if response.status_code != 200:
                self.logger.error(
                    "Failed to get Telegram updates",
                    status=response.status_code,
                    response=response.text[:500],
                )

                return []

            data = response.json()

            if not data.get("ok"):
                self.logger.error(
                    "Telegram returned error",
                    response=str(data)[:500],
                )

                return []

            return data.get("result", [])

        except Exception as e:
            self.logger.error(
                "Telegram getUpdates exception",
                error=str(e),
            )

            return []

    def parse_callback(
        self,
        update: dict,
    ) -> Optional[Tuple[str, str, str]]:
        """
        Parse callback query.

        Returns:
            (action, product_id, callback_query_id)

        For example:
            ("track", "m123456789", "123456789")
        """

        callback_query = update.get("callback_query")

        if not callback_query:
            return None

        data = callback_query.get("data", "")

        if ":" not in data:
            self.logger.warning(
                "Unknown callback data",
                data=data,
            )

            return None

        action, product_id = data.split(
            ":",
            1,
        )

        if action not in ("track", "stop"):
            self.logger.warning(
                "Unknown callback action",
                action=action,
                product_id=product_id,
            )

            return None

        callback_query_id = callback_query.get("id")

        if not callback_query_id:
            return None

        return (
            action,
            product_id,
            callback_query_id,
        )

    def answer_callback(
        self,
        callback_query_id: str,
        text: str,
    ) -> bool:
        """
        Show a short confirmation message after button click.
        """

        try:
            response = requests.post(
                f"{self.base_url}/answerCallbackQuery",
                json={
                    "callback_query_id": callback_query_id,
                    "text": text,
                },
                timeout=30,
            )

            if response.status_code == 200:
                return True

            self.logger.error(
                "Failed to answer callback query",
                status=response.status_code,
                response=response.text[:500],
            )

            return False

        except Exception as e:
            self.logger.error(
                "Telegram callback answer exception",
                error=str(e),
            )

            return False

    def edit_tracking_buttons(
        self,
        chat_id: str,
        message_id: int,
        product_id: str,
        tracking: bool,
    ) -> bool:
        """
        Replace tracking buttons on an existing Telegram message.
        """

        reply_markup = self._tracking_keyboard(
            product_id,
            tracking=tracking,
        )

        try:
            response = requests.post(
                f"{self.base_url}/editMessageReplyMarkup",
                json={
                    "chat_id": chat_id,
                    "message_id": message_id,
                    "reply_markup": reply_markup,
                },
                timeout=30,
            )

            if response.status_code == 200:
                return True

            self.logger.error(
                "Failed to edit Telegram buttons",
                status=response.status_code,
                response=response.text[:500],
            )

            return False

        except Exception as e:
            self.logger.error(
                "Telegram edit buttons exception",
                error=str(e),
            )

            return False

    def handle_callback_result(
        self,
        update: dict,
        tracking: bool,
    ) -> bool:
        """
        Apply the new tracking state to the Telegram message.

        Returns True if the callback was handled successfully.

        The actual database update is intentionally outside this class.
        """

        callback_query = update.get("callback_query")

        if not callback_query:
            return False

        parsed = self.parse_callback(update)

        if not parsed:
            return False

        action, product_id, callback_query_id = parsed

        message = callback_query.get("message")

        if not message:
            self.logger.warning(
                "Callback has no message",
                product_id=product_id,
            )

            return False

        chat = message.get("chat")

        if not chat:
            return False

        chat_id = str(chat["id"])
        message_id = message.get("message_id")

        if not message_id:
            return False

        if action == "track":
            callback_text = "✅ Price tracking enabled"

        else:
            callback_text = "🛑 Price tracking disabled"

        answered = self.answer_callback(
            callback_query_id,
            callback_text,
        )

        edited = self.edit_tracking_buttons(
            chat_id=chat_id,
            message_id=message_id,
            product_id=product_id,
            tracking=tracking,
        )

        return answered and edited


if __name__ == "__main__":
    print("--- Testing TelegramNotifier ---")

    try:
        with open(
            "config.json",
            encoding="utf-8",
        ) as f:
            config = json.load(f)

        notifier = TelegramNotifier(config)

        test_product = {
            "id": "m123456789",
            "title": "Test Product. Nintendo Switch!",
            "price": 35000,
            "url": "https://jp.mercari.com/item/m123456789",
            "image_url": None,
        }

        notifier.send_notification(
            test_product,
            {
                "keyword": "test.nitto",
            },
        )

        print("Test message sent")

    except Exception as e:
        print(e)