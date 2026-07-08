"""Leftover-first meal tray helpers (no rice slot)."""

from __future__ import annotations

import math
from itertools import product as iter_product

from app.config.ingredient_unit_defaults import normalize_need_to_mass
from app.config.pantry_defaults import is_pantry_ingredient, normalize_missing_pantry
from app.parser.ingredient_parser import parse_recipe_ingredient, parse_servings
from app.parser.product_parser import effective_price
from app.services.ingredient_matcher import ingredients_match


SOUP_CATEGORIES = {"국&찌개"}
MAIN_CATEGORIES = {"일품"}
SIDE_CATEGORIES = {"반찬"}

# 밥상에 밥 슬롯이 없으므로 집에 있다고 가정 (구매 제외)
ASSUMED_STAPLES = {
    "밥",
    "쌀",
    "흰밥",
    "현미",
    "즉석밥",
    "밥솥밥",
    "냉동밥",
    "오뚜기밥",
}

# 일품 후보에서 제외 — 레시피에 밥/쌀이 재료로 들어가는 메뉴
RICE_STAPLES = ASSUMED_STAPLES | {"밥숭어", "볶은밥", "남은밥"}

# 데이터 품질 이슈로 구매 대상에서 제외하는 재료
SUSPICIOUS_INGREDIENT_TOKENS = (
    "손질생선",
    "손질 생선",
    "동전육수",
    "동전 육수",
    "생선살",
)


def _compact_name(name: str) -> str:
    return (name or "").replace(" ", "").strip().lower()


def is_assumed_staple(name: str) -> bool:
    compact = _compact_name(name)
    if not compact:
        return False
    return any(
        compact == staple.replace(" ", "").lower()
        or staple.replace(" ", "").lower() in compact
        for staple in ASSUMED_STAPLES
    )


def is_rice_staple(name: str) -> bool:
    compact = _compact_name(name)
    if not compact:
        return False
    normalized = {s.replace(" ", "").lower() for s in RICE_STAPLES}
    return compact in normalized or compact.endswith("밥")


def is_suspicious_ingredient(name: str) -> bool:
    compact = _compact_name(name)
    if not compact:
        return False
    return any(token.replace(" ", "").lower() in compact for token in SUSPICIOUS_INGREDIENT_TOKENS)


def recipe_requires_rice(recipe: dict, cache, *, missing_pantry: set[str] | None = None) -> bool:
    name = (recipe.get("name") or "").replace(" ", "")
    if name.endswith("밥") or "볶음밥" in name or "덮밥" in name:
        return True
    rid = recipe.get("recipe_id")
    rows = recipe.get("ingredients") or (cache.get_ingredients(rid) if rid else [])
    for row in rows:
        ing_name = ingredient_key(row)
        if is_rice_staple(ing_name):
            return True
    return False

def recipe_display_ingredients(recipe: dict) -> list[dict]:
    return list(recipe.get("ingredients") or [])


def ingredient_key(row: dict) -> str:
    return (row.get("canonical_ingredient") or row.get("ingredient") or "").strip()


def is_buyable(row: dict, missing_pantry: set[str] | None = None) -> bool:
    if row.get("buy_required") is False:
        return False
    name = ingredient_key(row)
    if not name:
        return False
    if is_assumed_staple(name) or is_suspicious_ingredient(name):
        return False
    if is_pantry_ingredient(name, missing_pantry=missing_pantry):
        return False
    compact = name.replace(" ", "")
    if compact in {"물", "쌀뜨물", "육수", "뜨거운물", "찬물"}:
        return False
    return True


def covered_by_fridge(name: str, fridge_items: list[dict]) -> bool:
    for item in fridge_items or []:
        fridge_name = item.get("ingredient") or ""
        if ingredients_match(name, fridge_name):
            return True
    return False


