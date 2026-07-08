from app.config.ingredient_alias import INGREDIENT_ALIASES


def _compact(name: str) -> str:

    return name.replace(" ", "").strip().lower()


def _canonical(name: str) -> str:

    compact = _compact(name)
    return _compact(INGREDIENT_ALIASES.get(name, INGREDIENT_ALIASES.get(compact, name)))


def ingredients_match(recipe_ingredient: str, fridge_ingredient: str) -> bool:

    left = _compact(recipe_ingredient)
    right = _compact(fridge_ingredient)
    if not left or not right:
        return False

    if left == right:
        return True
    if left in right or right in left:
        return True

    if _canonical(recipe_ingredient) == _canonical(fridge_ingredient):
        return True

    meat_groups = (
        ("돼지", "돼지고기", "한돈", "제육"),
        ("소", "쇠고기", "소고기", "한우"),
        ("닭", "닭고기", "치킨"),
    )
    for group in meat_groups:
        if any(token in left for token in group) and any(token in right for token in group):
            return True

    return False


def fridge_ingredient_names(fridge_items: list[dict]) -> list[str]:

    return [item["ingredient"] for item in fridge_items if item.get("ingredient")]


def recipe_fridge_overlap(recipe_ingredients: set[str], fridge_items: list[dict]) -> list[str]:

    matched: list[str] = []
    fridge_names = fridge_ingredient_names(fridge_items)

    for recipe_name in recipe_ingredients:
        for fridge_name in fridge_names:
            if ingredients_match(recipe_name, fridge_name):
                matched.append(recipe_name)
                break

    return matched
