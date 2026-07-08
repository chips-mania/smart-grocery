from app.cache.startup_cache import get_cache
from app.optimizer.plan_enricher import enrich_plan
from app.services.menu_matcher import apply_menu_resolution
from app.services.plan_builder import PlanBuilder
from app.services.recipe_service import RecipeService


class CartAnalyzer:

    def __init__(self):

        self.recipe_service = RecipeService()
        self.plan_builder = PlanBuilder()
        self._cache = get_cache()

    def analyze(
        self,
        menus: list[str],
        people: int = 1,
        budget: int | None = None,
        missing_pantry: list[str] | None = None,
        preference: str = "minimize_waste",
    ) -> dict:

        recipes, resolutions = self.recipe_service.resolve_menu_names(menus)

        if not recipes:
            return {
                "error": "menus_not_found",
                "menus": menus,
                "suggestions": ["레시피 이름을 다시 확인해 주세요."],
            }

        plan = self.plan_builder.build_from_recipes(
            recipes,
            budget=budget,
            people=people,
            duration_days=len(recipes),
            meals_per_day=1,
            preference=preference,
            missing_pantry=missing_pantry,
        )
        plan = apply_menu_resolution(plan, resolutions)

        expensive_menu = self._most_expensive_menu(plan)

        return enrich_plan(
            plan,
            budget=budget,
            duration_days=len(recipes),
            people=people,
            meals_per_day=1,
            preference=preference,
            expensive_menu=expensive_menu,
        )

    def _most_expensive_menu(self, plan: dict) -> str | None:

        meals = plan.get("meals", [])
        if not meals:
            return None

        best_name = None
        best_count = -1

        for meal in meals:
            ingredient_count = len(self._cache.get_ingredient_names(meal["recipe_id"]))
            if ingredient_count > best_count:
                best_count = ingredient_count
                best_name = meal["recipe_name"]

        return best_name
