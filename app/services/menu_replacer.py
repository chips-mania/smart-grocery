from app.cache.startup_cache import get_cache
from app.services.cart_analyzer import CartAnalyzer
from app.services.plan_builder import PlanBuilder
from app.services.recipe_service import RecipeService


class MenuReplacer:

    def __init__(self):

        self.recipe_service = RecipeService()
        self.plan_builder = PlanBuilder()
        self.cart_analyzer = CartAnalyzer()
        self._cache = get_cache()

    def replace(
        self,
        current_menus: list[str],
        menu_to_replace: str,
        people: int = 1,
        budget: int = 999_999,
        preference: str = "minimize_waste",
    ) -> dict:

        original_plan = self.cart_analyzer.analyze(
            menus=current_menus,
            people=people,
            budget=budget,
            preference=preference,
        )

        if original_plan.get("error"):
            return original_plan

        target_resolution = self.recipe_service.resolve_menu_name(menu_to_replace)
        if target_resolution is None:
            return {
                "error": "menu_not_found",
                "menu_to_replace": menu_to_replace,
            }

        target_recipe = target_resolution["recipe"]
        resolved_replace_name = target_resolution["resolved"]

        candidates = self._similar_candidates(
            target_recipe,
            {meal["recipe_name"] for meal in original_plan.get("meals", [])},
        )
        best_plan = None
        best_replacement = None
        best_savings = 0

        for candidate in candidates[:5]:
            new_menus = [
                candidate["name"]
                if menu in {menu_to_replace, resolved_replace_name}
                else menu
                for menu in current_menus
            ]
            updated = self.cart_analyzer.analyze(
                menus=new_menus,
                people=people,
                budget=budget,
                preference=preference,
            )
            savings = original_plan["cost"]["total"] - updated["cost"]["total"]
            if best_plan is None or savings > best_savings:
                best_plan = updated
                best_replacement = candidate
                best_savings = savings

        if best_plan is None or best_replacement is None:
            return {
                "original_plan": original_plan,
                "replacement": None,
                "message": "유사한 대체 메뉴를 찾지 못했습니다.",
            }

        return {
            "original_plan": original_plan,
            "replacement": {
                "removed_menu": menu_to_replace,
                "suggested_menu": best_replacement["name"],
                "similarity_score": self._similarity_score(target_recipe, best_replacement),
                "cost_before": original_plan["cost"]["total"],
                "cost_after": best_plan["cost"]["total"],
                "savings": max(best_savings, 0),
                "leftover_improved": len(best_plan.get("leftovers", []))
                <= len(original_plan.get("leftovers", [])),
                "reasons": best_plan.get("reasons", []),
            },
            "updated_plan": best_plan,
        }

    def _similar_candidates(
        self,
        target_recipe: dict,
        current_recipe_names: set[str],
    ) -> list[dict]:

        scored: list[tuple[float, dict]] = []

        for recipe in self.recipe_service.get_all_recipes():
            if recipe["name"] in current_recipe_names:
                continue

            score = self._similarity_score(target_recipe, recipe)
            if score < 0.3:
                continue

            scored.append((score, recipe))

        scored.sort(key=lambda item: item[0], reverse=True)
        return [recipe for _, recipe in scored]

    def _similarity_score(self, base: dict, candidate: dict) -> float:

        category_match = 1.0 if base.get("category") == candidate.get("category") else 0.0
        method_match = 1.0 if base.get("method") == candidate.get("method") else 0.0

        base_ingredients = self._cache.get_ingredient_names(base["recipe_id"])
        candidate_ingredients = self._cache.get_ingredient_names(candidate["recipe_id"])

        if not base_ingredients:
            shared_ratio = 0.0
        else:
            shared_ratio = len(base_ingredients.intersection(candidate_ingredients)) / len(
                base_ingredients
            )

        base_name = base.get("name", "")
        candidate_name = candidate.get("name", "")
        token_overlap = 1.0 if base_name[:2] == candidate_name[:2] and base_name else 0.0

        return (
            0.40 * category_match
            + 0.30 * shared_ratio
            + 0.20 * method_match
            + 0.10 * token_overlap
        )
