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
    recipes_by_ids,
    relevant_kurly_products,
    score_cart_leftovers,
    score_recipe_for_fridge,
    select_min_waste_product,
    simulate_tray_shopping,
)
from app.services.ingredient_matcher import normalize_fridge_items
from app.services.recipe_service import RecipeService

_recipe_service = RecipeService()

_SEARCH_DEFAULT_LIMIT = 8


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


def _compact_recipe_row(recipe: dict) -> dict:
    """Shrink recipe payload for PlayMCP tool response size limits."""
    row = {k: v for k, v in recipe.items() if k != "ingredients"}
    ingredients = recipe.get("ingredients") or []
    buy_names: list[str] = []
    for item in ingredients:
        if not item.get("buy_required", True):
            continue
        name = (item.get("canonical_ingredient") or item.get("ingredient") or "").strip()
        if name and name not in buy_names:
            buy_names.append(name)
    row["ingredient_count"] = len(ingredients)
    row["buy_ingredients"] = buy_names[:12]
    fit = row.get("fridge_fit")
    if isinstance(fit, dict) and isinstance(fit.get("covered"), list):
        fit = dict(fit)
        fit["covered"] = fit["covered"][:8]
        row["fridge_fit"] = fit
    return row


def _format_menu_ingredients(recipe_rows: list[dict]) -> list[dict]:
    from app.services.ingredient_matcher import dedupe_ingredient_rows

    out: list[dict] = []
    for recipe in recipe_rows:
        ingredients = dedupe_ingredient_rows(recipe.get("ingredients") or [])
        out.append(
            {
                "recipe_id": recipe.get("recipe_id"),
                "name": recipe.get("name"),
                "category": recipe.get("category"),
                "ingredients": [
                    {
                        "ingredient": item.get("ingredient"),
                        "canonical_ingredient": item.get("canonical_ingredient"),
                        "amount": item.get("amount"),
                        "unit": item.get("unit"),
                        "count": item.get("count"),
                        "buy_required": item.get("buy_required", True),
                    }
                    for item in ingredients
                ],
            }
        )
    return out


def _build_recommendation_reason(
    *,
    meal_tray: dict[str, str | None],
    from_fridge: list[str] | None,
    shared_ingredients: list[str] | None,
    buy_count: int | None,
    total_price: int | float | None,
    leftover_score: float | None,
    leftover_summary: str | None,
    evaluated_count: int | None,
    query: str | None = None,
    fridge_items: list[dict] | None = None,
) -> str:
    """Korean explanation for why this tray was recommended (shown to end user)."""
    from app.services.ingredient_matcher import fridge_ingredient_names

    parts: list[str] = []
    dish_names = [meal_tray.get(slot) for slot in ("soup", "main", "side") if meal_tray.get(slot)]
    if dish_names:
        parts.append(f"국·메인·반찬으로 {' · '.join(dish_names)} 조합을 제안합니다.")

    if query and query.strip():
        parts.append(f"요청하신 '{query.strip()}' 메뉴 의도를 반영했습니다.")

    if from_fridge:
        parts.append(f"냉장고 재료({', '.join(from_fridge)})를 활용합니다.")
    elif fridge_items:
        wanted = ", ".join(fridge_ingredient_names(fridge_items))
        if wanted:
            parts.append(f"냉장고에 있는 {wanted}를 쓰는 요리를 우선 골랐습니다.")

    shared = [name for name in (shared_ingredients or []) if name]
    if shared:
        label = ", ".join(shared[:4])
        if len(shared) > 4:
            label += f" 외 {len(shared) - 4}개"
        parts.append(f"{label} 재료를 여러 요리가 함께 써 장보기 낭비를 줄입니다.")

    if evaluated_count and evaluated_count > 1:
        parts.append(f"후보 {evaluated_count}개 밥상을 컬리 장보기 시뮬레이션으로 비교했습니다.")

    if leftover_score is not None:
        summary = leftover_summary or f"잔여 식재료 점수 {round(leftover_score, 1)}"
        parts.append(f"{summary}(낮을수록 남는 재료가 적음) 기준으로 선택했습니다.")

    if buy_count is not None:
        if total_price is not None:
            parts.append(f"추가 구매 {buy_count}종, 예상 합계 {int(total_price):,}원입니다.")
        else:
            parts.append(f"추가 구매가 필요한 재료는 {buy_count}종입니다.")

    if parts:
        return " ".join(parts)
    return "잔여 식재료를 줄이는 한 끼 밥상으로 구성했습니다."


