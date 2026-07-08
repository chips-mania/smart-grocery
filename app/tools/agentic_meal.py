"""Atomic MCP tools for leftover-first one-meal planning."""

from __future__ import annotations

from app.cache.recipe_engagement import sort_recipes_by_inq
from app.cache.startup_cache import get_cache
from app.parser.product_parser import effective_price
from app.services.kurly_client import search_kurly
from app.tools.orchestrator_instructions import with_ai_review
from app.services.meal_tray import (
    MAIN_CATEGORIES,
    SIDE_CATEGORIES,
    SOUP_CATEGORIES,
    aggregate_ingredients,
    pick_best_tray_by_shopping,
    propose_trays,
    relevant_kurly_products,
    score_cart_leftovers,
    score_recipe_for_fridge,
    select_min_waste_product,
    simulate_tray_shopping,
)
from app.services.recipe_service import RecipeService

_recipe_service = RecipeService()


def _attach_ingredients(recipes: list[dict]) -> list[dict]:
    cache = get_cache()
    out: list[dict] = []
    for recipe in recipes:
        row = dict(recipe)
        ingredients = cache.get_ingredients(recipe["recipe_id"])
        row["ingredients"] = [
            {
                "ingredient": item.get("ingredient"),
                "canonical_ingredient": item.get("canonical_ingredient"),
                "amount": item.get("amount"),
                "unit": item.get("unit"),
                "count": item.get("count"),
                "role": item.get("role"),
                "buy_required": item.get("buy_required", True),
            }
            for item in ingredients
        ]
        out.append(row)
    return out


def search_recipes(
    query: str | None = None,
    fridge_items: list[dict] | None = None,
    category: str | None = None,
    limit: int = 15,
) -> dict:
    """Search recipes by dish name and/or fridge leftovers. Includes ingredients."""
    cache = get_cache()
    fridge_items = fridge_items or []
    limit = max(1, min(int(limit), 30))
    recipes: list[dict] = []

    category_map = {
        "soup": SOUP_CATEGORIES,
        "main": MAIN_CATEGORIES,
        "side": SIDE_CATEGORIES,
        "국&찌개": SOUP_CATEGORIES,
        "일품": MAIN_CATEGORIES,
        "반찬": SIDE_CATEGORIES,
    }
    allowed = category_map.get(category or "", None)

    if query and query.strip():
        resolution = _recipe_service.resolve_menu_name(query.strip())
        if resolution:
            row = resolution["recipe"]
            if allowed is None or row.get("category") in allowed:
                recipes.append(row)
        for row in _recipe_service.search_recipe(query.strip(), limit=limit):
            if allowed and row.get("category") not in allowed:
                continue
            if all(r["recipe_id"] != row["recipe_id"] for r in recipes):
                recipes.append(row)

    if fridge_items:
        from app.services.ingredient_matcher import ingredients_match

        fridge_names = [
            item.get("ingredient")
            for item in fridge_items
            if item.get("ingredient")
        ]
        scored: list[tuple] = []
        for recipe in cache.get_recipes():
            if allowed and recipe.get("category") not in allowed:
                continue
            names = cache.get_ingredient_names(recipe["recipe_id"])
            if not names:
                continue
            covered = [
                name
                for name in names
                if any(ingredients_match(name, fridge) for fridge in fridge_names)
            ]
            if not covered:
                continue
            # rough buy_count proxy: non-covered non-trivial names
            buy_proxy = max(0, len(names) - len(covered))
            coverage = len(covered) / max(len(names), 1)
            scored.append((coverage, -buy_proxy, recipe, covered))
        scored.sort(key=lambda item: (-item[0], -item[1]))
        for coverage, buy_proxy, recipe, covered in scored[:limit]:
            if all(r["recipe_id"] != recipe["recipe_id"] for r in recipes):
                row = dict(recipe)
                row["fridge_fit"] = {
                    "coverage": round(coverage, 3),
                    "covered_count": len(covered),
                    "covered": covered,
                    "buy_count_proxy": -buy_proxy,
                }
                recipes.append(row)

    recipes = sort_recipes_by_inq(_attach_ingredients(recipes))[:limit]
    for recipe in recipes:
        if "fridge_fit" not in recipe and fridge_items:
            recipe["fridge_fit"] = score_recipe_for_fridge(recipe, fridge_items)

    return with_ai_review(
        "search_recipes",
        {
            "count": len(recipes),
            "recipes": recipes,
            "objective": "Leftover minimization first; prefer recipes covering fridge items.",
        },
    )


