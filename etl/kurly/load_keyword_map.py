from pathlib import Path
import json

from etl.common.batch_upsert import batch_upsert

INPUT = Path("data/processed/kurly/search_keyword_map.json")


def main():

    with open(INPUT, encoding="utf-8") as f:
        rows = json.load(f)

    batch_upsert(
        table_name="search_keyword_map",
        rows=rows,
    )


if __name__ == "__main__":
    main()