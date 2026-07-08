"""Recipe popularity (inq_cnt) tie-breaking — runtime reads DB field only."""

from __future__ import annotations

import csv
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CSV = ROOT / "TB_RECIPE_SEARCH_251231.csv"


@lru_cache(maxsize=1)
def load_inq_cnt_by_recipe_id(csv_path: str | None = None) -> dict[int, int]:
    """ETL/backfill only. Runtime must not call this."""
    path = Path(csv_path) if csv_path else DEFAULT_CSV
    if not path.exists():
        return {}

    mapping: dict[int, int] = {}
    for encoding in ("cp949", "utf-8-sig", "utf-8"):
        try:
            with path.open(encoding=encoding, newline="") as handle:
                for row in csv.DictReader(handle):
                    raw_id = (row.get("RCP_SNO") or "").strip()
                    if not raw_id:
                        continue
                    try:
                        recipe_id = int(raw_id)
                        inq = int(float(row.get("INQ_CNT") or 0))
                    except (TypeError, ValueError):
                        continue
                    prev = mapping.get(recipe_id, 0)
                    if inq > prev:
                        mapping[recipe_id] = inq
            return mapping
        except UnicodeDecodeError:
            continue
    return mapping


def recipe_inq_cnt(recipe: dict) -> int:
    try:
        return int(recipe.get("inq_cnt") or 0)
    except (TypeError, ValueError):
        return 0


def sort_recipes_by_inq(recipes: list[dict], *, reverse: bool = True) -> list[dict]:
    return sorted(
        recipes,
        key=lambda row: (recipe_inq_cnt(row), row.get("name") or ""),
        reverse=reverse,
    )