def score_recipe_for_fridge(
    recipe: dict,
    fridge_items: list[dict],
    *,
    missing_pantry: set[str] | None = None,
) -> dict:
    ingredients = recipe_display_ingredients(recipe)
    buyable = [row for row in ingredients if is_buyable(row, missing_pantry)]
    covered = [
        ingredient_key(row)
        for row in buyable
        if covered_by_fridge(ingredient_key(row), fridge_items)
    ]
    to_buy = [
        ingredient_key(row)
        for row in buyable
        if ingredient_key(row) not in covered
    ]
    buyable_n = max(len(buyable), 1)
    coverage = len(covered) / buyable_n
    return {
        "recipe_id": recipe.get("recipe_id"),
        "name": recipe.get("name"),
        "category": recipe.get("category"),
        "coverage": round(coverage, 3),
        "covered_count": len(covered),
        "buy_count": len(to_buy),
        "covered": covered,
        "to_buy": to_buy,
        "buyable_count": len(buyable),
    }


def aggregate_ingredients(
    recipes: list[dict],
    *,
    people: int = 1,
    fridge_items: list[dict] | None = None,
    missing_pantry: list[str] | None = None,
) -> dict:
    fridge_items = fridge_items or []
    missing = normalize_missing_pantry(missing_pantry)
    aggregated: dict[str, dict] = {}
    assumed_at_home: set[str] = set()

    for recipe in recipes:
        recipe_servings = parse_servings(recipe.get("servings"))
        for row in recipe_display_ingredients(recipe):
            name = ingredient_key(row)
            if not is_buyable(row, missing):
                if name and (
                    is_assumed_staple(name)
                    or is_suspicious_ingredient(name)
                    or is_pantry_ingredient(name, missing_pantry=missing)
                ):
                    assumed_at_home.add(name)
                continue
            parsed = parse_recipe_ingredient(
                row, people, recipe_servings=recipe_servings
            )
            name = parsed["ingredient"] or ingredient_key(row)
            if not name:
                continue
            mass_need = normalize_need_to_mass({**parsed, "ingredient": name})
            entry = aggregated.setdefault(
                name,
                {
                    "ingredient": name,
                    "required_amount": 0.0,
                    "required_unit": None,
                    "required_count": 0.0,
                    "required_count_unit": None,
                    "from_fridge": False,
                    "source_recipes": [],
                },
            )
            if recipe.get("name") and recipe["name"] not in entry["source_recipes"]:
                entry["source_recipes"].append(recipe["name"])
            if mass_need.get("required_amount") is not None and mass_need.get("required_unit") in {
                "g",
                "ml",
            }:
                unit = mass_need["required_unit"]
                if entry["required_unit"] is None:
                    entry["required_unit"] = unit
                if entry["required_unit"] == unit:
                    entry["required_amount"] += float(mass_need["required_amount"])
            elif parsed.get("required_amount") is not None:
                if entry["required_unit"] is None:
                    entry["required_unit"] = parsed.get("required_unit")
                if entry["required_unit"] == parsed.get("required_unit"):
                    entry["required_amount"] += float(parsed["required_amount"])
            if (
                mass_need.get("required_unit") not in {"g", "ml"}
                and parsed.get("required_count") is not None
            ):
                if entry["required_count_unit"] is None:
                    entry["required_count_unit"] = parsed.get("required_count_unit")
                if entry["required_count_unit"] == parsed.get("required_count_unit"):
                    entry["required_count"] += float(parsed["required_count"])

    buy_list: list[dict] = []
    assumed_fridge: list[str] = []
    for name, entry in aggregated.items():
        if covered_by_fridge(name, fridge_items):
            entry["from_fridge"] = True
            assumed_fridge.append(name)
            continue
        buy_list.append(entry)

    return {
        "buy_list": buy_list,
        "from_fridge": assumed_fridge,
        "assumed_at_home": sorted(assumed_at_home),
        "ingredient_count": len(aggregated),
        "buy_count": len(buy_list),
    }


def package_supply(product: dict) -> tuple[float | None, str | None]:
    amount = product.get("package_amount")
    unit = product.get("package_unit")
    if amount is not None and unit:
        return float(amount), str(unit)
    count = product.get("package_count")
    count_unit = product.get("package_count_unit")
    if count is not None and count_unit:
        return float(count), str(count_unit)
    return None, None


def is_package_parsable(product: dict) -> bool:
    supply, _ = package_supply(product)
    return supply is not None


def product_covers_need(product: dict, need: dict) -> bool:
    return leftover_for_need(product, need)["coverage"] != "unknown"


