import json
from pathlib import Path

INPUT = Path("data/processed/kurly/search_keywords.json")
OUTPUT = Path("data/processed/kurly/search_keyword_map.json")


def main():

    with open(INPUT, encoding="utf-8") as f:
        keywords = json.load(f)

    rows = []

    for item in keywords:

        keyword = item["search_keyword"]

        for ingredient in item["ingredients"]:

            rows.append({
                "ingredient": ingredient,
                "search_keyword": keyword
            })

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)

    with open(OUTPUT, "w", encoding="utf-8") as f:
        json.dump(rows, f, ensure_ascii=False, indent=2)

    print(f"Rows : {len(rows)}")


if __name__ == "__main__":
    main()