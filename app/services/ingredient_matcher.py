"""Match recipe ingredients against fridge items (synonyms + meat groups)."""

# Fridge user input may differ from DB canonical_ingredient; keep only high-value pairs.
_SYNONYMS: dict[str, str] = {
    "달걀": "계란",
    "계란": "계란",
    "쇠고기": "소고기",
    "소고기": "소고기",
    "백다다기오이": "오이",
    "다다기오이": "오이",
    "오이": "오이",
}

_MEAT_GROUPS = (
    ("돼지", "돼지고기", "한돈", "제육"),
    ("소", "쇠고기", "소고기", "한우"),
    ("닭", "닭고기", "치킨"),
)


def _compact(name: str) -> str:
    return name.replace(" ", "").strip().lower()


def _canonical(name: str) -> str:
    compact = _compact(name)
    mapped = _SYNONYMS.get(name) or _SYNONYMS.get(compact) or name
    return _compact(mapped)


def _is_generic_meat(name: str) -> bool:
    return _compact(name) == "고기"


def dedupe_ingredient_rows(rows: list[dict]) -> list[dict]:
    """Drop duplicate DB rows for the same ingredient line on one recipe."""
    seen: set[tuple] = set()
    out: list[dict] = []
    for row in rows:
        name = (row.get("canonical_ingredient") or row.get("ingredient") or "").strip()
        key = (name, row.get("amount"), row.get("unit"), row.get("count"))
        if key in seen:
            continue
        seen.add(key)
        out.append(row)
    return out


def ingredients_match(recipe_ingredient: str, fridge_ingredient: str) -> bool:
    left = _compact(recipe_ingredient)
    right = _compact(fridge_ingredient)
    if not left or not right:
        return False

    if left == right:
        return True

    # Generic recipe "고기" must not substring-match "돼지고기"/"소고기".
    if _is_generic_meat(recipe_ingredient) or _is_generic_meat(fridge_ingredient):
        for group in _MEAT_GROUPS:
            if any(token in left for token in group) and any(token in right for token in group):
                return True
        return False

    if left in right or right in left:
        return True

    if _canonical(recipe_ingredient) == _canonical(fridge_ingredient):
        return True

    for group in _MEAT_GROUPS:
        if any(token in left for token in group) and any(token in right for token in group):
            return True

    return False


def fridge_item_name(item: dict) -> str:
    """Accept ingredient, name, or item keys (PlayMCP LLM often sends name)."""
    for key in ("ingredient", "name", "item"):
        value = (item.get(key) or "").strip()
        if value:
            return value
    return ""


def normalize_fridge_items(fridge_items: list[dict] | None) -> list[dict]:
    out: list[dict] = []
    for item in fridge_items or []:
        name = fridge_item_name(item)
        if not name:
            continue
        row = dict(item)
        row["ingredient"] = name
        out.append(row)
    return out


def fridge_ingredient_names(fridge_items: list[dict]) -> list[str]:
    return [item["ingredient"] for item in normalize_fridge_items(fridge_items)]


def recipe_fridge_overlap(recipe_ingredients: set[str], fridge_items: list[dict]) -> list[str]:
    matched: list[str] = []
    fridge_names = fridge_ingredient_names(fridge_items)

    for recipe_name in recipe_ingredients:
        for fridge_name in fridge_names:
            if ingredients_match(recipe_name, fridge_name):
                matched.append(recipe_name)
                break

    return matched