def propose_meal_trays(
    recipes: list[dict],
    fridge_items: list[dict] | None = None,
    people: int = 1,
    missing_pantry: list[str] | None = None,
    soup_recipe_id: int | None = None,
    limit: int = 5,
) -> dict:
    """Propose complete soup+main+side trays. Every slot is a real recipe."""
    cache = get_cache()
    if not recipes and soup_recipe_id is None:
        return {
            "trays": [],
            "error": "recipes required (or soup_recipe_id to anchor soup)",
        }

    need_fill = [r for r in recipes if not r.get("ingredients")]
    if need_fill:
        filled = {r["recipe_id"]: r for r in _attach_ingredients(need_fill)}
        recipes = [
            filled.get(r["recipe_id"], r) if not r.get("ingredients") else r
            for r in recipes
        ]

    trays = propose_trays(
        recipes,
        fridge_items or [],
        missing_pantry=missing_pantry,
        limit=limit,
        people=people,
        soup_recipe_id=soup_recipe_id,
        cache=cache,
    )
    if not trays:
        return {
            "count": 0,
            "trays": [],
            "slots": ["soup", "main", "side"],
            "error": (
                "완성된 밥상(국+일품+반찬 레시피 3개)을 만들 수 없습니다. "
                "search_recipes(category='main'|'side')로 후보를 더 넣거나 "
                "soup_recipe_id로 국을 고정하세요."
            ),
            "objective": "Each slot must be a recipe — never an ingredient name.",
        }
    return with_ai_review(
        "propose_meal_trays",
        {
            "count": len(trays),
            "trays": trays,
            "slots": ["soup", "main", "side"],
            "objective": (
                "Complete trays only: soup=국&찌개, main=일품, side=반찬. "
                "Never put ingredients in menu slots."
            ),
        },
    )


def aggregate_buy_list(
    recipes: list[dict],
    fridge_items: list[dict] | None = None,
    people: int = 1,
    missing_pantry: list[str] | None = None,
) -> dict:
    """Merge tray recipe needs minus fridge/pantry into one buy list."""
    get_cache()
    if not recipes:
        return {"buy_list": [], "error": "recipes required"}

    need_fill = [r for r in recipes if not r.get("ingredients")]
    if need_fill:
        filled = {r["recipe_id"]: r for r in _attach_ingredients(need_fill)}
        recipes = [
            filled.get(r["recipe_id"], r) if not r.get("ingredients") else r
            for r in recipes
        ]

    result = aggregate_ingredients(
        recipes,
        people=people,
        fridge_items=fridge_items or [],
        missing_pantry=missing_pantry,
    )
    result["objective"] = "Buy list for leftover-aware product selection."
    return with_ai_review("aggregate_buy_list", result)


def kurly_search(keyword: str, limit: int = 8) -> dict:
    """Search Kurly catalog by keyword. AI should filter irrelevant hits before select."""
    keyword = (keyword or "").strip()
    if not keyword:
        return {"products": [], "error": "keyword required"}
    limit = max(1, min(int(limit), 20))
    try:
        products = search_kurly(keyword, limit=limit)
    except Exception as exc:  # noqa: BLE001
        return {"products": [], "error": str(exc), "keyword": keyword}
    return with_ai_review(
        "kurly_search",
        {
            "keyword": keyword,
            "count": len(products),
            "products": products,
            "instruction": (
                "Only parsable-package products can be purchased. "
                "Filter irrelevant matches, then call select_product_min_waste."
            ),
        },
    )


def select_product_min_waste(
    ingredient: str,
    candidates: list[dict],
    required_amount: float | None = None,
    required_unit: str | None = None,
    required_count: float | None = None,
    required_count_unit: str | None = None,
) -> dict:
    """Pick the candidate with the smallest leftover vs required amount. Price is tie-break only."""
    need = {
        "ingredient": ingredient,
        "required_amount": required_amount or 0.0,
        "required_unit": required_unit,
        "required_count": required_count or 0.0,
        "required_count_unit": required_count_unit,
    }
    chosen = select_min_waste_product(candidates or [], need)
    if not chosen:
        return {
            "error": "no_parsable_candidates",
            "ingredient": ingredient,
            "note": "패키지 용량/수량 파싱이 가능한 상품만 구매 대상입니다.",
        }
    product = chosen["product"]
    line_price = effective_price(product) * int(chosen["quantity"])
    chosen["line_price"] = line_price
    return with_ai_review(
        "select_product_min_waste",
        {
            "ingredient": ingredient,
            "selection": chosen,
            "objective": "Minimize leftover amount first; price secondary.",
        },
    )


def score_leftovers(selections: list[dict]) -> dict:
    """Score a confirmed shopping selection list by leftover volume (lower is better)."""
    return with_ai_review("score_leftovers", score_cart_leftovers(selections or []))


