from __future__ import annotations

from postgrest.exceptions import APIError

from app.common.supabase_client import supabase

RECIPE_COLUMNS = (
    "recipe_id,name,inq_cnt,category,main_ingredient_group,occasion,"
    "difficulty,servings,method"
)
RECIPE_COLUMNS_LEGACY = (
    "recipe_id,name,category,main_ingredient_group,occasion,"
    "difficulty,servings,method"
)
INGREDIENT_COLUMNS = (
    "id,recipe_id,ingredient,canonical_ingredient,amount,unit,"
    "count,role,buy_required"
)
PRODUCT_COLUMNS = (
    "product_id,name,description,price,discount_price,discount_rate,"
    "category_name,package_amount,package_unit,package_count,"
    "package_count_unit"
)

PAGE_SIZE = 1000


def _fetch_all(table: str, columns: str, order_col: str) -> list[dict]:
    rows: list[dict] = []
    start = 0
    while True:
        end = start + PAGE_SIZE - 1
        response = (
            supabase.table(table)
            .select(columns)
            .order(order_col)
            .range(start, end)
            .execute()
        )
        batch = response.data or []
        rows.extend(batch)
        if len(batch) < PAGE_SIZE:
            break
        start += PAGE_SIZE
    return rows


class StartupCache:

    _instance: StartupCache | None = None

    def __init__(self) -> None:
        self._loaded = False
        self._recipes: list[dict] = []
        self._recipes_by_name: dict[str, dict] = {}
        self._ingredients_by_recipe: dict[int, list[dict]] = {}
        self._ingredient_names_by_recipe: dict[int, set[str]] = {}
        self._products_by_id: dict[int, dict] = {}

    @classmethod
    def instance(cls) -> StartupCache:
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @property
    def is_loaded(self) -> bool:
        return self._loaded

    def load(self) -> None:
        if self._loaded:
            return

        try:
            self._recipes = _fetch_all("recipes_v3", RECIPE_COLUMNS, "recipe_id")
        except APIError as exc:
            if "inq_cnt" not in str(exc):
                raise
            self._recipes = _fetch_all("recipes_v3", RECIPE_COLUMNS_LEGACY, "recipe_id")

        for row in self._recipes:
            row["inq_cnt"] = int(row.get("inq_cnt") or 0)

        by_name: dict[str, dict] = {}
        for row in self._recipes:
            name = row.get("name")
            if not name:
                continue
            prev = by_name.get(name)
            if prev is None or int(row.get("inq_cnt") or 0) > int(prev.get("inq_cnt") or 0):
                by_name[name] = row
        self._recipes_by_name = by_name

        for row in _fetch_all("recipe_ingredients_v3", INGREDIENT_COLUMNS, "id"):
            recipe_id = row["recipe_id"]
            self._ingredients_by_recipe.setdefault(recipe_id, []).append(row)
            display = (row.get("canonical_ingredient") or row.get("ingredient") or "").strip()
            if display:
                self._ingredient_names_by_recipe.setdefault(recipe_id, set()).add(display)

        for row in _fetch_all("products_v3", PRODUCT_COLUMNS, "product_id"):
            self._products_by_id[row["product_id"]] = row

        self._loaded = True

    def get_recipes(self) -> list[dict]:
        return list(self._recipes)

    def get_recipes_by_names(self, names: list[str]) -> list[dict]:
        return [self._recipes_by_name[name] for name in names if name in self._recipes_by_name]

    def get_ingredients(self, recipe_id: int) -> list[dict]:
        return list(self._ingredients_by_recipe.get(recipe_id, []))

    def get_ingredient_names(self, recipe_id: int) -> set[str]:
        return set(self._ingredient_names_by_recipe.get(recipe_id, set()))

    def get_product(self, product_id: int) -> dict | None:
        return self._products_by_id.get(product_id)

    def get_products_list(self) -> list[dict]:
        return list(self._products_by_id.values())


def get_cache() -> StartupCache:
    cache = StartupCache.instance()
    if not cache.is_loaded:
        cache.load()
    return cache