def leftover_for_need(product: dict, need: dict) -> dict:
    """Primary objective: leftover mass/count after covering need."""
    need = normalize_need_to_mass({**need, "ingredient": need.get("ingredient", "")})
    supply, supply_unit = package_supply(product)
    need_amount = need.get("required_amount") or 0.0
    need_unit = need.get("required_unit")
    need_count = need.get("required_count") or 0.0
    need_count_unit = need.get("required_count_unit")

    leftover_amount = None
    leftover_unit = None
    coverage = "unknown"
    qty = 1

    if supply is not None and supply_unit and need_amount and need_unit:
        if _units_compatible(supply_unit, need_unit):
            base_supply = _to_base(supply, supply_unit)
            base_need = _to_base(float(need_amount), need_unit)
            if base_need > 0 and base_supply > 0:
                qty = max(1, math.ceil(base_need / base_supply))
                leftover_amount = round(qty * base_supply - base_need, 2)
                leftover_unit = _base_unit(need_unit)
                coverage = "amount"

    if coverage == "unknown" and supply is not None and need_count and need_count_unit:
        if supply_unit == need_count_unit or (
            supply_unit and need_count_unit and supply_unit in need_count_unit
        ):
            qty = max(1, math.ceil(float(need_count) / supply))
            leftover_amount = round(qty * supply - float(need_count), 2)
            leftover_unit = need_count_unit
            coverage = "count"

    return {
        "quantity": qty,
        "leftover_amount": leftover_amount,
        "leftover_unit": leftover_unit,
        "coverage": coverage,
        "effective_price": effective_price(product) * qty,
        "conversion_note": need.get("conversion_note"),
    }


def _units_compatible(a: str, b: str) -> bool:
    a = a.lower()
    b = b.lower()
    mass = {"g", "kg"}
    vol = {"ml", "l"}
    return (a in mass and b in mass) or (a in vol and b in vol) or a == b


def _to_base(amount: float, unit: str) -> float:
    unit = unit.lower()
    if unit == "kg":
        return amount * 1000
    if unit == "l":
        return amount * 1000
    return amount


def _base_unit(unit: str) -> str:
    unit = unit.lower()
    if unit == "kg":
        return "g"
    if unit == "l":
        return "ml"
    return unit


def select_min_waste_product(
    candidates: list[dict],
    need: dict,
) -> dict | None:
    if not candidates:
        return None

    viable = [product for product in candidates if is_package_parsable(product)]
    if not viable:
        return None

    scored: list[tuple] = []
    for product in viable:
        meta = leftover_for_need(product, need)
        leftover = meta["leftover_amount"]
        leftover_key = (
            0 if leftover is not None else 1,
            float(leftover) if leftover is not None else 10**9,
            meta["effective_price"],
        )
        scored.append((leftover_key, product, meta))

    scored.sort(key=lambda item: item[0])
    _, best, meta = scored[0]
    return {
        "product": best,
        "quantity": meta["quantity"],
        "leftover_amount": meta["leftover_amount"],
        "leftover_unit": meta["leftover_unit"],
        "coverage": meta["coverage"],
        "line_price": meta["effective_price"],
        "reason": (
            "최소 잔량 우선"
            if meta["leftover_amount"] is not None
            else "패키지 파싱 가능 상품 중 가격 보조 선택"
        ),
    }


def parsable_kurly_products(products: list[dict]) -> list[dict]:
    return [product for product in products if is_package_parsable(product)]


def relevant_kurly_products(ingredient: str, products: list[dict]) -> list[dict]:
    products = parsable_kurly_products(products)
    if not products:
        return []
    token = (ingredient or "").replace(" ", "").lower()
    if not token:
        return products[:5]

    scored: list[tuple[int, dict]] = []
    for product in products:
        name = (product.get("name") or "").replace(" ", "").lower()
        desc = (product.get("description") or "").lower()
        score = 0
        if token in name:
            score += 3
        elif ingredient.lower() in (product.get("name") or "").lower():
            score += 2
        elif ingredient.lower() in desc:
            score += 1
        penalty_words = ("볶음밥", "라면", "스프", "소스", "양념", "햄", "어묵", "참기름", "들기름")
        if ingredient.replace(" ", "") in {"통깨", "참깨", "깨"} and "깨" not in name and "참깨" not in name:
            score -= 5
        if any(word in name for word in penalty_words) and token not in name:
            score -= 2
        scored.append((score, product))

    scored.sort(key=lambda item: (-item[0], effective_price(item[1])))
    positive = [p for s, p in scored if s > 0]
    if positive:
        return positive[:8]
    return [p for _, p in scored[:5]]