def evaluate_meal_tray(
    recipe_ids: list[int],
    people: int = 1,
    fridge_items: list[dict] | None = None,
    missing_pantry: list[str] | None = None,
    kurly_limit: int = 8,
) -> dict:
    """Simulate joint Kurly shopping for one tray (3 recipe ids). Returns leftover_score."""
    get_cache()
    return with_ai_review(
        "evaluate_meal_tray",
        simulate_tray_shopping(
            recipe_ids,
            people=people,
            fridge_items=fridge_items,
            missing_pantry=missing_pantry,
            kurly_limit=kurly_limit,
        ),
    )


def pick_best_meal_tray(
    trays: list[dict],
    people: int = 1,
    fridge_items: list[dict] | None = None,
    missing_pantry: list[str] | None = None,
    max_evaluate: int = 5,
    kurly_limit: int = 8,
) -> dict:
    """Evaluate multiple tray candidates with simulated shopping; pick lowest leftover."""
    get_cache()
    return with_ai_review(
        "pick_best_meal_tray",
        pick_best_tray_by_shopping(
            trays,
            people=people,
            fridge_items=fridge_items,
            missing_pantry=missing_pantry,
            max_evaluate=max_evaluate,
            kurly_limit=kurly_limit,
        ),
    )


def plan_one_meal(
    query: str | None = None,
    fridge_items: list[dict] | None = None,
    people: int = 1,
    soup_recipe_id: int | None = None,
    missing_pantry: list[str] | None = None,
    tray_candidates: int = 8,
    max_evaluate: int = 5,
) -> dict:
    """End-to-end: search → propose trays → simulate shopping for top-k → pick best."""
    get_cache()
    found = search_recipes(
        query=query,
        fridge_items=fridge_items,
        limit=max(tray_candidates, 5),
    )
    recipes = found.get("recipes") or []
    if not recipes and not soup_recipe_id:
        return {"error": "no_recipes", "query": query}

    if soup_recipe_id is None and query and recipes:
        soup_candidates = [
            recipe for recipe in recipes if recipe.get("category") in SOUP_CATEGORIES
        ]
        if soup_candidates:
            soup_recipe_id = sort_recipes_by_inq(soup_candidates)[0]["recipe_id"]
        else:
            soup_recipe_id = sort_recipes_by_inq(recipes)[0]["recipe_id"]

    trays_result = propose_meal_trays(
        recipes,
        fridge_items=fridge_items,
        people=people,
        missing_pantry=missing_pantry,
        soup_recipe_id=soup_recipe_id,
        limit=tray_candidates,
    )
    trays = trays_result.get("trays") or []
    if not trays:
        return {**trays_result, "stage": "propose_meal_trays"}

    picked = pick_best_meal_tray(
        trays,
        people=people,
        fridge_items=fridge_items,
        missing_pantry=missing_pantry,
        max_evaluate=max_evaluate,
    )
    if picked.get("error"):
        return {**picked, "stage": "pick_best_meal_tray", "tray_candidates": len(trays)}

    best = picked["best"]
    tray = best.get("tray") or {}
    return with_ai_review(
        "plan_one_meal",
        {
            "stage": "complete",
            "objective": "Minimize leftover_score after joint tray shopping simulation.",
            "meal_tray": {
                "soup": (tray.get("soup") or {}).get("name"),
                "main": (tray.get("main") or {}).get("name"),
                "side": (tray.get("side") or {}).get("name"),
            },
            "recipe_ids": best.get("recipe_ids"),
            "shared_ingredients": best.get("shared_ingredients", []),
            "total_price": best.get("total_price"),
            "leftover_score": best.get("leftover_score"),
            "adjusted_leftover_score": best.get("adjusted_leftover_score"),
            "leftover_detail": best.get("leftover_detail"),
            "shopping_selections": [
                {
                    "ingredient": s["ingredient"],
                    "product_name": (s.get("product") or {}).get("name"),
                    "quantity": s.get("quantity"),
                    "line_price": s.get("line_price"),
                    "leftover_amount": s.get("leftover_amount"),
                    "leftover_unit": s.get("leftover_unit"),
                }
                for s in best.get("selections") or []
            ],
            "ranking": picked.get("ranking"),
            "evaluated_count": picked.get("evaluated_count"),
            "from_fridge": best.get("from_fridge"),
            "assumed_at_home": best.get("assumed_at_home"),
            "failed_ingredients": best.get("failed_ingredients"),
            "skipped_unparsable": best.get("skipped_unparsable"),
        },
    )
