from app.cache.startup_cache import get_cache
from app.optimizer.greedy_solver import GreedySolver
from app.services.meal_composer import MealComposer


_solver = GreedySolver()
_composer = MealComposer()


def regenerate_meal_day(
    day: int,
    people: int = 1,
    meals_per_day: int = 3,
    preference: str = "minimize_waste",
    fridge_items: list[dict] | None = None,
    avoid_ingredients: list[str] | None = None,
    exclude_recipe_ids: list[int] | None = None,
) -> dict:
    """Regenerate breakfast/lunch/dinner trays for a single day."""

    get_cache().load()
    avoid_ingredients_set = set(avoid_ingredients or [])
    candidates = _solver._filter_recipes(avoid_ingredients_set)
    exclude_ids = set(exclude_recipe_ids or [])

    day_plan = _composer.compose_day(
        candidates,
        day=day,
        meals_per_day=meals_per_day,
        preference=preference,
        fridge_items=fridge_items or [],
        avoid_recipe_ids=exclude_ids,
    )

    return {
        "meta": {
            "scope": "day_regeneration",
            "day": day,
            "people": people,
            "meals_per_day": meals_per_day,
            "preference": preference,
        },
        "day": day_plan,
        "reasons": [
            f"{day_plan['date']}({day_plan['weekday']}) 식단을 "
            f"{preference} 기준으로 다시 구성했습니다."
        ],
    }
