import json
from pathlib import Path

from etl.common.batch_upsert import batch_insert, batch_upsert
from etl.common.logger import info, success
from etl.common.supabase_client import supabase

RECIPE_FILE = Path("data/processed/recipe/recipes.json")
INGREDIENT_FILE = Path("data/processed/recipe/recipe_ingredients.json")


def load_json(path: Path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def main():

    info("Loading recipe files...")

    recipes = load_json(RECIPE_FILE)
    ingredients = load_json(INGREDIENT_FILE)

    info(f"Recipes : {len(recipes)}")
    info(f"Ingredients : {len(ingredients)}")

    ##########################################
    # recipes
    ##########################################

    batch_upsert(
        table_name="recipes",
        rows=recipes,
    )

    ##########################################
    # recipe_ingredients
    ##########################################

    info("Deleting recipe_ingredients...")

    supabase.table("recipe_ingredients") \
        .delete() \
        .neq("id", 0) \
        .execute()

    info("Uploading recipe_ingredients...")

    batch_insert(
        table_name="recipe_ingredients",
        rows=ingredients,
    )

    success("Recipe upload complete")


if __name__ == "__main__":
    main()