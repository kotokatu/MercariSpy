#!/usr/bin/env python3.9

import os
import time
import json
import requests
from typing import List, Dict

from logging_config import get_logger


class TelegramNotifier:
    """
    Telegram bot notification system.
    Supports new products and price change notifications.
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
            text = text.replace(
                char,
                "\\" + char
            )

        return text


    def _get_query_text(self, query) -> str:
        """
        Convert query dict/string to readable text.
        """

        if isinstance(query, dict):
            return query.get("keyword", "")

        return str(query)


    def _format_price_message(self, price: int) -> str:
        return f"¥{price:,}"


    def _format_product_message(self, product: Dict, query: dict) -> str:

        price_msg = self._format_price_message(
            product["price"]
        )

        title = self.escape_markdown_v2(
            str(product["title"])
        )


        query_text = self.format_query(query)

        query_text = self.escape_markdown_v2(
            query_text
        )


        url = product["url"].replace(
            ")",
            "\\)"
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
        query
    ) -> str:

        old_price = product["old_price"]
        new_price = product["new_price"]


        title = self.escape_markdown_v2(
            product.get("title", "")
        )

        query_text = self.escape_markdown_v2(
            self.format_query(query)
        )

        url = self.escape_markdown_v2(
            product.get("url", "")
        )

        return (
            "💰 *Price changed*\n\n"
            f"*{title}*\n\n"
            f"¥{old_price:,} "
            "⬇️\n"
            f"¥{new_price:,} "
            f"Query: `{query_text}`\n"
            f"[View on Mercari]({url})"
        )


    def send_telegram_message(
        self,
        message: str,
        photo_url: str = None
    ) -> bool:

        time.sleep(
            self.config["notifications"]["rate_limit_delay"]
        )

        payload = {
            "chat_id": self.chat_id,
            "parse_mode": "MarkdownV2",
        }

        try:

            if photo_url:

                photo_payload = payload.copy()
                photo_payload.update(
                    {
                        "photo": photo_url,
                        "caption": message[:1024],
                    }
                )

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



    def send_notification(
        self,
        product: Dict,
        query
    ) -> bool:

        try:

            message = self._format_product_message(
                product,
                query,
            )

            return self.send_telegram_message(
                message,
                product.get("image_url"),
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
        query
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



    def send_price_change_notifications(
        self,
        products: List[Dict],
        query
    ):

        self.logger.info(
                "Sending notifications",
                count=len(products),
                query=str(query),
            )

        for product in products:

            message = self._format_price_change_message(
                product,
                query,
            )

            self.send_telegram_message(
                message,
                product.get("image_url"),
            )



if __name__ == "__main__":

    print("--- Testing TelegramNotifier ---")

    try:

        with open(
            "config.json",
            encoding="utf-8"
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
                "keyword": "test.nitto"
            }
        )


        print("Test message sent")


    except Exception as e:
        print(e)