def recipes_by_ids(recipe_ids: list[int], cache) -> list[dict]:
    rows: list[dict] = []
    for rid in recipe_ids:
        for recipe in cache.get_recipes():
            if recipe["recipe_id"] != rid:
                continue
            rows.append(
                {
                    **recipe,
                    "ingredients": [
                        {
                            "ingredient": i.get("ingredient"),
                            "canonical_ingredient": i.get("canonical_ingredient"),
                            "amount": i.get("amount"),
                            "unit": i.get("unit"),
                            "count": i.get("count"),
                            "role": i.get("role"),
                            "buy_required": i.get("buy_required", True),
                        }
                        for i in cache.get_ingredients(rid)
                    ],
                }
            )
            break
    return rows


def simulate_tray_shopping(
    recipe_ids: list[int],
    *,
    people: int = 1,
    fridge_items: list[dict] | None = None,
    missing_pantry: list[str] | None = None,
    kurly_limit: int = 8,
    cache=None,
) -> dict:
    from app.cache.startup_cache import get_cache
    from app.services.kurly_client import search_kurly

    cache = cache or get_cache()
    if not recipe_ids:
        return {"error": "recipe_ids required"}

    recipe_rows = recipes_by_ids(recipe_ids, cache)
    if len(recipe_rows) != len(set(recipe_ids)):
        return {"error": "recipe_not_found", "recipe_ids": recipe_ids}

    buy = aggregate_ingredients(
        recipe_rows,
        people=people,
        fridge_items=fridge_items or [],
        missing_pantry=missing_pantry,
    )

    selections: list[dict] = []
    total_price = 0
    failed: list[str] = []
    skipped_unparsable: list[str] = []

    for item in buy["buy_list"]:
        ing = item["ingredient"]
        try:
            products = search_kurly(ing, limit=kurly_limit)
        except Exception as exc:  # noqa: BLE001
            failed.append(f"{ing}:{exc}")
            continue

        filtered = relevant_kurly_products(ing, products)
        if not filtered:
            skipped_unparsable.append(ing)
            continue

        chosen = select_min_waste_product(
            filtered,
            {
                "ingredient": ing,
                "required_amount": item.get("required_amount") or 0.0,
                "required_unit": item.get("required_unit"),
                "required_count": item.get("required_count") or 0.0,
                "required_count_unit": item.get("required_count_unit"),
            },
        )
        if not chosen:
            skipped_unparsable.append(ing)
            continue

        product = chosen["product"]
        qty = int(chosen["quantity"])
        line = effective_price(product) * qty
        total_price += line
        selections.append(
            {
                "ingredient": ing,
                "product": product,
                "quantity": qty,
                "leftover_amount": chosen.get("leftover_amount"),
                "leftover_unit": chosen.get("leftover_unit"),
                "coverage": chosen.get("coverage"),
                "line_price": line,
            }
        )

    score = score_cart_leftovers(selections)
    penalty = len(failed) * 500.0
    adjusted_score = float(score["leftover_score"]) + penalty
    tray_names = {r["recipe_id"]: r["name"] for r in recipe_rows}

    return {
        "recipe_ids": recipe_ids,
        "recipe_names": [tray_names.get(rid) for rid in recipe_ids],
        "buy_count": buy["buy_count"],
        "from_fridge": buy["from_fridge"],
        "assumed_at_home": buy.get("assumed_at_home", []),
        "selections": selections,
        "failed_ingredients": failed,
        "skipped_unparsable": skipped_unparsable,
        "total_price": total_price,
        "leftover_score": score["leftover_score"],
        "adjusted_leftover_score": round(adjusted_score, 1),
        "unknown_package_count": score["unknown_package_count"],
        "leftover_detail": score["items"],
        "leftover_summary": score["summary"],
    }


