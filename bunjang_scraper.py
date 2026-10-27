#!/usr/bin/env python3.9
"""Minimal first-page scraper for Bunjang search API."""

from typing import Dict, List
import requests

from logging_config import get_logger


class BunjangScraper:
    API_URL = "https://api.bunjang.co.kr/api/search/v8/web/search"

    def __init__(self):
        self.logger = get_logger("BunjangScraper")
        self.session = requests.Session()
        self.session.headers.update({
            "Accept": "application/json, text/plain, */*",
            "User-Agent": "Mozilla/5.0",
        })

    def search_products(self, query: dict) -> List[Dict]:
        search_condition = {
            "sort": "latest", 
            }

        if query.get("category_id"):
            search_condition["categoryId"] = query.get("category_id")
            search_condition["policyKey"] = "pw.product.category"

        keyword = query.get("keyword")

        if keyword:
            search_condition["q"] = keyword
            search_condition["policyKey"] = "pw.product.keyword"

        response = self.session.get(
            self.API_URL,
            params=search_condition,
            timeout=30,
        )
        response.raise_for_status()
        payload = response.json()


        responses = (
            payload.get("data", {})
            .get("responses", {})
)

        grid = responses.get("mainGrid")

        if not grid:
            self.logger.warning(
                "Bunjang response did not contain mainGrid",
                keyword=keyword,
                response_keys=list(responses.keys()),
            )
            return []

        search_response = grid.get("searchResponse") or {}
        raw_products = search_response.get("data") or []
        products = []

        for item in raw_products:
            # Ignore external ads and any non-product cards.
            if item.get("type") != "PRODUCT" or not item.get("pid"):
                continue

            # MVP: only monitor listings explicitly marked as currently for sale.
            if item.get("status") != "SELLING":
                continue

            try:
                price = int(item.get("price", 0))
            except (TypeError, ValueError):
                continue

            pid = str(item["pid"])
            image_url = item.get("productImage") or ""
            if "{res}" in image_url:
                image_url = image_url.replace("{res}", "600")

            products.append({
                "id": pid,
                "title": str(item.get("name") or "").strip(),
                "price": price,
                # Common Bunjang mobile product URL pattern; verify with a live listing.
                "url": f"https://m.bunjang.co.kr/products/{pid}",
                "image_url": image_url or None,
                "status": item.get("status"),
            })

        self.logger.info(
            "Bunjang products parsed",
            keyword=keyword,
            raw_count=len(raw_products),
            active_count=len(products),
            page=search_response.get("loggingContext", {}).get("pageNumber"),
        )
        return products

    def close(self):
        self.session.close()
