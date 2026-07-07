import json
from pathlib import Path

from etl.common.logger import info, success

RAW_DIR = Path("data/raw/kurly")

OUTPUT = Path("data/processed/kurly/products.json")
FAILED = Path("data/processed/kurly/failed_products.json")


def extract_products(data):

    sections = data["response"]["data"].get("listSections", [])

    for section in sections:

        view = section.get("view", {})

        if view.get("sectionCode") != "PRODUCT_LIST":
            continue

        return section["data"].get("items", [])

    return []


def main():

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)

    products = []

    failed = []

    files = sorted(RAW_DIR.glob("*.json"))

    info(f"Raw files : {len(files)}")

    for file in files:

        with open(file, encoding="utf-8") as f:
            raw = json.load(f)

        keyword = raw["search_keyword"]

        items = extract_products(raw)

        if len(items) == 0:

            failed.append(keyword)
            continue

        for item in items[:10]:

            products.append({

                "search_keyword": keyword,

                "rank": item.get("position"),

                "product_id": item.get("no"),

                "name": item.get("name"),

                "description": item.get("shortDescription"),

                "price": item.get("salesPrice"),

                "discount_price": item.get("discountedPrice"),

                "discount_rate": item.get("discountRate"),

                "image": item.get("listImageUrl"),

                "review_count": item.get("reviewCount"),

                "delivery": item.get("deliveryTypeNames", []),

                "tags": [
                    s["name"]
                    for s in item.get("stickers", [])
                ],

                "sold_out": item.get("isSoldOut")
            })

    with open(OUTPUT, "w", encoding="utf-8") as f:
        json.dump(
            products,
            f,
            ensure_ascii=False,
            indent=2,
        )

    with open(FAILED, "w", encoding="utf-8") as f:
        json.dump(
            failed,
            f,
            ensure_ascii=False,
            indent=2,
        )

    success(f"Products : {len(products)}")
    success(f"Failed : {len(failed)}")


if __name__ == "__main__":
    main()