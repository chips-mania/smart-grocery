def build_nutrition_summary(meals: list[dict], *, preference: str) -> dict:

    total_protein = sum(float(meal.get("protein_g") or meal.get("protein") or 0) for meal in meals)
    total_kcal = sum(float(meal.get("kcal") or 0) for meal in meals)
    meal_count = len(meals) or 1
    adjusted_count = sum(1 for meal in meals if meal.get("nutrition_adjusted"))
    densities = [
        float(meal.get("protein_density") or 0)
        for meal in meals
        if meal.get("protein_density")
    ]

    summary = {
        "total_protein_g": round(total_protein, 1),
        "total_kcal": round(total_kcal, 1),
        "daily_avg_protein_g": round(total_protein / meal_count, 1),
        "daily_avg_kcal": round(total_kcal / meal_count, 1),
        "meal_count": meal_count,
        "preference": preference,
    }
    if densities:
        summary["avg_protein_density"] = round(sum(densities) / len(densities), 2)
    if adjusted_count:
        summary["adjusted_meal_count"] = adjusted_count
    return summary


def build_ingredient_ledger(
    ingredient_summary: list[dict],
    shopping_list: list[dict],
) -> list[dict]:

    shop_map = {row["ingredient"]: row for row in shopping_list}
    ledger: list[dict] = []

    for item in ingredient_summary:
        ingredient = item["ingredient"]
        shop = shop_map.get(ingredient)
        used_amount = item.get("required_amount")
        used_unit = item.get("required_unit")

        entry: dict = {
            "ingredient": ingredient,
            "used_amount": used_amount,
            "used_unit": used_unit,
            "from_fridge": item.get("from_fridge") or 0,
            "from_pantry": item.get("from_pantry") or 0,
            "to_buy_amount": item.get("to_buy_amount") or 0,
            "pantry_assumed": bool(item.get("pantry_assumed")),
        }

        if shop:
            entry.update(
                {
                    "product_name": shop.get("product_name"),
                    "effective_price": shop.get("effective_price"),
                    "purchased_amount": shop.get("package_amount"),
                    "purchased_unit": shop.get("package_unit"),
                    "purchased_count": shop.get("package_count"),
                    "purchased_count_unit": shop.get("package_count_unit"),
                    "leftover_amount": shop.get("leftover_amount"),
                    "leftover_unit": shop.get("leftover_unit"),
                    "leftover_confidence": shop.get("leftover_confidence"),
                    "source": "shopping",
                }
            )
        elif entry["from_pantry"] > 0:
            entry["source"] = "pantry_assumed"
        elif entry["from_fridge"] > 0:
            entry["source"] = "fridge"
        else:
            entry["source"] = "not_purchased"

        if used_amount or entry["from_fridge"] or entry["from_pantry"] or shop:
            ledger.append(entry)

    ledger.sort(
        key=lambda row: (
            row.get("source") != "shopping",
            -(row.get("effective_price") or 0),
        ),
    )
    return ledger
