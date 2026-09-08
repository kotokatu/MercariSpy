#!/usr/bin/env python3.9

import argparse

from product_storage import ProductStorage


def main():
    parser = argparse.ArgumentParser(
        description="Enable price tracking for Mercari products"
    )

    parser.add_argument(
        "product_ids",
        nargs="+",
        help="Mercari product IDs",
    )

    args = parser.parse_args()

    storage = ProductStorage()

    try:
        for product_id in args.product_ids:
            product = storage.get_product(product_id)

            if not product:
                print(
                    f"Not found in database: {product_id}"
                )
                continue

            if product["tracking"]:
                print(
                    f"Already tracked: "
                    f"{product['title']} "
                    f"(¥{product['price']:,})"
                )
                continue

            if storage.set_tracking(
                product_id,
                True,
            ):
                print(
                    f"Tracking enabled: "
                    f"{product['title']} "
                    f"(¥{product['price']:,})"
                )

    finally:
        storage.close()


if __name__ == "__main__":
    main()