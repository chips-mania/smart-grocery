from typing import Protocol

from app.cache.startup_cache import get_cache
from app.optimizer.plan_enricher import enrich_plan
from app.optimizer.preferences import get_weights
from app.services.nutrition import (
    get_effective_kcal,
    get_effective_protein,
    get_protein_density,
    high_protein_sort_key,
    low_calorie_sort_key,
)
from app.services.ingredient_matcher import recipe_fridge_overlap
from app.services.menu_matcher import apply_menu_resolution
from app.services.meal_composer import MealComposer
from app.services.plan_builder import PlanBuilder
from app.services.recipe_service import RecipeService


class Solver(Protocol):

    def solve(
        self,
        *,
        budget: int | None,
        people: int,
        duration_days: int,
        meals_per_day: int,
        preferred_menus: list[str],
        fridge_items: list[dict],
        avoid_ingredients: list[str],
        preference: str,
    ) -> dict:
        ...


class GreedySolver:

    def __init__(self):

        self.recipe_service = RecipeService()
        self.plan_builder = PlanBuilder()
        self.meal_composer = MealComposer(self.recipe_service)
        self._cache = get_cache()

    def solve(
        self,
        *,
        budget: int | None,
        people: int,
        duration_days: int,
        meals_per_day: int,
        preferred_menus: list[str] | None = None,
        fridge_items: list[dict] | None = None,
        avoid_ingredients: list[str] | None = None,
        missing_pantry: list[str] | None = None,
        preference: str = "minimize_waste",
    ) -> dict:

        preferred_menus = preferred_menus or []
        fridge_items = fridge_items or []
        avoid_ingredients = set(avoid_ingredients or [])
        total_meals = duration_days * meals_per_day

        candidates = self._filter_recipes(avoid_ingredients)
        menu_resolutions: list[dict] = []
        if preferred_menus:
            _, menu_resolutions = self.recipe_service.resolve_menu_names(preferred_menus)

        days, recipe_instances = self.meal_composer.compose(
            candidates,
            duration_days=duration_days,
            meals_per_day=meals_per_day,
            preference=preference,
            fridge_items=fridge_items,
            preferred_menus=preferred_menus,
        )

        plan = self.plan_builder.build_from_days(
            days,
            recipe_instances,
            budget=budget,
            people=people,
            duration_days=duration_days,
            meals_per_day=meals_per_day,
            preference=preference,
            preferred_menus=preferred_menus,
            fridge_items=fridge_items,
            missing_pantry=missing_pantry,
        )
        if menu_resolutions:
            plan = apply_menu_resolution(plan, menu_resolutions)

        expensive_menu = None
        alternative_plan = None
        if budget is not None and not plan["cost"]["within_budget"]:
            expensive_menu = self._most_expensive_menu(plan)
            if preference != "minimize_cost":
                alternative_plan = self._build_budget_alternative(
                    candidates=candidates,
                    total_meals=total_meals,
                    preferred_menus=preferred_menus,
                    budget=budget,
                    people=people,
                    duration_days=duration_days,
                    meals_per_day=meals_per_day,
                    fridge_items=fridge_items,
                    missing_pantry=missing_pantry,
                    menu_resolutions=menu_resolutions,
                )

        return enrich_plan(
            plan,
            budget=budget,
            duration_days=duration_days,
            people=people,
            meals_per_day=meals_per_day,
            preference=preference,
            expensive_menu=expensive_menu,
            alternative_plan=alternative_plan,
        )

    def _build_budget_alternative(
        self,
        *,
        candidates: list[dict],
        total_meals: int,
        preferred_menus: list[str],
        budget: int | None,
        people: int,
        duration_days: int,
        meals_per_day: int,
        fridge_items: list[dict],
        missing_pantry: list[str] | None,
        menu_resolutions: list[dict],
    ) -> dict | None:

        alt_days, alt_recipes = self.meal_composer.compose(
            candidates,
            duration_days=duration_days,
            meals_per_day=meals_per_day,
            preference="minimize_cost",
            fridge_items=fridge_items,
            preferred_menus=preferred_menus,
        )
        alt_plan = self.plan_builder.build_from_days(
            alt_days,
            alt_recipes,
            budget=budget,
            people=people,
            duration_days=duration_days,
            meals_per_day=meals_per_day,
            preference="minimize_cost",
            preferred_menus=preferred_menus,
            fridge_items=fridge_items,
            missing_pantry=missing_pantry,
        )
        if menu_resolutions:
            alt_plan = apply_menu_resolution(alt_plan, menu_resolutions)

        return alt_plan

    def _filter_recipes(self, avoid_ingredients: set[str]) -> list[dict]:

        recipes = self.recipe_service.get_all_recipes()

        if not avoid_ingredients:
            return recipes

        filtered = []
        for recipe in recipes:
            names = self._cache.get_ingredient_names(recipe["recipe_id"])
            if names.isdisjoint(avoid_ingredients):
                filtered.append(recipe)

        return filtered

    def _select_recipes(
        self,
        candidates: list[dict],
        *,
        total_meals: int,
        preferred_menus: list[str],
        preference: str,
        fridge_items: list[dict] | None = None,
    ) -> list[dict]:

        fridge_items = fridge_items or []
        selected: list[dict] = []
        used_ids: set[int] = set()

        preferred_recipes, _ = self.recipe_service.resolve_menu_names(preferred_menus)
        for recipe in preferred_recipes:
            if len(selected) >= total_meals:
                break
            if recipe["recipe_id"] not in used_ids:
                selected.append(recipe)
                used_ids.add(recipe["recipe_id"])

        remaining = [
            recipe
            for recipe in sorted(candidates, key=lambda row: row["recipe_id"])
            if recipe["recipe_id"] not in used_ids
        ]

        if not preferred_menus and fridge_items:
            fridge_first = [
                recipe
                for recipe in remaining
                if recipe_fridge_overlap(
                    self._cache.get_ingredient_names(recipe["recipe_id"]),
                    fridge_items,
                )
            ]
            if fridge_first:
                fridge_ids = {recipe["recipe_id"] for recipe in fridge_first}
                remaining = fridge_first + [
                    recipe for recipe in remaining if recipe["recipe_id"] not in fridge_ids
                ]

        ingredient_pool = self._ingredient_pool(selected)
        weights = get_weights(preference)

        if preference == "high_protein":
            remaining.sort(key=lambda row: high_protein_sort_key(row), reverse=True)
        elif preference == "low_calorie":
            remaining.sort(key=lambda row: low_calorie_sort_key(row))

        while len(selected) < total_meals and remaining:
            best_recipe = None
            best_score = -1.0

            pool_size = 50 if preference in ("high_protein", "low_calorie") else 30
            for recipe in remaining[: min(pool_size, len(remaining))]:
                overlap = self._ingredient_overlap(recipe, ingredient_pool)
                fridge_overlap = len(
                    recipe_fridge_overlap(
                        self._cache.get_ingredient_names(recipe["recipe_id"]),
                        fridge_items,
                    )
                )
                protein = get_effective_protein(recipe)
                protein_density = get_protein_density(recipe)
                kcal = get_effective_kcal(recipe)
                ingredient_count = len(
                    self._cache.get_ingredient_names(recipe["recipe_id"])
                )

                if preference == "high_protein":
                    score = (
                        protein_density * weights["nutrition"] * 12
                        + protein * weights["nutrition"] * 2
                        + overlap * weights["waste"] * 4
                        + fridge_overlap * 15
                    )
                elif preference == "low_calorie":
                    kcal_score = max(0.0, 400 - kcal) if kcal > 0 else 0.0
                    score = (
                        kcal_score * weights["nutrition"] * 0.15
                        + protein * weights["nutrition"] * 0.5
                        + overlap * weights["waste"] * 4
                        + fridge_overlap * 15
                    )
                elif preference == "minimize_cost":
                    score = (
                        -ingredient_count * weights["cost"] * 5
                        + fridge_overlap * 15
                    )
                elif preference == "maximize_discount":
                    score = overlap * weights["waste"] * 3 + protein * 0.1
                else:
                    score = (
                        overlap * 10 * weights["waste"]
                        + protein * weights["nutrition"]
                        + fridge_overlap * 25
                    )
                if score > best_score:
                    best_score = score
                    best_recipe = recipe

            if best_recipe is None:
                break

            selected.append(best_recipe)
            used_ids.add(best_recipe["recipe_id"])
            remaining.remove(best_recipe)
            ingredient_pool = self._ingredient_pool(selected)

        if len(selected) < total_meals:
            extras = [
                recipe
                for recipe in sorted(candidates, key=lambda row: row["recipe_id"])
                if recipe["recipe_id"] not in used_ids
            ]
            selected.extend(extras[: total_meals - len(selected)])

        return selected[:total_meals]

    def _most_expensive_menu(self, plan: dict) -> str | None:

        meals = plan.get("meals", [])
        if not meals:
            return None

        best_name = None
        best_count = -1

        for meal in meals:
            recipe_id = meal.get("recipe_id")
            if recipe_id is None:
                continue
            ingredient_count = len(self._cache.get_ingredient_names(recipe_id))
            if ingredient_count > best_count:
                best_count = ingredient_count
                best_name = meal["recipe_name"]

        return best_name

    def _ingredient_pool(self, recipes: list[dict]) -> set[str]:

        pool: set[str] = set()
        for recipe in recipes:
            pool.update(self._cache.get_ingredient_names(recipe["recipe_id"]))
        return pool

    def _ingredient_overlap(self, recipe: dict, pool: set[str]) -> int:

        names = self._cache.get_ingredient_names(recipe["recipe_id"])
        return len(names.intersection(pool))
