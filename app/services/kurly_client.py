"""Kurly market search API client."""

from __future__ import annotations

import requests

from app.parser.product_parser import effective_price, parse_product_package

KURLY_SEARCH_URL = "https://api.kurly.com/search/v4/sites/market/normal-search"
HEADERS = {
    "User-Agent": "Mozilla/5.0",
    "Accept": "application/json",
}


def search_kurly(keyword: str, *, page: int = 1, limit: int = 10) -> list[dict]:
    response = requests.get(
        KURLY_SEARCH_URL,
        params={"keyword": keyword, "sortType": 4, "page": page},
        headers=HEADERS,
        timeout=20,
    )
    response.raise_for_status()
    payload = response.json()
    raw_items = _extract_product_items(payload)
    products: list[dict] = []
    for item in raw_items:
        if item.get("isSoldOut"):
            continue
        product = _normalize_product(item, keyword)
        products.append(product)
        if len(products) >= limit:
            break
    return products


def _extract_product_items(payload: dict) -> list[dict]:
    data = payload.get("data") or {}
    items: list[dict] = []
    for section in data.get("listSections") or []:
        view = section.get("view") or {}
        if view.get("sectionCode") != "PRODUCT_LIST":
            continue
        section_data = section.get("data") or {}
        for item in section_data.get("items") or []:
            if isinstance(item, dict) and item.get("no") is not None:
                items.append(item)
    return items


def _normalize_product(item: dict, keyword: str) -> dict:
    name = item.get("name") or ""
    description = item.get("shortDescription") or ""
    sales = item.get("salesPrice")
    discounted = item.get("discountedPrice")
    price = int(sales) if sales is not None else 0
    discount_price = int(discounted) if discounted is not None else None
    discount_rate = int(item.get("discountRate") or 0)
    package = parse_product_package(name, description)
    product = {
        "product_id": item.get("no"),
        "name": name,
        "description": description,
        "price": price,
        "discount_price": discount_price,
        "discount_rate": discount_rate,
        "image_url": item.get("listImageUrl"),
        "search_keyword": keyword,
        "package_amount": package.get("package_amount"),
        "package_unit": package.get("package_unit"),
        "package_count": package.get("package_count"),
        "package_count_unit": package.get("package_count_unit"),
        "package_parse_status": package.get("parse_status"),
        "effective_price": effective_price(
            {
                "price": price,
                "discount_price": discount_price,
            }
        ),
    }
    return product
