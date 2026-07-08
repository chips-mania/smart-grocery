from app.config.pantry_defaults import (
    DEFAULT_PANTRY_LABELS,
    PANTRY_ASSUMPTION_NOTE,
    is_pantry_ingredient,
    normalize_missing_pantry,
)
from app.parser.ingredient_parser import parse_recipe_ingredient, parse_servings
from app.parser.product_parser import effective_price, parse_product_package
from app.optimizer.scorer import build_highlights, build_reasons, score_plan
from app.services.ingredient_matcher import ingredients_match
from app.services.meal_composer import SLOT_LABELS
from app.services.plan_enrichments import build_ingredient_ledger, build_nutrition_summary
from app.services.nutrition import enrich_recipe_nutrition, get_effective_protein
from app.services.product_service import ProductService
from app.services.recipe_service import RecipeService


class PlanBuilder:

    def __init__(self):

        self.recipe_service = RecipeService()
        self.product_service = ProductService()

    def build_from_recipes(
        self,
        recipes: list[dict],
        *,
        budget: int | None,
        people: int,
        duration_days: int = 1,
        meals_per_day: int = 1,
        preference: str = "minimize_waste",
        preferred_menus: list[str] | None = None,
        fridge_items: list[dict] | None = None,
        missing_pantry: list[str] | None = None,
    ) -> dict:

        fridge_items = fridge_items or []
        missing_pantry_set = normalize_missing_pantry(missing_pantry)
        meals = self._build_meals(recipes, duration_days, meals_per_day)
        ingredient_summary = self._aggregate_ingredients(
            recipes,
            people,
            fridge_items,
            missing_pantry_set,
        )
        shopping_list, discount_savings = self._build_shopping_list(
            ingredient_summary,
            preference,
        )
        shopping_if_missing, _ = self._build_shopping_if_missing(
            ingredient_summary,
            preference,
        )
        leftovers = self._build_leftovers(ingredient_summary, shopping_list)
        ingredient_ledger = build_ingredient_ledger(ingredient_summary, shopping_list)
        nutrition_summary = build_nutrition_summary(
            meals,
            preference=preference,
        )
        total = sum(item["effective_price"] for item in shopping_list)

        shared_ingredients = self._shared_ingredients(recipes)

        within_budget = True if budget is None else total <= budget
        budget_remaining = max(budget - total, 0) if budget is not None else None

        pantry_used = [
            row["ingredient"]
            for row in ingredient_summary
            if row.get("pantry_assumed")
        ]

        plan = {
            "meta": {
                "budget": budget,
                "people": people,
                "duration_days": duration_days,
                "meals_per_day": meals_per_day,
                "preference": preference,
                "total_meals": len(meals),
                "scope": "weekly_grocery",
            },
            "assumptions": {
                "pantry_assumed": True,
                "pantry_defaults": DEFAULT_PANTRY_LABELS,
                "pantry_ingredients_used": pantry_used,
                "missing_pantry": sorted(missing_pantry_set),
                "note": PANTRY_ASSUMPTION_NOTE,
            },
            "meals": meals,
            "nutrition_summary": nutrition_summary,
            "ingredient_summary": ingredient_summary,
            "ingredient_ledger": ingredient_ledger,
            "shopping_list": shopping_list,
            "shopping_if_missing": shopping_if_missing,
            "cost": {
                "total": total,
                "within_budget": within_budget,
                "budget_remaining": budget_remaining,
                "discount_savings": discount_savings,
                "if_missing_pantry_total": sum(
                    item["effective_price"] for item in shopping_if_missing
                ),
            },
            "leftovers": leftovers,
            "highlights": {
                "shared_ingredients": shared_ingredients,
                "fridge_savings": self._estimate_fridge_savings(fridge_items),
            },
        }

        scored = score_plan(plan, preference, preferred_menus)
        plan["score"] = scored["score"]
        plan["score_breakdown"] = scored["score_breakdown"]
        plan["reasons"] = build_reasons(plan)
        plan["highlights"] = build_highlights(plan)

        return plan

    def build_from_days(
        self,
        days: list[dict],
        recipe_instances: list[dict],
        *,
        budget: int | None,
        people: int,
        duration_days: int,
        meals_per_day: int,
        preference: str = "minimize_waste",
        preferred_menus: list[str] | None = None,
        fridge_items: list[dict] | None = None,
        missing_pantry: list[str] | None = None,
    ) -> dict:

        fridge_items = fridge_items or []
        missing_pantry_set = normalize_missing_pantry(missing_pantry)
        meals = self._build_meals_from_days(days)
        ingredient_summary = self._aggregate_ingredients(
            recipe_instances,
            people,
            fridge_items,
            missing_pantry_set,
        )
        shopping_list, discount_savings = self._build_shopping_list(
            ingredient_summary,
            preference,
        )
        shopping_if_missing, _ = self._build_shopping_if_missing(
            ingredient_summary,
            preference,
        )
        leftovers = self._build_leftovers(ingredient_summary, shopping_list)
        ingredient_ledger = build_ingredient_ledger(ingredient_summary, shopping_list)
        nutrition_summary = build_nutrition_summary(
            meals,
            preference=preference,
        )
        total = sum(item["effective_price"] for item in shopping_list)

        shared_ingredients = self._shared_ingredients(recipe_instances)

        within_budget = True if budget is None else total <= budget
        budget_remaining = max(budget - total, 0) if budget is not None else None

        pantry_used = [
            row["ingredient"]
            for row in ingredient_summary
            if row.get("pantry_assumed")
        ]

        plan = {
            "meta": {
                "budget": budget,
                "people": people,
                "duration_days": duration_days,
                "meals_per_day": meals_per_day,
                "preference": preference,
                "total_meals": len(meals),
                "meal_format": "tray",
                "scope": "weekly_grocery",
            },
            "days": days,
            "meals": meals,
            "nutrition_summary": nutrition_summary,
            "ingredient_summary": ingredient_summary,
            "ingredient_ledger": ingredient_ledger,
            "shopping_list": shopping_list,
            "shopping_if_missing": shopping_if_missing,
            "cost": {
                "total": total,
                "within_budget": within_budget,
                "budget_remaining": budget_remaining,
                "discount_savings": discount_savings,
                "if_missing_pantry_total": sum(
                    item["effective_price"] for item in shopping_if_missing
                ),
            },
            "leftovers": leftovers,
            "highlights": {
                "shared_ingredients": shared_ingredients,
                "fridge_savings": self._estimate_fridge_savings(fridge_items),
            },
        }

        scored = score_plan(plan, preference, preferred_menus)
        plan["score"] = scored["score"]
        plan["score_breakdown"] = scored["score_breakdown"]
        plan["reasons"] = build_reasons(plan)
        plan["highlights"] = build_highlights(plan)

        return plan

    def _build_meals_from_days(self, days: list[dict]) -> list[dict]:
        slot_order = {"breakfast": 1, "lunch": 2, "dinner": 3}
        meals: list[dict] = []

        for day_row in days:
            for slot_name, slot in day_row.get("slots", {}).items():
                dishes = slot.get("dishes", [])
                primary_recipe_id = next(
                    (dish["recipe_id"] for dish in dishes if dish.get("recipe_id")),
                    None,
                )
                dish_names = [dish["recipe_name"] for dish in dishes]
                meals.append(
                    {
                        "day": day_row["day"],
                        "date": day_row.get("date"),
                        "weekday": day_row.get("weekday"),
                        "meal_index": slot_order.get(slot_name, 1),
                        "slot": slot_name,
                        "slot_label": slot.get("slot_label")
                        or SLOT_LABELS.get(slot_name, slot_name),
                        "dishes": dishes,
                        "recipe_id": primary_recipe_id,
                        "recipe_name": " · ".join(dish_names),
                        "kcal": slot.get("kcal"),
                        "protein_g": slot.get("protein_g"),
                        "protein": slot.get("protein_g"),
                    }
                )

        return meals

    def _build_meals(
        self,
        recipes: list[dict],
        duration_days: int,
        meals_per_day: int,
    ) -> list[dict]:

        meals = []
        total_meals = duration_days * meals_per_day
        selected = recipes[:total_meals]

        for index, recipe in enumerate(selected):
            day = index // meals_per_day + 1
            meal_index = index % meals_per_day + 1
            nutrition = enrich_recipe_nutrition(recipe)
            meals.append(
                {
                    "day": day,
                    "meal_index": meal_index,
                    "recipe_id": recipe["recipe_id"],
                    "recipe_name": recipe["name"],
                    "category": recipe.get("category"),
                    "protein_g": nutrition["protein_g"],
                    "protein_raw": nutrition.get("protein_raw"),
                    "protein_density": nutrition.get("protein_density"),
                    "nutrition_adjusted": nutrition.get("nutrition_adjusted", False),
                    "kcal": recipe.get("kcal"),
                    "protein": nutrition["protein_g"],
                }
            )

        return meals

    def _aggregate_ingredients(
        self,
        recipes: list[dict],
        people: int,
        fridge_items: list[dict],
        missing_pantry: set[str],
    ) -> list[dict]:

        aggregated: dict[str, dict] = {}

        for recipe in recipes:
            rows = self.recipe_service.get_ingredients(recipe["recipe_id"])
            recipe_servings = parse_servings(recipe.get("servings"))
            for row in rows:
                if row.get("buy_required") is False:
                    continue
                parsed = parse_recipe_ingredient(
                    row, people, recipe_servings=recipe_servings
                )
                name = parsed["ingredient"]
                if name not in aggregated:
                    aggregated[name] = {
                        "ingredient": name,
                        "required_amount": 0.0,
                        "required_unit": parsed["required_unit"],
                        "required_count": 0.0,
                        "required_count_unit": parsed["required_count_unit"],
                        "parse_status": parsed["parse_status"],
                        "from_fridge": 0.0,
                        "from_pantry": 0.0,
                        "to_buy_amount": 0.0,
                        "pantry_assumed": False,
                    }

                entry = aggregated[name]
                if parsed["required_amount"] is not None:
                    if entry["required_unit"] is None:
                        entry["required_unit"] = parsed["required_unit"]
                    entry["required_amount"] += parsed["required_amount"]
                if parsed["required_count"] is not None:
                    if entry["required_count_unit"] is None:
                        entry["required_count_unit"] = parsed["required_count_unit"]
                    entry["required_count"] += parsed["required_count"]

                if parsed["parse_status"] == "failed":
                    entry["parse_status"] = "failed"
                elif parsed["parse_status"] == "partial" and entry["parse_status"] == "ok":
                    entry["parse_status"] = "partial"

        for name, entry in aggregated.items():
            fridge_amount = self._fridge_amount_for_ingredient(name, fridge_items)
            if fridge_amount > 0 and entry["required_amount"] is not None:
                entry["from_fridge"] = min(fridge_amount, entry["required_amount"])
                entry["to_buy_amount"] = max(
                    entry["required_amount"] - entry["from_fridge"],
                    0,
                )
            elif entry["required_amount"] is not None:
                entry["to_buy_amount"] = entry["required_amount"]

            if is_pantry_ingredient(name, missing_pantry=missing_pantry):
                pantry_amount = max(
                    (entry.get("required_amount") or 0) - (entry.get("from_fridge") or 0),
                    0,
                )
                entry["from_pantry"] = pantry_amount
                entry["pantry_assumed"] = pantry_amount > 0
                entry["pantry_buy_reference"] = entry.get("to_buy_amount") or 0
                entry["to_buy_amount"] = 0.0

        return list(aggregated.values())

    def _build_shopping_list(
        self,
        ingredient_summary: list[dict],
        preference: str,
    ) -> tuple[list[dict], int]:

        shopping_list: list[dict] = []
        discount_savings = 0

        for item in ingredient_summary:
            to_buy = item.get("to_buy_amount")
            if to_buy is not None and to_buy <= 0:
                continue

            products = self.product_service.get_products_by_ingredient(
                item["ingredient"],
                preference=preference,
            )
            if not products:
                continue

            product = self._select_product(products, item, preference)
            package = parse_product_package(
                product.get("name", ""),
                product.get("description") or "",
            )
            price = int(product.get("price") or 0)
            discount = product.get("discount_price")
            effective = effective_price(product)

            if discount and discount < price:
                discount_savings += price - effective

            leftover_amount, leftover_unit, leftover_confidence = self._calc_leftover(
                item,
                package,
            )

            shopping_list.append(
                {
                    "ingredient": item["ingredient"],
                    "search_keyword": product.get("search_keyword"),
                    "product_id": product.get("product_id"),
                    "product_name": product.get("name"),
                    "price": price,
                    "discount_price": discount,
                    "effective_price": effective,
                    "package_amount": package["package_amount"],
                    "package_unit": package["package_unit"],
                    "package_count": package["package_count"],
                    "package_count_unit": package["package_count_unit"],
                    "required_amount": item.get("to_buy_amount") or item.get("required_amount"),
                    "leftover_amount": leftover_amount,
                    "leftover_unit": leftover_unit,
                    "parse_status": package["parse_status"],
                    "leftover_confidence": leftover_confidence,
                    "selection_reason": f"rank {product.get('rank')}",
                }
            )

        return shopping_list, discount_savings

    def _build_shopping_if_missing(
        self,
        ingredient_summary: list[dict],
        preference: str,
    ) -> tuple[list[dict], int]:

        reference_items = [
            {**item, "to_buy_amount": item.get("pantry_buy_reference") or 0}
            for item in ingredient_summary
            if item.get("pantry_assumed") and (item.get("pantry_buy_reference") or 0) > 0
        ]
        return self._build_shopping_list(reference_items, preference)

    def _select_product(
        self,
        products: list[dict],
        ingredient_item: dict,
        preference: str,
    ) -> dict:

        if preference == "maximize_discount":
            discounted = [p for p in products if (p.get("discount_rate") or 0) > 0]
            if discounted:
                return discounted[0]

        if preference == "minimize_waste":
            return self._best_for_waste(products, ingredient_item)

        return min(products, key=effective_price)

    def _best_for_waste(self, products: list[dict], ingredient_item: dict) -> dict:

        required = ingredient_item.get("to_buy_amount") or ingredient_item.get("required_amount")
        required_unit = ingredient_item.get("required_unit")

        if required is None:
            return products[0]

        best = products[0]
        best_leftover = float("inf")

        for product in products:
            package = parse_product_package(
                product.get("name", ""),
                product.get("description") or "",
            )
            if (
                package["package_amount"] is not None
                and package["package_unit"] == required_unit
            ):
                leftover = max(package["package_amount"] - required, 0)
                if leftover < best_leftover:
                    best_leftover = leftover
                    best = product

        return best

    def _calc_leftover(
        self,
        ingredient_item: dict,
        package: dict,
    ) -> tuple[float | None, str | None, str]:

        required = ingredient_item.get("to_buy_amount") or ingredient_item.get("required_amount")
        required_unit = ingredient_item.get("required_unit")

        if required is None:
            return None, None, "unknown"

        if (
            package["package_amount"] is not None
            and package["package_unit"] == required_unit
        ):
            leftover = max(package["package_amount"] - required, 0)
            return leftover, required_unit, "high"

        if (
            package["package_count"] is not None
            and ingredient_item.get("required_count") is not None
            and package["package_count_unit"] == ingredient_item.get("required_count_unit")
        ):
            leftover = max(package["package_count"] - ingredient_item["required_count"], 0)
            return leftover, package["package_count_unit"], "high"

        return None, None, "unknown"

    def _build_leftovers(
        self,
        ingredient_summary: list[dict],
        shopping_list: list[dict],
    ) -> list[dict]:

        shop_map = {item["ingredient"]: item for item in shopping_list}
        leftovers = []

        for item in ingredient_summary:
            shop = shop_map.get(item["ingredient"])
            if not shop or shop.get("leftover_amount") is None:
                continue
            leftovers.append(
                {
                    "ingredient": item["ingredient"],
                    "amount": shop["leftover_amount"],
                    "unit": shop.get("leftover_unit"),
                    "leftover_confidence": shop.get("leftover_confidence"),
                }
            )

        return leftovers

    def _shared_ingredients(self, recipes: list[dict]) -> list[str]:

        counts: dict[str, int] = {}

        for recipe in recipes:
            rows = self.recipe_service.get_ingredients(recipe["recipe_id"])
            for row in rows:
                name = row["ingredient"]
                counts[name] = counts.get(name, 0) + 1

        return [name for name, count in counts.items() if count >= 2]

    def _estimate_fridge_savings(self, fridge_items: list[dict]) -> int:
        return len(fridge_items) * 1000

    def _fridge_amount_for_ingredient(
        self,
        ingredient_name: str,
        fridge_items: list[dict],
    ) -> float:

        total = 0.0
        for fridge in fridge_items:
            if ingredients_match(ingredient_name, fridge["ingredient"]):
                total += float(fridge.get("amount") or 0)
        return total
