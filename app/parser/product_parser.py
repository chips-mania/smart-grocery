import re

GRAM_PATTERN = re.compile(
    r"(\d+(?:\.\d+)?)\s*(kg|g|ml|L)\b",
    re.IGNORECASE,
)
COUNT_PATTERN = re.compile(
    r"(\d+(?:\.\d+)?)\s*(개|입|구|모|팩|봉|송이|마리|대)\b",
)
MULTIPLY_PATTERN = re.compile(
    r"(\d+(?:\.\d+)?)\s*(g|kg|ml|L)\s*[x×X]\s*(\d+)",
    re.IGNORECASE,
)
MULTIPLY_COUNT_PATTERN = re.compile(
    r"(\d+(?:\.\d+)?)\s*(개|입|구|모|팩|봉|송이|마리|대)\s*[x×X]\s*(\d+)",
)


def _to_base(amount: float, unit: str) -> tuple[float, str]:
    unit = unit.lower()
    if unit == "kg":
        return amount * 1000, "g"
    if unit == "l":
        return amount * 1000, "ml"
    return amount, unit


def parse_product_package(name: str, description: str = "") -> dict:
    text = f"{name} {description or ''}"

    match = MULTIPLY_PATTERN.search(text)
    if match:
        amount, unit = _to_base(float(match.group(1)), match.group(2))
        multiplier = int(match.group(3))
        return {
            "package_amount": amount * multiplier,
            "package_unit": unit,
            "package_count": None,
            "package_count_unit": None,
            "parse_status": "ok",
        }

    match = GRAM_PATTERN.search(text)
    if match:
        amount, unit = _to_base(float(match.group(1)), match.group(2))
        return {
            "package_amount": amount,
            "package_unit": unit,
            "package_count": None,
            "package_count_unit": None,
            "parse_status": "ok",
        }

    match = MULTIPLY_COUNT_PATTERN.search(text)
    if match:
        return {
            "package_amount": None,
            "package_unit": None,
            "package_count": float(match.group(1)) * float(match.group(3)),
            "package_count_unit": match.group(2),
            "parse_status": "ok",
        }

    match = COUNT_PATTERN.search(text)
    if match:
        return {
            "package_amount": None,
            "package_unit": None,
            "package_count": float(match.group(1)),
            "package_count_unit": match.group(2),
            "parse_status": "ok",
        }

    return {
        "package_amount": None,
        "package_unit": None,
        "package_count": None,
        "package_count_unit": None,
        "parse_status": "failed",
    }


def effective_price(product: dict) -> int:
    discount = product.get("discount_price")
    if discount is not None and discount > 0:
        return int(discount)
    return int(product.get("price") or 0)
