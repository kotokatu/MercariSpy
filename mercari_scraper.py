#!/usr/bin/env python3.9

"""
Mercari.jp scraper using official internal API.
No Selenium required.
"""



import requests
import time
import uuid
import hashlib
from typing import List, Dict, Optional

from dpop import DPoPGenerator
from logging_config import get_logger
from mercari_device import MercariDevice

def create_search_session_id():

        return hashlib.md5(
            str(uuid.uuid4()).encode()
        ).hexdigest()


class MercariScraper:

    API_URL = "https://api.mercari.jp/v2/entities:search"

    def __init__(self, config: dict):
        self.config = config
        self.logger = get_logger("MercariScraper")
        self.dpop = DPoPGenerator()
        self.device = MercariDevice()
       

        self.session = requests.Session()
        

        self.session.headers.update({
            "accept": "application/json, text/plain, */*",
            "content-type": "application/json",
            "origin": "https://jp.mercari.com",
            "referer": "https://jp.mercari.com/",
            "user-agent": (
                "Mozilla/5.0 "
                "(Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 "
                "Chrome/150 Safari/537.36"
            ),
            "x-country-code": "RU",
            "x-platform": "web",
        })

    def _build_payload(self, query: dict) -> dict:
        search_condition = {
        "keyword": "",
        "excludeKeyword": "",

        "sort": "SORT_CREATED_TIME",
        "order": "ORDER_DESC",
        "status": ["STATUS_ON_SALE"],

        "sizeId": [],
        "categoryId": [],
        "brandId": [],
        "sellerId": [],

        "priceMin": 0,
        "priceMax": 0,

        "itemConditionId": [],
        "shippingPayerId": [],
        "shippingFromArea": [],
        "shippingMethod": [],

        "colorId": [],

        "hasCoupon": False,

        "attributes": [],
        "itemTypes": [],
        "skuIds": [],
        "shopIds": [],

        "excludeShippingMethodIds": [],
    }


        if query.get("keyword"):
            search_condition["keyword"] = query["keyword"]


        if query.get("category_id"):
            search_condition["categoryId"] = [
                query["category_id"]
            ]


        if query.get("brand_id"):
            search_condition["brandId"] = [
                query["brand_id"]
            ]


        if query.get("price_min"):
            search_condition["priceMin"] = query["price_min"]


        if query.get("price_max"):
            search_condition["priceMax"] = query["price_max"]


        payload = {
            "userId": "",

            "config": {
                "responseToggles": [
                    "QUERY_SUGGESTION_WEB_1"
                ]
            },

            "pageSize": 120,
            "pageToken": "",

           

            "source": "BaseSerp",

            "indexRouting": "INDEX_ROUTING_UNSPECIFIED",

            "thumbnailTypes": [],

            "searchCondition": search_condition,

            "serviceFrom": "suruga",

            "withItemBrand": True,
            "withItemSize": False,
            "withItemPromotions": True,
            "withItemSizes": True,

            "withShopname": False,

            "useDynamicAttribute": True,

            "withSuggestedItems": True,
            "withOfferPricePromotion": True,
            "withProductSuggest": True,

            "withParentProducts": False,
            "withProductArticles": True,

            "withSearchConditionId": False,

            "withAuction": True,

            "laplaceDeviceUuid":  self.device.get_device_id()
        
        }

        return payload


    
    def _parse_product(self, item: dict) -> Optional[Dict]:
        """
        Convert API item into internal format.
        """

        try:

            product_id = item.get("id")

            if not product_id:
                return None

            price = int(
                item.get("price", 0)
            )

            title = (
                item.get("name")
                or item.get("title")
                or ""
            )

            image = None

            if item.get("photos"):
                image = item["photos"][0].get("uri")

            elif item.get("thumbnails"):
                image = item["thumbnails"][0]

            # Private seller vs shop
            if product_id.startswith("m"):
                url = f"https://jp.mercari.com/en/item/{product_id}"
            else:
                url = (
                    f"https://jp.mercari.com/en/shops/product/{product_id}"
                )

            return {
                "id": product_id,
                "title": title,
                "price": price,
                "url": url,
                "image_url": image
            }

        except Exception as e:
            self.logger.error(
                "Failed parsing product",
                error=str(e)
            )
            return None

    def search_products(self, query: dict) -> List[Dict]:

        try:

            payload = self._build_payload(query)

            payload["searchSessionId"] = create_search_session_id()

            payload["laplaceDeviceUuid"] = (
                self.device.get_device_id()
            )

            self.logger.info(
                "Mercari API search",
                query=query
            )


            for attempt in range(3):

                headers = {
                    "dpop": self.dpop.generate(
                        self.API_URL,
                        "POST"
                    )
                }


                try:

                    response = self.session.post(
                        self.API_URL,
                        json=payload,
                        headers=headers,
                        timeout=(10,60)
                    )


                except requests.exceptions.ReadTimeout:

                    self.logger.warning(
                        "Mercari timeout",
                        attempt=attempt + 1
                    )

                    time.sleep(3)
                    continue


                if response.status_code == 200:

                    data = response.json()

                    products = []

                    for item in data.get("items", []):

                        product = self._parse_product(item)

                        if product:
                            products.append(product)


                    self.logger.info(
                        "Products extracted",
                        count=len(products)
                    )

                    return products


                elif response.status_code == 401:

                    self.logger.warning(
                        "401 - regenerating DPoP"
                    )

                    continue


                elif response.status_code == 429:

                    self.logger.warning(
                        "Rate limit"
                    )

                    time.sleep(10)
                    continue


                else:

                    self.logger.error(
                        "Mercari API error",
                        status=response.status_code,
                        body=response.text[:500]
                    )

                    return []


            return []


        except Exception as e:

            self.logger.error(
                "Mercari request failed",
                error=str(e)
            )

            return []

    def close(self):

        try:
            self.session.close()

        except Exception:
            pass

   



if __name__ == "__main__":

    import json


    with open(
        "config.json",
        encoding="utf-8"
    ) as f:
        config = json.load(f)


    scraper = MercariScraper(config)


    result = scraper.search_products(
        {
            "keyword": "shimano alfine",
            "category_id": 1139
        }
    )


    print(
        json.dumps(
            result[:3],
            indent=2,
            ensure_ascii=False
        )
    )