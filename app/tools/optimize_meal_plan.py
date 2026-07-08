from app.services.meal_planner import MealPlanner

_planner = MealPlanner()


def optimize_meal_plan(
    people: int = 2,
    duration_days: int = 7,
    meals_per_day: int = 3,
    budget: int | None = None,
    preferred_menus: list[str] | None = None,
    fridge_items: list[dict] | None = None,
    avoid_ingredients: list[str] | None = None,
    missing_pantry: list[str] | None = None,
    preference: str = "minimize_waste",
) -> dict:

    return _planner.plan(
        budget=budget,
        people=people,
        duration_days=duration_days,
        meals_per_day=meals_per_day,
        preferred_menus=preferred_menus or [],
        fridge_items=fridge_items or [],
        avoid_ingredients=avoid_ingredients or [],
        missing_pantry=missing_pantry or [],
        preference=preference,
    )
