from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from app.cache.startup_cache import StartupCache
from app.optimizer.preferences import get_weights
from app.services.ingredient_matcher import recipe_fridge_overlap
from app.services.nutrition import (
    enrich_recipe_nutrition,
    get_effective_kcal,
    get_effective_protein,
    get_protein_density,
    high_protein_sort_key,
    low_calorie_sort_key,
)
from app.services.recipe_service import RecipeService

SOUP_CATEGORIES = {"국&찌개"}
SIDE_CATEGORIES = {"반찬"}
MAIN_CATEGORIES = {"일품"}
DESSERT_CATEGORIES = {"후식"}

SLOT_LABELS = {
    "breakfast": "아침",
    "lunch": "점심",
    "dinner": "저녁",
}

WEEKDAY_LABELS = ["월", "화", "수", "목", "금", "토", "일"]

SLOT_TEMPLATES: dict[str, dict[str, Any]] = {
    "breakfast": {
        "rice": False,
        "kimchi": False,
        "soup": 0,
        "ipum": 1,
        "side": 1,
        "dessert": 1,
    },
    "lunch": {
        "rice": True,
        "kimchi": True,
        "soup": 1,
        "ipum": 0,
        "side": 2,
        "dessert": 0,
    },
    "dinner": {
        "rice": True,
        "kimchi": True,
        "soup": 1,
        "ipum": 0,
        "side": 2,
        "dessert": 1,
    },
}

VIRTUAL_RICE = {
    "recipe_id": None,
    "recipe_name": "백미밥",
    "category": "밥",
    "role": "rice",
    "virtual": True,
    "kcal": 310.0,
    "protein_g": 5.5,
}

VIRTUAL_KIMCHI = {
    "recipe_id": None,
    "recipe_name": "배추김치",
    "category": "반찬",
    "role": "kimchi",
    "virtual": True,
    "pantry": True,
    "kcal": 15.0,
    "protein_g": 1.0,
}


def slots_for_meals_per_day(meals_per_day: int) -> list[str]:
    if meals_per_day >= 3:
        return ["breakfast", "lunch", "dinner"]
    if meals_per_day == 2:
        return ["lunch", "dinner"]
    return ["lunch"]


