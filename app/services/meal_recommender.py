from app.cache.startup_cache import get_cache
from app.services.nutrition import get_effective_kcal, get_effective_protein, get_protein_density
from app.config.pantry_defaults import (
    PANTRY_ASSUMPTION_NOTE,
    normalize_missing_pantry,
)
from app.services.ingredient_matcher import recipe_fridge_overlap
from app.services.plan_builder import PlanBuilder
from app.services.recipe_service import RecipeService

SOUP_CATEGORIES = {"국&찌개"}
SIDE_CATEGORIES = {"반찬"}
MAX_SUGGESTIONS = 5
SINGLE_MEAL_SHOPPING_SOFT_LIMIT = 10_000


def _fridge_protein_tags(fridge_items: list[dict]) -> set[str]:

    tags: set[str] = set()
    for item in fridge_items:
        name = item.get("ingredient", "")
        if any(token in name for token in ("돼지", "한돈", "제육")):
            tags.add("pork")
        if any(token in name for token in ("소", "쇠고기", "한우")):
            tags.add("beef")
        if any(token in name for token in ("닭", "치킨")):
            tags.add("chicken")
    return tags


def _ingredient_protein_tag(name: str) -> str | None:

    if any(token in name for token in ("돼지", "한돈", "제육")):
        return "pork"
    if any(token in name for token in ("소고기", "쇠고기", "한우")):
        return "beef"
    if any(token in name for token in ("닭", "치킨")):
        return "chicken"