def pick_best_tray_by_shopping(
    trays: list[dict],
    *,
    people: int = 1,
    fridge_items: list[dict] | None = None,
    missing_pantry: list[str] | None = None,
    max_evaluate: int = 5,
    kurly_limit: int = 8,
    cache=None,
) -> dict:
    from app.cache.startup_cache import get_cache

    cache = cache or get_cache()
    if not trays:
        return {"error": "no_tray_candidates"}

    max_evaluate = max(1, min(int(max_evaluate), 10))
    evaluations: list[dict] = []

    for tray in trays[:max_evaluate]:
        ids = tray.get("recipe_ids") or []
        if len(ids) < 3:
            continue
        sim = simulate_tray_shopping(
            ids,
            people=people,
            fridge_items=fridge_items,
            missing_pantry=missing_pantry,
            kurly_limit=kurly_limit,
            cache=cache,
        )
        if sim.get("error"):
            continue
        evaluations.append(
            {
                **sim,
                "tray": tray.get("tray"),
                "shared_ingredients": tray.get("shared_ingredients", []),
                "pre_shop_waste_proxy": tray.get("pre_shop_waste_proxy"),
            }
        )

    if not evaluations:
        return {"error": "no_tray_evaluated"}

    evaluations.sort(
        key=lambda row: (
            row["adjusted_leftover_score"],
            row["leftover_score"],
            row.get("unknown_package_count", 99),
            row["total_price"],
        )
    )
    best = evaluations[0]
    return {
        "best": best,
        "ranking": [
            {
                "recipe_names": row["recipe_names"],
                "leftover_score": row["leftover_score"],
                "adjusted_leftover_score": row["adjusted_leftover_score"],
                "total_price": row["total_price"],
                "buy_count": row["buy_count"],
            }
            for row in evaluations
        ],
        "evaluated_count": len(evaluations),
        "objective": "Tray with lowest leftover after simulated joint shopping.",
    }


def score_cart_leftovers(selections: list[dict]) -> dict:
    items = []
    total_leftover_g = 0.0
    unknown = 0
    for row in selections:
        # Accept either flat rows or nested {ingredient, selection:{...}}
        if "selection" in row and isinstance(row.get("selection"), dict):
            sel = row["selection"]
            product = sel.get("product") or {}
            leftover = sel.get("leftover_amount")
            unit = sel.get("leftover_unit")
            coverage = sel.get("coverage")
            ingredient = row.get("ingredient") or sel.get("ingredient")
            product_name = product.get("name")
        else:
            leftover = row.get("leftover_amount")
            unit = row.get("leftover_unit")
            coverage = row.get("coverage")
            ingredient = row.get("ingredient")
            product = row.get("product") or {}
            product_name = (
                row.get("product_name")
                or product.get("name")
            )

        entry = {
            "ingredient": ingredient,
            "product_name": product_name,
            "leftover_amount": leftover,
            "leftover_unit": unit,
            "coverage": coverage,
        }
        items.append(entry)
        if leftover is None:
            unknown += 1
            continue
        if unit in {"g", "ml"}:
            total_leftover_g += float(leftover)
        else:
            total_leftover_g += float(leftover) * 50.0

    return {
        "leftover_score": round(total_leftover_g, 1),
        "unknown_package_count": unknown,
        "items": items,
        "summary": (
            f"추정 잔량 점수 {total_leftover_g:.0f} "
            f"(낮을수록 좋음; 미파싱 {unknown}건)"
        ),
    }