class MealComposer:

    def __init__(
        self,
        recipe_service: RecipeService | None = None,
        cache: StartupCache | None = None,
    ) -> None:
        self.recipe_service = recipe_service or RecipeService()
        self._cache = cache

    @property
    def cache(self) -> StartupCache:
        if self._cache is None:
            from app.cache.startup_cache import get_cache

            self._cache = get_cache()
        return self._cache

    def compose(
        self,
        candidates: list[dict],
        *,
        duration_days: int,
        meals_per_day: int,
        preference: str,
        fridge_items: list[dict] | None = None,
        preferred_menus: list[str] | None = None,
        start_date: date | None = None,
    ) -> tuple[list[dict], list[dict]]:
        """Return (days, recipe_instances) for plan building."""

        fridge_items = fridge_items or []
        preferred_menus = preferred_menus or []
        pools = self._build_pools(candidates)
        ingredient_pool: set[str] = set()
        used_ids: set[int] = set()
        trays: list[dict] = []
        recipe_instances: list[dict] = []
        global_use_count: dict[int, int] = {}

        preferred_recipes, _ = self.recipe_service.resolve_menu_names(preferred_menus)
        preferred_ids = {row["recipe_id"] for row in preferred_recipes}

        base_date = start_date or date.today()
        slot_names = slots_for_meals_per_day(meals_per_day)

        for day_index in range(duration_days):
            current_date = base_date + timedelta(days=day_index)
            for slot_index, slot in enumerate(slot_names, start=1):
                tray = self._compose_tray(
                    slot=slot,
                    day=day_index + 1,
                    meal_index=slot_index,
                    pools=pools,
                    ingredient_pool=ingredient_pool,
                    used_ids=used_ids,
                    preferred_ids=preferred_ids,
                    preference=preference,
                    fridge_items=fridge_items,
                    tray_used_ids=set(),
                    global_use_count=global_use_count,
                )
                trays.append(tray)
                for dish in tray["dishes"]:
                    if dish.get("virtual"):
                        continue
                    recipe_id = dish.get("recipe_id")
                    if recipe_id is None:
                        continue
                    recipe = self._recipe_by_id(candidates, recipe_id)
                    if recipe:
                        recipe_instances.append(recipe)

        days = self._group_trays_by_day(trays, base_date)
        return days, recipe_instances

    def compose_day(
        self,
        candidates: list[dict],
        *,
        day: int,
        meals_per_day: int,
        preference: str,
        fridge_items: list[dict] | None = None,
        avoid_recipe_ids: set[int] | None = None,
        start_date: date | None = None,
    ) -> dict:
        """Compose trays for a single day (for date regeneration)."""

        fridge_items = fridge_items or []
        avoid_recipe_ids = avoid_recipe_ids or set()
        filtered = [row for row in candidates if row["recipe_id"] not in avoid_recipe_ids]
        pools = self._build_pools(filtered)
        ingredient_pool: set[str] = set()
        used_ids: set[int] = set()
        global_use_count: dict[int, int] = {}
        trays: list[dict] = []

        base_date = start_date or date.today()
        current_date = base_date + timedelta(days=day - 1)
        slot_names = slots_for_meals_per_day(meals_per_day)

        for slot_index, slot in enumerate(slot_names, start=1):
            tray = self._compose_tray(
                slot=slot,
                day=day,
                meal_index=slot_index,
                pools=pools,
                ingredient_pool=ingredient_pool,
                used_ids=used_ids,
                preferred_ids=set(),
                preference=preference,
                fridge_items=fridge_items,
                tray_used_ids=set(),
                global_use_count=global_use_count,
            )
            trays.append(tray)

        return {
            "day": day,
            "date": current_date.isoformat(),
            "weekday": WEEKDAY_LABELS[current_date.weekday()],
            "slots": {tray["slot"]: self._slot_payload(tray) for tray in trays},
        }

    def _compose_tray(
        self,
        *,
        slot: str,
        day: int,
        meal_index: int,
        pools: dict[str, list[dict]],
        ingredient_pool: set[str],
        used_ids: set[int],
        preferred_ids: set[int],
        preference: str,
        fridge_items: list[dict],
        tray_used_ids: set[int],
        global_use_count: dict[int, int],
    ) -> dict:
        template = SLOT_TEMPLATES[slot]
        dishes: list[dict] = []

        def pick(
            pool: list[dict],
            role: str,
            *,
            dessert_fallback: bool = False,
        ) -> None:
            recipe = self._pick_recipe(
                pool,
                used_ids=used_ids,
                tray_used_ids=tray_used_ids,
                global_use_count=global_use_count,
                ingredient_pool=ingredient_pool,
                preferred_ids=preferred_ids,
                preference=preference,
                fridge_items=fridge_items,
            )
            if not recipe and dessert_fallback:
                recipe = self._pick_recipe(
                    pools["side"],
                    used_ids=used_ids,
                    tray_used_ids=tray_used_ids,
                    global_use_count=global_use_count,
                    ingredient_pool=ingredient_pool,
                    preferred_ids=preferred_ids,
                    preference=preference,
                    fridge_items=fridge_items,
                )
            if recipe:
                dishes.append(self._recipe_dish(recipe, role=role))
                self._mark_used(recipe, used_ids, ingredient_pool, tray_used_ids, global_use_count)

        if template["rice"]:
            dishes.append(dict(VIRTUAL_RICE))

        for _ in range(template["soup"]):
            pick(pools["soup"], "soup")

        for _ in range(template["ipum"]):
            pick(pools["ipum"], "main")

        for _ in range(template["side"]):
            pick(pools["side"], "side")

        for _ in range(template["dessert"]):
            pick(pools["dessert"], "dessert", dessert_fallback=True)

        if template["kimchi"]:
            dishes.append(dict(VIRTUAL_KIMCHI))

        kcal = round(sum(float(d.get("kcal") or 0) for d in dishes), 1)
        protein_g = round(sum(float(d.get("protein_g") or 0) for d in dishes), 1)

        return {
            "day": day,
            "meal_index": meal_index,
            "slot": slot,
            "slot_label": SLOT_LABELS[slot],
            "dishes": dishes,
            "kcal": kcal,
            "protein_g": protein_g,
        }

    def _pick_recipe(
        self,
        pool: list[dict],
        *,
        used_ids: set[int],
        tray_used_ids: set[int],
        global_use_count: dict[int, int],
        ingredient_pool: set[str],
        preferred_ids: set[int],
        preference: str,
        fridge_items: list[dict],
    ) -> dict | None:
        if not pool:
            return None

        weights = get_weights(preference)
        ranked = [
            row
            for row in pool
            if row["recipe_id"] not in tray_used_ids
        ]
        if not ranked:
            ranked = list(pool)

        if preference == "high_protein":
            ranked.sort(key=lambda row: high_protein_sort_key(row), reverse=True)
        elif preference == "low_calorie":
            ranked.sort(key=lambda row: low_calorie_sort_key(row))

        best_recipe = None
        best_score = -1.0

        for recipe in ranked[:40]:
            overlap = self._ingredient_overlap(recipe, ingredient_pool)
            fridge_overlap = len(
                recipe_fridge_overlap(
                    self.cache.get_ingredient_names(recipe["recipe_id"]),
                    fridge_items,
                )
            )
            protein = get_effective_protein(recipe)
            protein_density = get_protein_density(recipe)
            kcal = get_effective_kcal(recipe)
            preferred_bonus = 50 if recipe["recipe_id"] in preferred_ids else 0
            reuse_count = global_use_count.get(recipe["recipe_id"], 0)
            reuse_penalty = reuse_count * 35

            if preference == "high_protein":
                score = (
                    protein_density * weights["nutrition"] * 12
                    + protein * weights["nutrition"] * 2
                    + overlap * weights["waste"] * 4
                    + fridge_overlap * 15
                    + preferred_bonus
                    - reuse_penalty
                )
            elif preference == "low_calorie":
                kcal_score = max(0.0, 400 - kcal) if kcal > 0 else 0.0
                score = (
                    kcal_score * weights["nutrition"] * 0.15
                    + protein * weights["nutrition"] * 0.5
                    + overlap * weights["waste"] * 4
                    + fridge_overlap * 15
                    + preferred_bonus
                    - reuse_penalty
                )
            else:
                score = (
                    overlap * 10 * weights["waste"]
                    + protein * weights["nutrition"]
                    + fridge_overlap * 25
                    + preferred_bonus
                    - reuse_penalty
                )

            if score > best_score:
                best_score = score
                best_recipe = recipe

        return best_recipe

    def _build_pools(self, candidates: list[dict]) -> dict[str, list[dict]]:
        return {
            "soup": [row for row in candidates if row.get("category") in SOUP_CATEGORIES],
            "side": [row for row in candidates if row.get("category") in SIDE_CATEGORIES],
            "ipum": [row for row in candidates if row.get("category") in MAIN_CATEGORIES],
            "dessert": [
                row for row in candidates if row.get("category") in DESSERT_CATEGORIES
            ],
        }

    def _recipe_dish(self, recipe: dict, *, role: str) -> dict:
        nutrition = enrich_recipe_nutrition(recipe)
        return {
            "recipe_id": recipe["recipe_id"],
            "recipe_name": recipe["name"],
            "category": recipe.get("category"),
            "role": role,
            "virtual": False,
            "kcal": recipe.get("kcal"),
            "protein_g": nutrition["protein_g"],
            "protein_density": nutrition.get("protein_density"),
            "nutrition_adjusted": nutrition.get("nutrition_adjusted", False),
        }

    def _mark_used(
        self,
        recipe: dict,
        used_ids: set[int],
        ingredient_pool: set[str],
        tray_used_ids: set[int],
        global_use_count: dict[int, int],
    ) -> None:
        recipe_id = recipe["recipe_id"]
        used_ids.add(recipe_id)
        tray_used_ids.add(recipe_id)
        global_use_count[recipe_id] = global_use_count.get(recipe_id, 0) + 1
        ingredient_pool.update(self.cache.get_ingredient_names(recipe_id))

    def _ingredient_overlap(self, recipe: dict, pool: set[str]) -> int:
        names = self.cache.get_ingredient_names(recipe["recipe_id"])
        return len(names.intersection(pool))

    def _recipe_by_id(self, candidates: list[dict], recipe_id: int) -> dict | None:
        for recipe in candidates:
            if recipe["recipe_id"] == recipe_id:
                return recipe
        return None

    def _group_trays_by_day(self, trays: list[dict], base_date: date) -> list[dict]:
        days_map: dict[int, dict] = {}

        for tray in trays:
            day = tray["day"]
            if day not in days_map:
                current_date = base_date + timedelta(days=day - 1)
                days_map[day] = {
                    "day": day,
                    "date": current_date.isoformat(),
                    "weekday": WEEKDAY_LABELS[current_date.weekday()],
                    "slots": {},
                }
            days_map[day]["slots"][tray["slot"]] = self._slot_payload(tray)

        return [days_map[day] for day in sorted(days_map)]

    def _slot_payload(self, tray: dict) -> dict:
        return {
            "slot": tray["slot"],
            "slot_label": tray["slot_label"],
            "dishes": tray["dishes"],
            "kcal": tray["kcal"],
            "protein_g": tray["protein_g"],
        }