class MealRecommender:

    def __init__(self):

        self.recipe_service = RecipeService()
        self.plan_builder = PlanBuilder()
        self._cache = get_cache()

    def suggest(
        self,
        fridge_items: list[dict],
        *,
        people: int = 1,
        avoid_ingredients: list[str] | None = None,
        missing_pantry: list[str] | None = None,
        preference: str = "minimize_waste",
        include_side: bool = True,
    ) -> dict:

        missing_pantry_set = normalize_missing_pantry(missing_pantry)

        if not fridge_items:
            return {
                "meta": {
                    "scope": "single_meal",
                    "people": people,
                    "preference": preference,
                },
                "error": "fridge_items_required",
                "suggestions": [],
                "reasons": ["냉장고 재료 정보가 필요합니다."],
            }

        avoid_ingredients = set(avoid_ingredients or [])
        ranked = self._rank_recipes(
            fridge_items,
            avoid_ingredients,
            preference,
            missing_pantry_set,
        )
        if not ranked:
            return {
                "meta": {
                    "scope": "single_meal",
                    "people": people,
                    "preference": preference,
                },
                "fridge_items": fridge_items,
                "suggestions": [],
                "reasons": ["냉장고 재료로 만들 수 있는 메뉴를 찾지 못했습니다."],
            }

        suggestions: list[dict] = []
        used_combos: set[tuple[str, ...]] = set()

        soup_ranked = [
            row for row in ranked if row[0].get("category") in SOUP_CATEGORIES
        ]
        other_ranked = [
            row for row in ranked if row[0].get("category") not in SOUP_CATEGORIES
        ]

        candidate_rows = soup_ranked if soup_ranked else other_ranked

        for recipe, score, fridge_hits in candidate_rows:
            if len(suggestions) >= MAX_SUGGESTIONS:
                break

            recipes = [recipe]
            if include_side and recipe.get("category") in SOUP_CATEGORIES:
                side = self._find_side(recipe, ranked, avoid_ingredients)
                if side:
                    recipes.append(side)

            combo_key = tuple(row["name"] for row in recipes)
            if combo_key in used_combos:
                continue
            used_combos.add(combo_key)

            suggestion = self._build_suggestion(
                recipes,
                people=people,
                fridge_items=fridge_items,
                preference=preference,
                score=score,
                fridge_hits=fridge_hits,
                missing_pantry=missing_pantry,
            )
            suggestions.append(suggestion)

        suggestions.sort(
            key=lambda row: (
                not row["can_cook_without_shopping"],
                row["additional_shopping"]["total"],
                -row["fridge_match_count"],
            ),
        )

        return {
            "meta": {
                "scope": "single_meal",
                "people": people,
                "preference": preference,
                "meal_pattern": "soup_plus_side" if include_side else "single_dish",
            },
            "assumptions": {
                "pantry_assumed": True,
                "missing_pantry": sorted(missing_pantry_set),
                "note": PANTRY_ASSUMPTION_NOTE,
            },
            "fridge_items": fridge_items,
            "suggestions": suggestions,
            "reasons": self._global_reasons(suggestions, fridge_items),
            "next_actions": self._next_actions(suggestions),
        }

    def _rank_recipes(
        self,
        fridge_items: list[dict],
        avoid_ingredients: set[str],
        preference: str,
        missing_pantry: set[str],
    ) -> list[tuple[dict, float, list[str]]]:

        ranked: list[tuple[dict, float, list[str]]] = []
        fridge_proteins = _fridge_protein_tags(fridge_items)

        for recipe in self.recipe_service.get_all_recipes():
            ingredient_names = self._cache.get_ingredient_names(recipe["recipe_id"])
            if ingredient_names.intersection(avoid_ingredients):
                continue

            fridge_hits = recipe_fridge_overlap(ingredient_names, fridge_items)
            if not fridge_hits:
                continue

            mini_plan = self.plan_builder.build_from_recipes(
                [recipe],
                budget=None,
                people=1,
                duration_days=1,
                meals_per_day=1,
                preference=preference,
                fridge_items=fridge_items,
                missing_pantry=sorted(missing_pantry),
            )
            missing_rows = [
                row
                for row in mini_plan["ingredient_summary"]
                if (row.get("to_buy_amount") or 0) > 0
            ]
            missing_count = len(missing_rows)
            extra_cost = mini_plan["cost"]["total"]
            ingredient_count = len(ingredient_names)
            protein_bonus = get_effective_protein(recipe) / 10
            density_bonus = get_protein_density(recipe)

            score = (
                len(fridge_hits) * 100
                - missing_count * 15
                - extra_cost / 400
                - ingredient_count * 3
                + protein_bonus
            )
            if recipe.get("category") in SOUP_CATEGORIES:
                score += 40
            for row in missing_rows:
                protein_tag = _ingredient_protein_tag(row["ingredient"])
                if protein_tag and protein_tag not in fridge_proteins:
                    score -= 100
            if preference == "high_protein":
                score += protein_bonus * 2 + density_bonus * 4
            elif preference == "low_calorie":
                kcal = get_effective_kcal(recipe)
                if kcal > 0:
                    score += max(0.0, 350 - kcal) / 5
                score += protein_bonus
            elif preference == "minimize_cost":
                score -= extra_cost / 200

            ranked.append((recipe, score, fridge_hits))

        ranked.sort(key=lambda row: row[1], reverse=True)
        return ranked

    def _find_side(
        self,
        main_recipe: dict,
        ranked: list[tuple[dict, float, list[str]]],
        avoid_ingredients: set[str],
    ) -> dict | None:

        main_ingredients = self._cache.get_ingredient_names(main_recipe["recipe_id"])

        best_side = None
        best_score = -1.0

        for recipe, score, _ in ranked:
            if recipe["recipe_id"] == main_recipe["recipe_id"]:
                continue
            if recipe.get("category") not in SIDE_CATEGORIES:
                continue

            side_ingredients = self._cache.get_ingredient_names(recipe["recipe_id"])
            if side_ingredients.intersection(avoid_ingredients):
                continue

            overlap = len(main_ingredients.intersection(side_ingredients))
            combined_score = score + overlap * 5
            if combined_score > best_score:
                best_score = combined_score
                best_side = recipe

        return best_side

    def _build_suggestion(
        self,
        recipes: list[dict],
        *,
        people: int,
        fridge_items: list[dict],
        preference: str,
        score: float,
        fridge_hits: list[str],
        missing_pantry: list[str] | None = None,
    ) -> dict:

        plan = self.plan_builder.build_from_recipes(
            recipes,
            budget=None,
            people=people,
            duration_days=1,
            meals_per_day=len(recipes),
            preference=preference,
            fridge_items=fridge_items,
            missing_pantry=missing_pantry,
        )
        plan["meta"]["scope"] = "single_meal"

        pantry_assumed = [
            {
                "ingredient": row["ingredient"],
                "from_pantry": row.get("from_pantry"),
                "required_unit": row.get("required_unit"),
            }
            for row in plan["ingredient_summary"]
            if row.get("pantry_assumed")
        ]
        missing = [
            {
                "ingredient": row["ingredient"],
                "to_buy_amount": row.get("to_buy_amount"),
                "required_unit": row.get("required_unit"),
            }
            for row in plan["ingredient_summary"]
            if (row.get("to_buy_amount") or 0) > 0
        ]
        additional_total = plan["cost"]["total"]
        can_cook_without_shopping = additional_total == 0 and not missing
        shopping_reference_only = additional_total > SINGLE_MEAL_SHOPPING_SOFT_LIMIT

        fridge_usage = [
            {
                "ingredient": row["ingredient"],
                "from_fridge": row.get("from_fridge"),
                "required_unit": row.get("required_unit"),
            }
            for row in plan["ingredient_summary"]
            if (row.get("from_fridge") or 0) > 0
        ]

        dishes = []
        for meal in plan["meals"]:
            dishes.append(
                {
                    "recipe_id": meal["recipe_id"],
                    "recipe_name": meal["recipe_name"],
                    "category": meal.get("category"),
                    "role": "main" if meal.get("category") in SOUP_CATEGORIES else "side",
                    "protein_g": meal.get("protein_g") or meal.get("protein"),
                    "kcal": meal.get("kcal"),
                }
            )

        reasons = [
            f"냉장고 재료({', '.join(fridge_hits[:3])})를 활용하는 메뉴입니다.",
        ]
        if can_cook_without_shopping:
            reasons.append("기본 양념·조미료를 집에 있다고 보아 추가 장보기 없이 만들 수 있습니다.")
        elif additional_total <= SINGLE_MEAL_SHOPPING_SOFT_LIMIT:
            reasons.append(
                f"추가로 사야 할 재료 기준 약 {additional_total:,}원 수준입니다."
            )
        elif shopping_reference_only:
            reasons.append(
                "컬리 판매 단위 기준 참고가가 높습니다. 집에 김치·채소가 있으면 "
                "굳이 장보지 않아도 됩니다."
            )
        else:
            reasons.append(
                f"추가 구매 참고가 약 {additional_total:,}원입니다."
            )

        return {
            "dishes": dishes,
            "fridge_match_count": len(fridge_hits),
            "fridge_usage": fridge_usage,
            "pantry_assumed": pantry_assumed,
            "missing_ingredients": missing,
            "shopping_if_missing": plan.get("shopping_if_missing", []),
            "can_cook_without_shopping": can_cook_without_shopping,
            "shopping_reference_only": shopping_reference_only,
            "additional_shopping": {
                "total": additional_total,
                "items": plan["shopping_list"],
                "discount_savings": plan["cost"].get("discount_savings") or 0,
                "if_missing_pantry_total": plan["cost"].get("if_missing_pantry_total") or 0,
            },
            "leftovers": plan.get("leftovers", []),
            "ingredient_ledger": plan.get("ingredient_ledger", []),
            "nutrition_summary": plan.get("nutrition_summary", {}),
            "reasons": reasons,
            "score": round(score, 1),
        }

    def _global_reasons(
        self,
        suggestions: list[dict],
        fridge_items: list[dict],
    ) -> list[str]:

        if not suggestions:
            return []

        names = ", ".join(item["ingredient"] for item in fridge_items[:3])
        top = suggestions[0]["dishes"][0]["recipe_name"]
        reasons = [
            f"냉장고의 {names} 등을 활용해 한 끼 메뉴를 추천했습니다.",
            f"가장 추천하는 메뉴는 '{top}'입니다.",
            PANTRY_ASSUMPTION_NOTE,
        ]
        if suggestions[0]["can_cook_without_shopping"]:
            reasons.append("1순위 메뉴는 추가 장보기 없이 조리 가능합니다.")
        elif suggestions[0].get("shopping_reference_only"):
            reasons.append(
                "1순위는 메뉴 추천 위주입니다. 장보기 금액은 판매 단위 참고가일 뿐입니다."
            )
        return reasons

    def _next_actions(self, suggestions: list[dict]) -> list[dict]:

        if not suggestions:
            return []

        top = suggestions[0]
        menu_names = [dish["recipe_name"] for dish in top["dishes"]]
        actions = [
            {
                "tool": "analyze_cart",
                "args_hint": {"menus": menu_names},
            }
        ]
        if len(suggestions) > 1:
            actions.append(
                {
                    "tool": "optimize_meal_plan",
                    "args_hint": {
                        "duration_days": 7,
                        "preferred_menus": menu_names,
                    },
                }
            )
        return actions
