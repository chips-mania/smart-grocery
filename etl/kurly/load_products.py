import json
from pathlib import Path

from etl.common.batch_upsert import batch_upsert
from etl.common.logger import info, success

INPUT = Path("data/processed/kurly/products.json")


def main():

    with open(INPUT, encoding="utf-8") as f:
        rows = json.load(f)

    info(f"Products : {len(rows)}")

    batch_upsert(
        table_name="products",
        rows=rows,
        on_conflict="search_keyword,product_id",
    )

    success("Products upload complete")


if __name__ == "__main__":
    main()