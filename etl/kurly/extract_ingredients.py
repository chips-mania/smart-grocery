import json
from pathlib import Path

from etl.common.supabase_client import supabase
from etl.common.logger import info, success

OUTPUT = Path("data/processed/kurly/ingredients.json")


def main():

    info("Loading ingredients from Supabase...")

    response = (
        supabase
        .table("recipe_ingredients")
        .select("ingredient")
        .execute()
    )

    rows = response.data

    ingredients = sorted({
        row["ingredient"].strip()
        for row in rows
        if row["ingredient"]
    })

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)

    with open(OUTPUT, "w", encoding="utf-8") as f:
        json.dump(ingredients, f, ensure_ascii=False, indent=2)

    success(f"Saved {len(ingredients)} ingredients")
    success(f"Output : {OUTPUT}")


if __name__ == "__main__":
    main()