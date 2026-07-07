import json
from collections import defaultdict
from pathlib import Path

from etl.common.logger import info, success

RECIPE_FILE = Path("data/processed/recipe/recipes.json")
INGREDIENT_FILE = Path("data/processed/recipe/recipe_ingredients.json")

OUTPUT = Path("data/processed/kurly/ingredient_context.json")


def main():

    info("Loading recipe files...")

    with open(RECIPE_FILE, encoding="utf-8") as f:
        recipes = json.load(f)

    with open(INGREDIENT_FILE, encoding="utf-8") as f:
        ingredients = json.load(f)

    recipe_map = {
        recipe["recipe_id"]: recipe["name"]
        for recipe in recipes
    }

    grouped = defaultdict(list)

    for row in ingredients:

        ingredient = row["ingredient"].strip()

        grouped[ingredient].append({
            "recipe_id": row["recipe_id"],
            "recipe_name": recipe_map.get(row["recipe_id"], ""),
            "raw": row["raw"]
        })

    result = []

    for ingredient in sorted(grouped.keys()):

        result.append({
            "ingredient": ingredient,
            "recipes": grouped[ingredient]
        })

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)

    with open(OUTPUT, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    success(f"Ingredients : {len(result)}")
    success(f"Saved : {OUTPUT}")


if __name__ == "__main__":
    main()