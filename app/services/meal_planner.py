from app.optimizer.greedy_solver import GreedySolver


class MealPlanner:

    def __init__(self):

        self.solver = GreedySolver()

    def plan(
        self,
        budget: int | None,
        people: int,
        duration_days: int = 7,
        meals_per_day: int = 1,
        preferred_menus: list[str] | None = None,
        fridge_items: list[dict] | None = None,
        avoid_ingredients: list[str] | None = None,
        missing_pantry: list[str] | None = None,
        preference: str = "minimize_waste",
    ) -> dict:

        return self.solver.solve(
            budget=budget,
            people=people,
            duration_days=duration_days,
            meals_per_day=meals_per_day,
            preferred_menus=preferred_menus,
            fridge_items=fridge_items,
            avoid_ingredients=avoid_ingredients,
            missing_pantry=missing_pantry,
            preference=preference,
        )