def propose_trays(
    recipes: list[dict],
    fridge_items: list[dict],
    *,
    missing_pantry: list[str] | None = None,
    limit: int = 5,
    people: int = 1,
    soup_recipe_id: int | None = None,
    cache=None,
) -> list[dict]:
    from app.cache.startup_cache import get_cache

    missing = normalize_missing_pantry(missing_pantry)
    cache = cache or get_cache()

    pool = {r["recipe_id"]: r for r in recipes if r.get("recipe_id")}
    for recipe in cache.get_recipes():
        rid = recipe["recipe_id"]
        if rid not in pool:
            pool[rid] = recipe

    soups = [r for r in pool.values() if r.get("category") in SOUP_CATEGORIES]
    mains = [
        r
        for r in pool.values()
        if r.get("category") in MAIN_CATEGORIES
        and not recipe_requires_rice(r, cache, missing_pantry=missing)
    ]
    sides = [r for r in pool.values() if r.get("category") in SIDE_CATEGORIES]

    if soup_recipe_id is not None:
        soups = [r for r in soups if r["recipe_id"] == soup_recipe_id]
    if not soups or not mains or not sides:
        return []

    def _buyable_names(recipe: dict) -> set[str]:
        rid = recipe["recipe_id"]
        rows = recipe.get("ingredients") or cache.get_ingredients(rid)
        return {
            ingredient_key(row)
            for row in rows
            if is_buyable(row, missing)
        }

    def _rank_by_shared(candidates: list[dict], anchor_names: set[str]) -> list[dict]:
        scored = []
        for recipe in candidates:
            overlap = len(_buyable_names(recipe) & anchor_names)
            scored.append((overlap, recipe))
        scored.sort(key=lambda item: (-item[0], item[1].get("name") or ""))
        return [recipe for _, recipe in scored]

    anchor_names: set[str] = set()
    if soups:
        anchor_names = _buyable_names(soups[0])

    soup_opts = soups[:5]
    main_opts = _rank_by_shared(mains, anchor_names)[:12]
    side_opts = _rank_by_shared(sides, anchor_names)[:15]

    candidates: list[dict] = []
    for soup, main, side in iter_product(soup_opts, main_opts, side_opts):
        tray_recipes_raw = [soup, main, side]
        tray_recipes = []
        for recipe in tray_recipes_raw:
            if recipe.get("ingredients"):
                tray_recipes.append(recipe)
            else:
                tray_recipes.append(
                    {
                        **recipe,
                        "ingredients": [
                            {
                                "ingredient": row.get("ingredient"),
                                "canonical_ingredient": row.get("canonical_ingredient"),
                                "amount": row.get("amount"),
                                "unit": row.get("unit"),
                                "count": row.get("count"),
                                "role": row.get("role"),
                                "buy_required": row.get("buy_required", True),
                            }
                            for row in cache.get_ingredients(recipe["recipe_id"])
                        ],
                    }
                )
        ids = [r["recipe_id"] for r in tray_recipes]
        if len(set(ids)) != len(ids):
            continue

        agg = aggregate_ingredients(
            tray_recipes,
            people=people,
            fridge_items=fridge_items,
            missing_pantry=missing_pantry,
        )
        name_sets = []
        for recipe in tray_recipes:
            names = {
                ingredient_key(row)
                for row in recipe_display_ingredients(recipe)
                if is_buyable(row, missing)
            }
            name_sets.append(names)
        shared = set.intersection(*name_sets) if name_sets else set()

        score = agg["buy_count"] * 10 - len(shared) * 8 - len(agg["from_fridge"])
        candidates.append(
            {
                "tray": {
                    "soup": _slim(tray_recipes[0]),
                    "main": _slim(tray_recipes[1]),
                    "side": _slim(tray_recipes[2]),
                },
                "recipes": [_slim(r) for r in tray_recipes],
                "recipe_ids": ids,
                "shared_ingredients": sorted(shared),
                "buy_count": agg["buy_count"],
                "from_fridge_count": len(agg["from_fridge"]),
                "buy_list_preview": [
                    {
                        "ingredient": item["ingredient"],
                        "required_amount": item["required_amount"],
                        "required_unit": item["required_unit"],
                    }
                    for item in agg["buy_list"][:10]
                ],
                "pre_shop_waste_proxy": score,
                "note": "각 슬롯은 반드시 레시피(국&찌개/일품/반찬). 낮을수록 잔량·구매 관점 유리.",
            }
        )

    candidates.sort(key=lambda row: (row["pre_shop_waste_proxy"], row["buy_count"]))
    seen: set[tuple] = set()
    unique: list[dict] = []
    for row in candidates:
        key = tuple(sorted(row["recipe_ids"]))
        if key in seen:
            continue
        seen.add(key)
        unique.append(row)
        if len(unique) >= limit:
            break
    return unique


def _slim(recipe: dict | None) -> dict | None:
    if not recipe:
        return None
    return {
        "recipe_id": recipe.get("recipe_id"),
        "name": recipe.get("name"),
        "category": recipe.get("category"),
    }
