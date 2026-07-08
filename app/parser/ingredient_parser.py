import re
from fractions import Fraction

GRAM_PATTERN = re.compile(
    r"(\d+(?:\.\d+)?)\s*(kg|g|ml|L)\b",
    re.IGNORECASE,
)
COUNT_PATTERN = re.compile(
    r"(\d+(?:\.\d+)?)\s*(개|구|모|대|줄기|알|마리|컵|봉|팩|입|송이|쪽)\b",
)
FRACTION_COUNT_PATTERN = re.compile(
    r"(\d+)\s*/\s*(\d+)\s*(개|구|모|대|줄기|알|마리|컵|봉|팩|입|송이|쪽)",
)
PAREN_FRACTION_PATTERN = re.compile(
    r"\((\d+)\s*/\s*(\d+)(개|구|모|대|줄기|알|마리|컵|봉|팩|입|송이|쪽)\)",
)
SERVINGS_PATTERN = re.compile(r"(\d+)")


def parse_servings(value: str | int | None) -> int:
    if value is None:
        return 1
    if isinstance(value, int):
        return max(1, value)
    match = SERVINGS_PATTERN.search(str(value))
    if match:
        return max(1, int(match.group(1)))
    return 1


def _scale_for_people(amount: float, *, people: int, recipe_servings: int) -> float:
    servings = max(1, recipe_servings)
    return float(amount) * max(1, people) / servings


def _to_grams(amount: float, unit: str) -> tuple[float, str]:
    unit = unit.lower()
    if unit == "kg":
        return amount * 1000, "g"
    if unit == "l":
        return amount * 1000, "ml"
    return amount, unit.lower()


def _parse_count_text(text: str) -> tuple[float | None, str | None]:
    if not text:
        return None, None

    text = text.strip()

    match = PAREN_FRACTION_PATTERN.search(text)
    if match:
        value = float(Fraction(int(match.group(1)), int(match.group(2))))
        return value, match.group(3)

    match = FRACTION_COUNT_PATTERN.search(text)
    if match:
        value = float(Fraction(int(match.group(1)), int(match.group(2))))
        return value, match.group(3)

    match = COUNT_PATTERN.search(text)
    if match:
        return float(match.group(1)), match.group(2)

    return None, None


def parse_recipe_ingredient(
    row: dict,
    people: int = 1,
    *,
    recipe_servings: int = 1,
) -> dict:
    ingredient = (
        row.get("canonical_ingredient")
        or row.get("ingredient")
        or ""
    )
    amount = row.get("amount")
    unit = row.get("unit")
    count = row.get("count")
    raw = row.get("raw") or ""

    required_amount = None
    required_unit = None
    required_count = None
    required_count_unit = None
    parse_status = "failed"

    servings = max(1, recipe_servings)

    if amount is not None and unit:
        required_amount = _scale_for_people(float(amount), people=people, recipe_servings=servings)
        required_unit = unit.lower()
        parse_status = "ok"

    count_value, count_unit = _parse_count_text(str(count) if count else "")
    if count_value is None:
        count_value, count_unit = _parse_count_text(raw)

    if count_value is not None and count_unit:
        required_count = _scale_for_people(count_value, people=people, recipe_servings=servings)
        required_count_unit = count_unit
        if parse_status == "failed":
            parse_status = "ok"
        elif required_amount is None:
            parse_status = "partial"

    if required_amount is None and required_count is None:
        gram_match = GRAM_PATTERN.search(raw)
        if gram_match:
            value, gram_unit = _to_grams(float(gram_match.group(1)), gram_match.group(2))
            required_amount = _scale_for_people(value, people=people, recipe_servings=servings)
            required_unit = gram_unit
            parse_status = "ok"

    # Fallback requested by product direction:
    # if amount/count is empty, assume one piece.
    if required_amount is None and required_count is None:
        required_count = _scale_for_people(1.0, people=people, recipe_servings=servings)
        required_count_unit = "개"
        parse_status = "estimated"

    return {
        "ingredient": ingredient,
        "required_amount": required_amount,
        "required_unit": required_unit,
        "required_count": required_count,
        "required_count_unit": required_count_unit,
        "parse_status": parse_status,
        "raw": raw,
    }
