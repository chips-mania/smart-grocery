from app.services.meal_recommender import MealRecommender

_recommender = MealRecommender()


def suggest_meals_from_fridge(
    fridge_items: list[dict],
    people: int = 1,
    avoid_ingredients: list[str] | None = None,
    missing_pantry: list[str] | None = None,
    preference: str = "minimize_waste",
    include_side: bool = True,
) -> dict:

    return _recommender.suggest(
        fridge_items,
        people=people,
        avoid_ingredients=avoid_ingredients or [],
        missing_pantry=missing_pantry or [],
        preference=preference,
        include_side=include_side,
    )