def _meal_tray_from_best(best: dict) -> dict[str, str | None]:
    tray = best.get("tray") or {}
    return {
        "soup": (tray.get("soup") or {}).get("name"),
        "main": (tray.get("main") or {}).get("name"),
        "side": (tray.get("side") or {}).get("name"),
    }


def _format_shopping_selection(selection: dict) -> dict:
    product = selection.get("product") or {}
    return {
        "ingredient": selection.get("ingredient"),
        "product_name": product.get("name"),
        "product_id": product.get("product_id"),
        "price": product.get("price"),
        "discount_price": product.get("discount_price"),
        "effective_price": product.get("effective_price") or effective_price(product),
        "quantity": selection.get("quantity"),
        "line_price": selection.get("line_price"),
        "required_amount": selection.get("required_amount"),
        "required_unit": selection.get("required_unit"),
        "leftover_amount": selection.get("leftover_amount"),
        "leftover_unit": selection.get("leftover_unit"),
        "package_amount": product.get("package_amount"),
        "package_unit": product.get("package_unit"),
    }


def search_recipes(
    query: str | None = None,
    fridge_items: list[dict] | None = None,
    category: str | None = None,
    limit: int = _SEARCH_DEFAULT_LIMIT,
) -> dict:
    """Search recipes by dish name and/or fridge leftovers.

    fridge_items: [{"ingredient": "돼지고기"}] — name key also accepted.
    """
    cache = get_cache()
    fridge_items = normalize_fridge_items(fridge_items)
    limit = max(1, min(int(limit), 15))
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
        from app.services.ingredient_matcher import fridge_ingredient_names
        from app.services.ingredient_matcher import ingredients_match

        fridge_names = fridge_ingredient_names(fridge_items)
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

    elif allowed:
        for recipe in sort_recipes_by_inq(cache.get_recipes()):
            if recipe.get("category") not in allowed:
                continue
            if all(r["recipe_id"] != recipe["recipe_id"] for r in recipes):
                recipes.append(recipe)
            if len(recipes) >= limit:
                break

    recipes = sort_recipes_by_inq(_attach_ingredients(recipes))[:limit]
    for recipe in recipes:
        if "fridge_fit" not in recipe and fridge_items:
            recipe["fridge_fit"] = score_recipe_for_fridge(recipe, fridge_items)

    compact = [_compact_recipe_row(recipe) for recipe in recipes]
    return with_ai_review(
        "search_recipes",
        {
            "count": len(compact),
            "recipes": compact,
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
    fridge_items = normalize_fridge_items(fridge_items)
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
    fridge_items = normalize_fridge_items(fridge_items)
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
                "Browse-only. For optimized buy list and leftovers use plan_one_meal."
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
    fridge_items = normalize_fridge_items(fridge_items)
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
    fridge_items = normalize_fridge_items(fridge_items)
    get_cache()
    result = pick_best_tray_by_shopping(
        trays,
        people=people,
        fridge_items=fridge_items,
        missing_pantry=missing_pantry,
        max_evaluate=max_evaluate,
        kurly_limit=kurly_limit,
    )
    best = result.get("best")
    if best and not result.get("error"):
        meal_tray = _meal_tray_from_best(best)
        result["recommendation_reason"] = _build_recommendation_reason(
            meal_tray=meal_tray,
            from_fridge=best.get("from_fridge"),
            shared_ingredients=best.get("shared_ingredients"),
            buy_count=best.get("buy_count"),
            total_price=best.get("total_price"),
            leftover_score=best.get("leftover_score"),
            leftover_summary=best.get("leftover_summary"),
            evaluated_count=result.get("evaluated_count"),
            fridge_items=fridge_items,
        )
    return with_ai_review("pick_best_meal_tray", result)


def plan_one_meal(
    query: str | None = None,
    fridge_items: list[dict] | None = None,
    people: int = 1,
    soup_recipe_id: int | None = None,
    missing_pantry: list[str] | None = None,
    tray_candidates: int = 5,
    max_evaluate: int = 3,
) -> dict:
    """End-to-end: search → propose trays → simulate shopping for top-k → pick best."""
    fridge_items = normalize_fridge_items(fridge_items)
    try:
        return _plan_one_meal_impl(
            query=query,
            fridge_items=fridge_items,
            people=people,
            soup_recipe_id=soup_recipe_id,
            missing_pantry=missing_pantry,
            tray_candidates=tray_candidates,
            max_evaluate=max_evaluate,
        )
    except Exception as exc:  # noqa: BLE001
        return {"error": "plan_failed", "message": str(exc), "query": query}


def _plan_one_meal_impl(
    *,
    query: str | None,
    fridge_items: list[dict],
    people: int,
    soup_recipe_id: int | None,
    missing_pantry: list[str] | None,
    tray_candidates: int,
    max_evaluate: int,
) -> dict:
    get_cache()
    tray_candidates = max(3, min(int(tray_candidates), 8))
    max_evaluate = max(1, min(int(max_evaluate), 5))
    search_limit = max(tray_candidates, 12) if fridge_items and not (query or "").strip() else tray_candidates
    found = search_recipes(
        query=query,
        fridge_items=fridge_items,
        limit=search_limit,
    )
    recipes = found.get("recipes") or []
    if not recipes and not soup_recipe_id:
        return {"error": "no_recipes", "query": query}

    cache = get_cache()
    if soup_recipe_id is None and recipes:
        soup_candidates = [
            recipe for recipe in recipes if recipe.get("category") in SOUP_CATEGORIES
        ]
        if not soup_candidates and fridge_items:
            from app.services.ingredient_matcher import recipe_fridge_overlap

            for recipe in cache.get_recipes():
                if recipe.get("category") not in SOUP_CATEGORIES:
                    continue
                if recipe_fridge_overlap(
                    cache.get_ingredient_names(recipe["recipe_id"]),
                    fridge_items,
                ):
                    soup_candidates.append(recipe)
        if soup_candidates:
            soup_recipe_id = sort_recipes_by_inq(soup_candidates)[0]["recipe_id"]
        elif query:
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
        kurly_limit=5,
    )
    if picked.get("error"):
        return {**picked, "stage": "pick_best_meal_tray", "tray_candidates": len(trays)}

    best = picked["best"]
    tray = best.get("tray") or {}
    recipe_ids = best.get("recipe_ids") or []
    cache = get_cache()
    recipe_rows = recipes_by_ids(recipe_ids, cache)
    buy_result = aggregate_ingredients(
        recipe_rows,
        people=people,
        fridge_items=fridge_items,
        missing_pantry=missing_pantry,
    )
    meal_tray = {
        "soup": (tray.get("soup") or {}).get("name"),
        "main": (tray.get("main") or {}).get("name"),
        "side": (tray.get("side") or {}).get("name"),
    }
    from_fridge = buy_result.get("from_fridge") or best.get("from_fridge")
    buy_list = buy_result.get("buy_list") or []
    return {
        "stage": "complete",
        "meal_tray": meal_tray,
        "recommendation_reason": _build_recommendation_reason(
            meal_tray=meal_tray,
            from_fridge=from_fridge,
            shared_ingredients=best.get("shared_ingredients"),
            buy_count=len(buy_list),
            total_price=best.get("total_price"),
            leftover_score=best.get("leftover_score"),
            leftover_summary=best.get("leftover_summary"),
            evaluated_count=picked.get("evaluated_count"),
            query=query,
            fridge_items=fridge_items,
        ),
        "recipe_ids": recipe_ids,
        "menu_ingredients": _format_menu_ingredients(recipe_rows),
        "shared_ingredients": best.get("shared_ingredients", []),
        "from_fridge": from_fridge,
        "assumed_at_home": buy_result.get("assumed_at_home") or best.get(
            "assumed_at_home", []
        ),
        "buy_list": buy_list,
        "total_price": best.get("total_price"),
        "leftover_score": best.get("leftover_score"),
        "leftover_summary": best.get("leftover_summary"),
        "shopping_selections": [
            _format_shopping_selection(s) for s in best.get("selections") or []
        ],
        "evaluated_count": picked.get("evaluated_count"),
        "failed_ingredients": best.get("failed_ingredients"),
        "skipped_unparsable": best.get("skipped_unparsable"),
    }
